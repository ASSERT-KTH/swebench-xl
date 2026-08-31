#!/usr/bin/env python3
"""Harbor agent that measures benchmark instance size instead of solving it.

``RepoTokenizerAgent`` never attempts the task. On ``run()`` it locates the
task's working directory inside the environment, downloads its contents to
the host, and tokenizes every text file with tiktoken (via ``tiktoken``'s
``cl100k_base`` encoding by default). The result is a per-file / per-extension
token breakdown that's useful for estimating how large a benchmark instance's
repository is, independent of whether any agent can actually solve it.

- The repository is fetched via ``BaseEnvironment.download_dir_with_exclusions``
  instead of being walked in place, so this works against any Harbor
  environment backend (local Docker, remote sandboxes, ...), not just one
  where the filesystem is directly mounted.
- Results are written using Harbor's own conventions: a detailed
  ``token_counts.json`` and an ATIF ``trajectories/trajectory.json`` under the
  agent's log directory (``self.logs_dir``, i.e. ``<trial_dir>/agent/``), and
  a summary on ``AgentContext.metadata`` so it shows up in each trial's
  ``result.json``. See ``benchmark_size_stats.py`` for aggregating these
  per-instance numbers (mean/median/stdev) across a whole ``harbor run`` job.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
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

# ---------------------------------------------------------------------------
# Tokenization configuration (unchanged from ``tokenizer copy.py``)
# ---------------------------------------------------------------------------

DEFAULT_ENCODING_NAME = os.environ.get("TIKTOKEN_ENCODING", "cl100k_base")

TOP_N_FILES = 50

# Directories to skip entirely (fast-path before os.walk descends, and also
# used to keep them out of the environment->host download in the first place).
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
    "venv",
    ".venv",
    "env",
    "build",
    "dist",
    ".gradle",
    ".idea",
    ".vscode",
}

# Extensions we deliberately don't tokenize. Includes true binaries
# (compiled artifacts, images, archives, media) as well as text formats
# whose content is structurally noisy and low-signal for repo-size
# estimation (e.g. .svg path data, .lock files).
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".jar", ".war", ".ear",
    ".so", ".dylib", ".dll", ".exe", ".o", ".a",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".db", ".sqlite", ".sqlite3",
    ".bin", ".dat", ".pkl", ".pickle", ".npy", ".npz",
    ".parquet", ".avro",
    ".DS_Store",
}

# Source code extensions — aggregated separately as a "signal" subset.
SOURCE_CODE_EXTENSIONS = {
    # Python
    ".py", ".pyx", ".pxd", ".pyi",
    # Java / JVM
    ".java", ".kt", ".kts", ".scala", ".groovy", ".gradle",
    # JavaScript / TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # C / C++
    ".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx",
    # C#
    ".cs", ".csx",
    # Go
    ".go",
    # Rust
    ".rs",
    # Ruby
    ".rb", ".rake",
    # PHP
    ".php",
    # Swift / Objective-C
    ".swift", ".m", ".mm",
    # Shell
    ".sh", ".bash", ".zsh",
    # Lua
    ".lua",
    # R
    ".r", ".R",
    # Perl
    ".pl", ".pm",
    # Elixir / Erlang
    ".ex", ".exs", ".erl",
    # Haskell
    ".hs",
    # Dart
    ".dart",
    # PowerShell
    ".ps1", ".psm1",
}

# Max chunk size (chars) fed to tiktoken in a single encode call.
# tiktoken's cl100k_base regex can stack-overflow during backtracking on
# pathological inputs (long single-line strings, dense regex/template text
# common in TS/JS test fixtures). Chunking sidesteps this.
_ENCODE_CHUNK_CHARS = 25_000


def should_skip_extension(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() in SKIP_EXTENSIONS


def try_read_text(path: str) -> str | None:
    """Return file text or None if the file appears binary."""
    try:
        with open(path, "r", encoding="utf-8", errors="strict") as f:
            return f.read()
    except (UnicodeDecodeError, ValueError):
        return None
    except OSError:
        return None


def _safe_encode_count(enc: tiktoken.Encoding, content: str) -> int:
    """Count tokens for `content`, chunking to avoid tiktoken regex backtracking errors."""
    if len(content) <= _ENCODE_CHUNK_CHARS:
        try:
            return len(enc.encode(content, disallowed_special=()))
        except ValueError:
            pass  # Fall through to chunked path

    total = 0
    n = len(content)
    i = 0
    while i < n:
        end = min(i + _ENCODE_CHUNK_CHARS, n)
        # Prefer to break on a newline to avoid splitting tokens unnecessarily
        if end < n:
            nl = content.rfind("\n", i, end)
            if nl > i:
                end = nl + 1
        chunk = content[i:end]
        try:
            total += len(enc.encode(chunk, disallowed_special=()))
        except ValueError:
            # Last-resort: shrink further. If even a tiny chunk fails,
            # fall back to a char-based approximation for that slice.
            sub_size = 4096
            j = 0
            while j < len(chunk):
                sub = chunk[j : j + sub_size]
                try:
                    total += len(enc.encode(sub, disallowed_special=()))
                except ValueError:
                    # Approximate: ~4 chars per token for unencodable slices.
                    total += max(1, len(sub) // 4)
                j += sub_size
        i = end
    return total


def walk_and_count(
    repo_dir: Path, enc: tiktoken.Encoding
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Walk a local copy of the repo tree and return per-file token counts."""
    file_results: list[dict[str, Any]] = []
    by_extension: dict[str, dict[str, int]] = {}  # ext → {tokens, files}

    for root, dirs, files in os.walk(repo_dir):
        # Prune skipped directories in-place so os.walk won't descend
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            fpath = os.path.join(root, fname)

            if should_skip_extension(fpath):
                continue

            content = try_read_text(fpath)
            if content is None:
                continue

            tokens = _safe_encode_count(enc, content)
            rel_path = os.path.relpath(fpath, repo_dir)
            _, ext = os.path.splitext(fname)
            ext = ext.lower() if ext else "(no extension)"

            file_results.append({"path": rel_path, "tokens": tokens})

            entry = by_extension.setdefault(ext, {"tokens": 0, "files": 0})
            entry["tokens"] += tokens
            entry["files"] += 1

    return file_results, by_extension


