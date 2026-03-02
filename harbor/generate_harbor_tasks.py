#!/usr/bin/env python3
"""
generate_harbor_tasks.py

Converts the local dataset (benchmark/dataset.jsonl) into Harbor-compatible
task directories. Based on Harbor's SWE-bench Pro adapter, adapted for
fully local use — no HuggingFace or DockerHub required.

Each generated task uses a locally-built Docker image named:
    es-bench-instance:{instance_id}

Build your Docker images first:
    docker build -t es-bench-base harbor/dockerfiles/base_dockerfile/<any_id>/
    for id in harbor/dockerfiles/instance_dockerfile/*/; do
        instance_id=$(basename $id)
        docker build -t es-bench-instance:$instance_id $id
    done

Then run this script to generate Harbor tasks:
    python generate_harbor_tasks.py

Output structure per instance (in harbor_tasks/):
    {instance_id}/
        task.toml
        instruction.md
        environment/
            Dockerfile          <- FROM es-bench-instance:{instance_id}
        solution/
            solve.sh
        tests/
            test.sh
            run_script.sh       <- from harbor/run_scripts/
            parser.py           <- from harbor/run_scripts/
            config.json         <- full instance record
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).parent.parent  # project root (one level above harbor/)
HARBOR_DIR = Path(__file__).parent
DATASET_PATH = ROOT / "swe-bench++tools" / "high_quality_instances.jsonl"
RUN_SCRIPTS_DIR = HARBOR_DIR / "run_scripts"
TEMPLATES_DIR = ROOT / "harbor_templates"
DEFAULT_OUTPUT_DIR = ROOT / "harbor_tasks"
DOCKERFILES_BASE_DIR = HARBOR_DIR / "dockerfiles" / "base_dockerfile"
DOCKERFILES_INSTANCE_DIR = HARBOR_DIR / "dockerfiles" / "instance_dockerfile"


# ─── Dataset loading ──────────────────────────────────────────────────────────

def load_dataset(path: Path) -> dict[str, dict]:
    """Load dataset.jsonl into a dict keyed by instance_id."""
    records = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records[rec["instance_id"]] = rec
    return records


def build_problem_statement(rec: dict) -> str:
    """Merge title + description into a single problem_statement string."""
    title = rec.get("problem_statement_title", "").strip()
    description = rec.get("problem_statement_description", "").strip()
    if title and description:
        return f"## {title}\n\n{description}"
    return title or description or "(no problem statement)"


# ─── Template rendering ───────────────────────────────────────────────────────

def render(template_text: str, **replacements: str) -> str:
    """Replace {key} placeholders with values."""
    out = template_text
    for k, v in replacements.items():
        out = out.replace("{" + k + "}", v)
    return out


def read_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text()


# ─── Dockerfile construction ──────────────────────────────────────────────────

def build_combined_dockerfile(instance_id: str) -> str:
    """
    Build a self-contained environment/Dockerfile by merging:
      1. base_dockerfile  (public FROM + apt installs + git clone)
      2. instance_dockerfile (git checkout + history cleanup), skipping its FROM line
      3. Harbor additions (ENTRYPOINT, WORKDIR, ENV, uv install, /logs)

    This avoids referencing any locally-named Docker image, so Docker BuildKit
    can resolve the base image (eclipse-temurin) from a public registry without
    needing DockerHub access for the instance image.
    """
    instance_path = DOCKERFILES_INSTANCE_DIR / instance_id / "Dockerfile"

    # All base Dockerfiles are identical — fall back to any available one
    base_path = DOCKERFILES_BASE_DIR / instance_id / "Dockerfile"
    if not base_path.exists():
        candidates = list(DOCKERFILES_BASE_DIR.glob("*/Dockerfile"))
        if not candidates:
            raise FileNotFoundError(f"No base Dockerfile found anywhere in {DOCKERFILES_BASE_DIR}")
        base_path = candidates[0]

    base_content = base_path.read_text().rstrip()

    # Strip the FROM line from the instance Dockerfile — we inherit from base inline
    instance_lines = instance_path.read_text().splitlines()
    instance_content = "\n".join(
        line for line in instance_lines
        if not line.strip().upper().startswith("FROM ")
    ).strip()

    harbor_additions = (
        "\n# ── Harbor additions ──────────────────────────────────────\n"
        "# Reset entrypoint so docker-compose can run (sleep infinity)\n"
        "ENTRYPOINT []\n"
        "\n"
        "WORKDIR /app\n"
        "\n"
        "# Patches applied by the agent are loaded from /app/lib first\n"
        "ENV PYTHONPATH=/app/lib:/app\n"
        "\n"
        "RUN mkdir -p /logs\n"
        "\n"
        "# /installed-agent is where Harbor copies the agent's install.sh before startup\n"
        "RUN mkdir -p /installed-agent\n"
        "\n"
        "# Elasticsearch refuses to run as root — create a dedicated user for testing.\n"
        "# The container stays as root so Harbor can install agents via apt-get;\n"
        "# run_script.sh drops to this user with 'su elasticsearch' before invoking Gradle.\n"
        "RUN useradd -m -u 1000 elasticsearch 2>/dev/null || true\n"
        "\n"
        "# Create a separate non-root user for Gradle to run as.\n"
        "# mini-swe-agent itself stays as root (Harbor needs root for apt installs),\n"
        "# but Gradle/ES refuse to build as root — the gradlew wrapper below handles\n"
        "# the privilege drop transparently.\n"
        "RUN useradd -m -u 1001 agent 2>/dev/null || true\n"
        "RUN chown -R agent:agent /app\n"
        "\n"
        "# Replace ./gradlew with a thin wrapper that drops to the 'agent' user\n"
        "# whenever it is invoked as root.\n"
        "#\n"
        "# How it works:\n"
        "#   1. The real Gradle launcher is moved to /app/.gradlew-real (hidden).\n"
        "#      APP_BASE_NAME is patched to 'gradlew' so Gradle's own :help output\n"
        "#      always says 'run gradlew <task>' — not '.gradlew-real <task>' — which\n"
        "#      keeps the agent pointed at our wrapper rather than the raw script.\n"
        "#   2. The wrapper is installed at BOTH ./gradlew and ./gradlew.real so that\n"
        "#      it is always intercepted regardless of which name the agent uses.\n"
        "#      (Gradle's :help output says 'gradlew.real' because we renamed the\n"
        "#      original; putting the wrapper there too closes the bypass.)\n"
        "#   3. The wrapper checks 'id -u'. If root (UID 0), it first runs\n"
        "#      'chown -R agent:agent /app' to fix ownership of any files the agent\n"
        "#      wrote as root (edited source files, new directories, etc.), then\n"
        "#      re-invokes Gradle via 'su -s /bin/bash -c ... -- agent _ \"$@\"':\n"
        "#        - '-s /bin/bash'        run bash as the shell.\n"
        "#        - '-c ...'              the mini-script to execute in that shell.\n"
        "#        - '--'                  end of su's own options. su uses PERMUTE-\n"
        "#          mode option parsing, so without '--' it keeps scanning and\n"
        "#          mistakes Gradle flags like '--tests' or '-Dtests.class' for\n"
        "#          its own options, producing 'su: unrecognized option' errors.\n"
        "#        - 'agent'               the username to switch to.\n"
        "#        - '_ \"$@\"'             '_' becomes $0 (a dummy script name); the\n"
        "#          real Gradle args land in $1, $2, … so \"$@\" picks them all up.\n"
        "#          Without the dummy, the first Gradle arg would be consumed as $0\n"
        "#          and silently dropped, causing Gradle to run :help instead.\n"
        "#   4. If already non-root (e.g. test.sh has already su-d to 'elasticsearch'),\n"
        "#      the wrapper skips the su and calls .gradlew-real directly.\n"
        "RUN mv /app/gradlew /app/.gradlew-real\n"
        "RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' /app/.gradlew-real\n"
        "RUN cat > /app/gradlew << 'GRADLEW_WRAPPER_EOF'\n"
        "#!/bin/sh\n"
        "if [ \"$(id -u)\" = \"0\" ]; then\n"
        "    chown -R agent:agent /app 2>/dev/null || true\n"
        "    exec su -s /bin/bash -c 'exec /app/.gradlew-real \"$@\"' -- agent _ \"$@\"\n"
        "fi\n"
        "exec /app/.gradlew-real \"$@\"\n"
        "GRADLEW_WRAPPER_EOF\n"
        "RUN chmod +x /app/gradlew\n"
        "RUN cp /app/gradlew /app/gradlew.real\n"
        "\n"
        "# Write a mini-swe-agent config that:\n"
        "#   1. Restores the system_template from mini.yaml (lost when MSWEA_MINI_CONFIG_PATH\n"
        "#      fully replaces mini.yaml instead of merging with it).\n"
        "#   2. Raises per-command timeout to 600s (default 30s is too short for Gradle).\n"
        "#   3. Sets step_limit to 250.\n"
        "#   4. Fixes the format_error_template to explicitly require ```bash blocks.\n"
        "RUN cat > /root/mini-swe-agent-config.yaml << 'MSWEA_CONFIG_EOF'\n"
        "env:\n"
        "  timeout: 600\n"
        "agent:\n"
        "  step_limit: 250\n"
        "  system_template: |\n"
        "    You are a helpful assistant that can interact with a computer.\n"
        "\n"
        "    Your response must contain exactly ONE bash code block with ONE command (or\n"
        "    commands connected with && or ||).\n"
        "    Include a THOUGHT section before your command where you explain your reasoning\n"
        "    process.\n"
        "    Format your response as shown in <format_example>.\n"
        "\n"
        "    <format_example>\n"
        "    Your reasoning and analysis here. Explain why you want to perform the action.\n"
        "\n"
        "    ```bash\n"
        "    your_command_here\n"
        "    ```\n"
        "    </format_example>\n"
        "\n"
        "    Failure to follow these rules will cause your response to be rejected.\n"
        "  format_error_template: |\n"
        "    Please always provide EXACTLY ONE action in triple backticks, found {{actions|length}} actions.\n"
        "    If you want to end the task, please issue the following command: `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`\n"
        "    without any other command.\n"
        "    Else, please format your response exactly as follows:\n"
        "\n"
        "    <response_example>\n"
        "    Here are some thoughts about why you want to perform the action.\n"
        "\n"
        "    ```bash\n"
        "    <action>\n"
        "    ```\n"
        "    </response_example>\n"
        "\n"
        "    Note: In rare cases, if you need to reference a similar format in your command,\n"
        "    you might have to proceed in two steps, first writing TRIPLEBACKTICKSBASH, then replacing them with ```bash.\n"
        "MSWEA_CONFIG_EOF\n"
        "ENV MSWEA_MINI_CONFIG_PATH=/root/mini-swe-agent-config.yaml\n"
        "\n"
        "# Pre-warm the Gradle distribution so the agent doesn't time out downloading it.\n"
        "# Runs as root; the wrapper su-s to 'agent', so the cache lands in\n"
        "# /home/agent/.gradle — the same location used at runtime.\n"
        "RUN cd /app && ./gradlew --version --no-daemon || true\n"
    )

    return f"{base_content}\n\n# ── Instance-specific setup ──────────────────────────────────\n{instance_content}\n{harbor_additions}"


# ─── Difficulty inference ─────────────────────────────────────────────────────

def infer_difficulty(rec: dict) -> str:
    """Best-effort difficulty from dataset fields."""
    import json as _json

    fail_to_pass_raw = rec.get("fail_to_pass", "[]")
    try:
        ftp = _json.loads(fail_to_pass_raw) if isinstance(fail_to_pass_raw, str) else fail_to_pass_raw
    except Exception:
        ftp = []

    n = len(ftp)
    if n <= 2:
        return "easy"
    elif n <= 6:
        return "medium"
    else:
        return "hard"


# ─── Task generation ──────────────────────────────────────────────────────────

def generate_task(
    rec: dict,
    output_root: Path,
    run_scripts_dir: Path,
    *,
    overwrite: bool = False,
    timeout_sec: float = 3600.0,
) -> Path:
    instance_id = rec["instance_id"]
    task_dir = output_root / instance_id

    if task_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Task directory already exists: {task_dir}  (use --overwrite)")
        shutil.rmtree(task_dir)

    # Create subdirectories
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "solution").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)

    problem_statement = build_problem_statement(rec)

    # ── instruction.md ──────────────────────────────────────────────────────
    instr = render(
        read_template("instruction.md"),
        problem_statement=dedent(problem_statement).strip(),
        repo=rec.get("repo", ""),
        base_commit=rec.get("base_commit", ""),
        instance_id=instance_id,
        repo_language=rec.get("repo_language", "java"),
    )
    if not instr.endswith("\n"):
        instr += "\n"
    (task_dir / "instruction.md").write_text(instr)

    # ── task.toml ───────────────────────────────────────────────────────────
    toml = render(
        read_template("task.toml"),
        difficulty=infer_difficulty(rec),
        max_timeout=str(int(timeout_sec)),
    )
    (task_dir / "task.toml").write_text(toml)

    # ── environment/Dockerfile ───────────────────────────────────────────────
    # Combine base + instance Dockerfiles into one self-contained file so that
    # Docker BuildKit only needs the public eclipse-temurin base image.
    (task_dir / "environment" / "Dockerfile").write_text(
        build_combined_dockerfile(instance_id)
    )

    # ── solution/solve.sh ────────────────────────────────────────────────────
    patch_text = (rec.get("patch") or "").strip()
    if patch_text and not patch_text.endswith("\n"):
        patch_text += "\n"
    solve_sh = render(read_template("solve.sh"), patch=patch_text)
    solve_path = task_dir / "solution" / "solve.sh"
    solve_path.write_text(solve_sh)
    solve_path.chmod(solve_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # ── tests/test.sh ────────────────────────────────────────────────────────
    test_sh_path = task_dir / "tests" / "test.sh"
    test_sh_path.write_text(read_template("test.sh"))
    test_sh_path.chmod(test_sh_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # ── tests/config.json ────────────────────────────────────────────────────
    # Store the full record so test.sh can read fail_to_pass / pass_to_pass.
    (task_dir / "tests" / "config.json").write_text(json.dumps(rec, indent=2))

    # ── tests/run_script.sh + tests/parser.py ───────────────────────────────
    instance_scripts = run_scripts_dir / instance_id
    if not instance_scripts.exists():
        raise FileNotFoundError(
            f"run_scripts directory not found for {instance_id}\n"
            f"Expected: {instance_scripts}"
        )

    run_script_src = instance_scripts / "run_script.sh"
    parser_src = instance_scripts / "parser.py"

    for src in (run_script_src, parser_src):
        if not src.exists():
            raise FileNotFoundError(f"Missing: {src}")

    run_script_dst = task_dir / "tests" / "run_script.sh"
    shutil.copy2(run_script_src, run_script_dst)
    shutil.copy2(parser_src, task_dir / "tests" / "parser.py")
    run_script_dst.chmod(run_script_dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return task_dir


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert local dataset to Harbor-compatible task directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--dataset", type=Path, default=DATASET_PATH,
        help=f"Path to dataset.jsonl (default: {DATASET_PATH})",
    )
    ap.add_argument(
        "--run-scripts-dir", type=Path, default=RUN_SCRIPTS_DIR,
        help=f"Path to run_scripts directory (default: {RUN_SCRIPTS_DIR})",
    )
    ap.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for Harbor tasks (default: {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--instance-id", type=str, default=None,
        help="Generate a single instance only (default: all instances)",
    )
    ap.add_argument(
        "--timeout", type=float, default=3600.0,
        help="Agent/verifier timeout in seconds (default: 3600)",
    )
    ap.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing task directories",
    )
    ap.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of instances to generate (for testing)",
    )
    args = ap.parse_args()

    # Validate inputs
    if not args.dataset.exists():
        ap.error(f"Dataset not found: {args.dataset}")

    run_scripts_dir = args.run_scripts_dir
    if not run_scripts_dir.exists():
        ap.error(f"run_scripts directory not found: {run_scripts_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset from: {args.dataset}")
    records = load_dataset(args.dataset)
    print(f"  {len(records)} instances loaded.")

    # Only process instances that have a Dockerfile in harbor/
    available_in_harbor = {
        p.parent.name for p in DOCKERFILES_INSTANCE_DIR.glob("*/Dockerfile")
    }

    if args.instance_id:
        if args.instance_id not in records:
            ap.error(f"Instance not found in dataset: {args.instance_id}")
        if args.instance_id not in available_in_harbor:
            ap.error(f"Instance has no Dockerfile in harbor/: {args.instance_id}")
        ids_to_process = [args.instance_id]
    else:
        ids_to_process = sorted(records.keys() & available_in_harbor)
        skipped = len(records) - len(ids_to_process)
        if skipped:
            print(f"  Skipping {skipped} instances not present in harbor/dockerfiles/")

    if args.limit is not None:
        ids_to_process = ids_to_process[: args.limit]

    print(f"Generating {len(ids_to_process)} Harbor tasks into: {args.output_dir}\n")

    success, failures = [], []
    for i, iid in enumerate(ids_to_process, 1):
        try:
            out = generate_task(
                records[iid],
                args.output_dir,
                run_scripts_dir,
                overwrite=args.overwrite,
                timeout_sec=args.timeout,
            )
            print(f"[{i:3d}/{len(ids_to_process)}] OK   {iid}")
            success.append(out)
        except Exception as e:
            print(f"[{i:3d}/{len(ids_to_process)}] FAIL {iid}: {e}")
            failures.append((iid, str(e)))

    print(f"\nDone. Success: {len(success)}  Failures: {len(failures)}")
    if failures:
        print("\nFailed instances:")
        for iid, reason in failures:
            print(f"  - {iid}: {reason}")


if __name__ == "__main__":
    main()
