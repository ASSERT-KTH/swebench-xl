#!/usr/bin/env python3
"""Harbor agent that measures benchmark instance size instead of solving it.

``RepoTokenizerAgent`` never attempts the task. On ``run()`` it locates the
task's working directory inside the environment, downloads its contents to
the host, and tokenizes every text file with tiktoken (via ``tiktoken``'s
``cl100k_base`` encoding by default). The result is a per-file / per-extension
token breakdown that's useful for estimating how large a benchmark instance's
repository is, independent of whether any agent can actually solve it.

- The repository is fetched by archiving it inside the environment (with
  VCS/dependency/build noise excluded) and extracting that archive on the
  host, so this works against any Harbor environment backend (local Docker,
  remote sandboxes, ...), not just one where the filesystem is directly
  mounted. Extraction uses tarfile's permissive ``"tar"`` filter rather than
  Harbor's own stricter ``"data"`` filter (see ``_download_repo`` below) —
  some repos' test fixtures intentionally contain symlinks to absolute paths
  (e.g. Helm's chart-loader tests, which symlink to ``/dev/null``), and
  ``"data"`` refuses to extract those.
- Results are written using Harbor's own conventions: a detailed
  ``token_counts.json``, a per-file ``files.csv.gz`` and an ATIF ``trajectories/trajectory.json`` under the
  agent's log directory (``self.logs_dir``, i.e. ``<trial_dir>/agent/``), and
  a summary on ``AgentContext.metadata`` so it shows up in each trial's
  ``result.json``. See ``benchmark_size_stats.py`` for aggregating these
  per-instance numbers (mean/median/stdev) across a whole ``harbor run`` job.
- The actual walk/skip-list/tokenization logic lives in ``tokenizer_core.py``
  (ported from ``tokenizer copy.py``) and has no Harbor dependency of its own.
"""

from __future__ import annotations

import json
import shlex
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, override

import tiktoken

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trajectories import (
    Agent as TrajectoryAgent,
    FinalMetrics,
    Observation,
    ObservationResult,
    Step,
    ToolCall,
    Trajectory,
)

from tokenizer_core import (
    DEFAULT_ENCODING_NAME,
    SKIP_DIRS,
    build_token_result,
    walk_and_count,
    write_files_csv,
)

# ---------------------------------------------------------------------------
# Repo transfer
# ---------------------------------------------------------------------------

# Container-side scratch location for the transfer archive.
_TRANSFER_TAR_DIR = "/tmp"


async def _download_repo(
    environment: BaseEnvironment, source_dir: str, target_dir: Path
) -> None:
    """Archive `source_dir` inside the environment (excluding SKIP_DIRS) and
    extract it into `target_dir` on the host.

    This is a near-identical reimplementation of Harbor's own
    ``BaseEnvironment.download_dir_with_exclusions``, with one deliberate
    difference: extraction uses tarfile's ``"tar"`` filter instead of
    Harbor's ``"data"`` filter. ``"data"`` (Python's strictest, meant for
    untrusted archives) refuses to extract any symlink or hardlink that
    targets an absolute path, raising ``tarfile.AbsoluteLinkError``. Some
    repos' test fixtures do this intentionally — e.g. Helm's chart-loader
    tests ship a fixture symlinked to ``/dev/null`` specifically to exercise
    that edge case — which made every task built on such a repo fail before
    tokenization even started. ``"tar"`` still blocks path traversal and
    absolute *destination* paths; it's only the "trust this symlink target"
    check that's relaxed, which is fine here since the archive is one we
    generate ourselves from a container we already control, not third-party
    input.
    """
    exclude_flags = " ".join(f"--exclude={shlex.quote(p)}" for p in sorted(SKIP_DIRS))
    tar_name = f".repo-tokenizer-transfer-{uuid.uuid4()}.tar.gz"
    remote_tar_path = f"{_TRANSFER_TAR_DIR}/{tar_name}"

    result = await environment.exec(
        command=(
            f"tar czf {shlex.quote(remote_tar_path)} {exclude_flags} "
            f"-C {shlex.quote(source_dir)} ."
        ),
        user="root",
        timeout_sec=120,
    )
    if result.return_code != 0:
        raise RuntimeError(
            f"Failed to archive {source_dir!r} for download "
            f"(exit {result.return_code}): {result.stderr or result.stdout}"
        )

    try:
        with tempfile.TemporaryDirectory(prefix="repo-tokenizer-tar-") as host_tmp:
            host_tar_path = Path(host_tmp) / tar_name
            await environment.download_file(remote_tar_path, host_tar_path)
            with tarfile.open(host_tar_path, "r:gz") as tf:
                tf.extractall(path=target_dir, filter="tar")
    finally:
        await environment.exec(
            command=f"rm -f {shlex.quote(remote_tar_path)}",
            user="root",
            timeout_sec=120,
        )


# ---------------------------------------------------------------------------
# Harbor agent
# ---------------------------------------------------------------------------