def build_token_result(
    instance_id: str,
    file_results: list[dict[str, Any]],
    by_extension: dict[str, dict[str, int]],
    encoding_name: str,
) -> dict[str, Any]:
    total_tokens = sum(f["tokens"] for f in file_results)
    total_files = len(file_results)

    sorted_ext = dict(
        sorted(by_extension.items(), key=lambda x: x[1]["tokens"], reverse=True)
    )

    top_files = sorted(file_results, key=lambda x: x["tokens"], reverse=True)[
        :TOP_N_FILES
    ]

    source_code_tokens = 0
    source_code_files = 0
    for ext, info in by_extension.items():
        if ext in SOURCE_CODE_EXTENSIONS:
            source_code_tokens += info["tokens"]
            source_code_files += info["files"]

    return {
        "instance_id": instance_id,
        "encoding": encoding_name,
        "total_tokens": total_tokens,
        "total_files": total_files,
        "source_code_tokens": source_code_tokens,
        "source_code_files": source_code_files,
        "by_extension": sorted_ext,
        "top_files": top_files,
    }


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
        return "1.0.0"

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
            await environment.download_dir_with_exclusions(
                source_dir=testbed_dir,
                target_dir=local_repo,
                exclude=sorted(SKIP_DIRS),
            )

            enc = tiktoken.get_encoding(self._encoding_name)
            file_results, by_extension = walk_and_count(local_repo, enc)

        elapsed = time.monotonic() - t0

        token_result = build_token_result(
            instance_id, file_results, by_extension, self._encoding_name
        )

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._write_token_counts(token_result)
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