class RepoTokenizerAgent(BaseAgent):
    """Measures a task's repository size instead of attempting the task.

    Register/run with Harbor as an import-path agent, e.g.::

        harbor run -d "<dataset@version>" --agent tokenizer_agent:RepoTokenizerAgent

    See the README for the full setup (PYTHONPATH, dependencies, output
    locations) and ``benchmark_size_stats.py`` for aggregating results across
    a whole job into mean/median/stdev.
    """

    # This agent only ever runs `pwd`/`test -d`/`tar` style POSIX probes to
    # locate the task's working directory before downloading it.
    SUPPORTS_WINDOWS: bool = False

    # We emit a schema-valid ATIF trajectory (single deterministic step,
    # `llm_call_count=0`) under `<logs_dir>/trajectories/trajectory.json`.
    SUPPORTS_ATIF: bool = True

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        *,
        testbed_dir: str | None = None,
        encoding_name: str = DEFAULT_ENCODING_NAME,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            testbed_dir: Absolute path inside the environment to tokenize.
                Defaults to auto-discovery: the ``TESTBED_DIR`` env var if
                set, else ``/testbed`` if present, else the agent user's
                default working directory.
            encoding_name: tiktoken encoding to use. Defaults to
                ``cl100k_base`` (overridable via ``TIKTOKEN_ENCODING``).
        """
        super().__init__(logs_dir, model_name=model_name, **kwargs)
        self._testbed_dir_override = testbed_dir
        self._encoding_name = encoding_name

    @staticmethod
    @override
    def name() -> str:
        return "repo-tokenizer"

    @override
    def version(self) -> str | None:
        return "1.1.0"

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        # Tokenization runs on the host against a downloaded copy of the repo
        # (see run()), so nothing needs to be installed in the environment.
        return

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        t0 = time.monotonic()
        instance_id = environment.environment_name or environment.session_id

        testbed_dir = await self._resolve_testbed_dir(environment)

        with tempfile.TemporaryDirectory(prefix="repo-tokenizer-") as tmp_dir:
            local_repo = Path(tmp_dir)
            await _download_repo(environment, testbed_dir, local_repo)

            enc = tiktoken.get_encoding(self._encoding_name)
            file_results, by_extension = walk_and_count(local_repo, enc)

        elapsed = time.monotonic() - t0

        token_result = build_token_result(
            instance_id, file_results, by_extension, self._encoding_name
        )

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._write_token_counts(token_result)
        write_files_csv(file_results, self.logs_dir / "files.csv.gz")
        self._write_trajectory(instance_id, testbed_dir, token_result, elapsed)

        # Harbor-native per-trial result: shows up under `agent_result.metadata`
        # in the trial's result.json.
        context.metadata = {
            "repo_tokenizer": {
                "instance_id": instance_id,
                "testbed_dir": testbed_dir,
                "encoding": token_result["encoding"],
                "total_tokens": token_result["total_tokens"],
                "total_files": token_result["total_files"],
                "source_code_tokens": token_result["source_code_tokens"],
                "source_code_files": token_result["source_code_files"],
                "total_lines": token_result["total_lines"],
                "total_bytes": token_result["total_bytes"],
                "source_code_lines": token_result["source_code_lines"],
                "source_code_bytes": token_result["source_code_bytes"],
                "skipped_files": token_result["skipped_files"],
                "elapsed_sec": round(elapsed, 2),
            }
        }

    async def _resolve_testbed_dir(self, environment: BaseEnvironment) -> str:
        """Locate the task's working directory inside the environment.

        Priority: explicit `testbed_dir` kwarg > `$TESTBED_DIR` > `/testbed`
        (the conventional path for file-graded/SWE-bench-style tasks) >
        the agent user's default working directory.
        """
        if self._testbed_dir_override:
            return self._testbed_dir_override

        env_result = await environment.exec(
            command='printf "%s" "${TESTBED_DIR:-}"'
        )
        candidate = (env_result.stdout or "").strip()
        if candidate:
            return candidate

        probe = await environment.exec(command="test -d /testbed")
        if probe.return_code == 0:
            return "/testbed"

        pwd_result = await environment.exec(command="pwd -P")
        cwd = (pwd_result.stdout or "").strip()
        if not cwd:
            raise RuntimeError(
                "Could not determine the task's working directory to tokenize "
                "(checked $TESTBED_DIR, /testbed, and `pwd`)"
            )
        return cwd

    def _write_token_counts(self, token_result: dict[str, Any]) -> None:
        out_path = self.logs_dir / "token_counts.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(token_result, f, indent=2)

    def _write_trajectory(
        self,
        instance_id: str,
        testbed_dir: str,
        token_result: dict[str, Any],
        elapsed_seconds: float,
    ) -> None:
        traj_dir = self.logs_dir / "trajectories"
        traj_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "total_tokens": token_result["total_tokens"],
            "total_files": token_result["total_files"],
            "source_code_tokens": token_result["source_code_tokens"],
            "source_code_files": token_result["source_code_files"],
            "top_extension": next(iter(token_result["by_extension"]), "N/A"),
        }

        step = Step(
            step_id=1,
            source="agent",
            message=f"Tokenized {testbed_dir!r} for instance {instance_id!r}",
            llm_call_count=0,  # deterministic dispatch, no LLM involved
            tool_calls=[
                ToolCall(
                    tool_call_id="tc_1",
                    function_name="walk_and_count",
                    arguments={
                        "testbed_dir": testbed_dir,
                        "encoding": token_result["encoding"],
                    },
                )
            ],
            observation=Observation(
                results=[
                    ObservationResult(
                        source_call_id="tc_1",
                        content=json.dumps(summary),
                    )
                ]
            ),
        )

        trajectory = Trajectory(
            session_id=self.session_id,
            agent=TrajectoryAgent(name=self.name(), version=self.version() or "1.0.0"),
            steps=[step],
            notes=(
                "Deterministic repo-sizing agent: does not attempt the task, "
                "only tokenizes its working directory with tiktoken."
            ),
            final_metrics=FinalMetrics(
                total_steps=1,
                extra={
                    "repo_total_tokens": token_result["total_tokens"],
                    "repo_source_code_tokens": token_result["source_code_tokens"],
                    "repo_total_files": token_result["total_files"],
                    "repo_source_code_files": token_result["source_code_files"],
                    "elapsed_seconds": round(elapsed_seconds, 2),
                },
            ),
        )

        out_path = traj_dir / "trajectory.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(trajectory.to_json_dict(), indent=2))
