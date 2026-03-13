"""
Harbor task directory generation.

Produces complete harbor task directories ready for evaluation:
    {instance_id}/
        task.toml
        instruction.md
        environment/
            Dockerfile
            mini-swe-agent-config.yaml
        solution/
            solve.sh
        tests/
            test.sh
            config.json
            run_script.sh
            parser.py
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "harbor_templates"

# Per-repo configuration for Dockerfile generation
REPO_CONFIG: dict[str, dict[str, Any]] = {
    "elastic/elasticsearch": {
        "base_image": "eclipse-temurin:21-jdk-jammy",
        "system_packages": "git python3 python3-pip curl wget unzip jq",
        "build_tool": "gradle",
        "no_root_user": "elasticsearch",
        "version_file": "build-tools-internal/version.properties",
        "java_version_file": ".java-version",
    },
}


def _read_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text()


def _render(template: str, **kw: str) -> str:
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", v)
    return out


def _infer_difficulty(fail_to_pass: list) -> str:
    n = len(fail_to_pass)
    if n <= 2:
        return "easy"
    elif n <= 6:
        return "medium"
    return "hard"


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# Dockerfile generation
# ---------------------------------------------------------------------------

def _generate_dockerfile(
    repo_url: str,
    base_commit: str,
    repo_slug: str,
    instance_id: str,
    *,
    gradlew_wrapper: bool = True,
    jdk_version: Optional[str] = None,
) -> str:
    """Generate a self-contained Dockerfile for an instance."""
    cfg = REPO_CONFIG.get(repo_slug, REPO_CONFIG["elastic/elasticsearch"])
    base_image = cfg["base_image"]

    # Allow JDK version override (e.g. from .java-version at the base commit)
    if jdk_version:
        base_image = f"eclipse-temurin:{jdk_version}-jdk-jammy"

    packages = cfg["system_packages"]

    lines = [
        f"# Auto-generated Dockerfile for {instance_id}",
        f"FROM {base_image}",
        "",
        "ENV DEBIAN_FRONTEND=noninteractive",
        "",
        "# System dependencies",
        f"RUN apt-get update && apt-get install -y --no-install-recommends \\",
        f"    {packages} \\",
        "    && rm -rf /var/lib/apt/lists/*",
        "",
        "# Install junitparser for test result parsing inside the container",
        "RUN pip3 install --no-cache-dir junitparser",
        "",
        "# Clone repository",
        f"RUN mkdir /app && \\",
        f"    git clone -o origin --single-branch {repo_url} /app",
        "",
        "WORKDIR /app",
        "SHELL [\"/bin/bash\", \"-c\"]",
        "",
        f"# Reset to base commit (before the fix)",
        f"RUN git checkout {base_commit} && \\",
        f"    git reset --hard {base_commit} && \\",
        f"    git clean -fdx",
        "",
        "# === Git History Cleanup ===",
        "# Prevents agents from seeing future commits/tags.",
        f"RUN git remote remove origin && \\",
        f"    git branch -a | grep -v '\\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \\",
        f"    BASE_TIMESTAMP=$(git show -s --format=%ci {base_commit}) && \\",
        f"    git tag -l | while read tag; do \\",
        f"        TAG_COMMIT=$(git rev-list -n 1 \"$tag\" 2>/dev/null) || continue; \\",
        f"        TAG_TIME=$(git show -s --format=%ci \"$TAG_COMMIT\" 2>/dev/null) || continue; \\",
        f"        if [[ \"$TAG_TIME\" > \"$BASE_TIMESTAMP\" ]]; then \\",
        f"            git tag -d \"$tag\" > /dev/null 2>&1; \\",
        f"        fi; \\",
        f"    done && \\",
        f"    git reflog expire --expire=now --all && \\",
        f"    git gc --prune=now",
        "",
        "# Verify no future commits accessible",
        f"RUN FUTURE_COMMITS=$(git log --oneline --all "
        f"--after=\"$(git show -s --format=%ci {base_commit})\" "
        f"--not {base_commit} 2>/dev/null | wc -l | tr -d ' ') && \\",
        f"    if [ \"$FUTURE_COMMITS\" -gt 0 ]; then \\",
        f"        echo \"ERROR: $FUTURE_COMMITS future commits still accessible!\" && exit 1; \\",
        f"    fi",
        "",
        f"# Verify HEAD at correct commit",
        f"RUN CURRENT=$(git rev-parse HEAD) && \\",
        f"    if [ \"$CURRENT\" != \"{base_commit}\" ]; then \\",
        f"        echo \"ERROR: HEAD is $CURRENT, expected {base_commit}\" && exit 1; \\",
        f"    fi",
        "",
        "# ── Harbor additions ──────────────────────────────────────",
        "ENTRYPOINT []",
        "WORKDIR /app",
        "ENV PYTHONPATH=/app/lib:/app",
        "# Cap Gradle JVM heap and parallelism for memory-constrained hosts",
        'ENV GRADLE_OPTS="-Xmx2g"',
        "RUN mkdir -p /logs",
        "RUN mkdir -p /installed-agent",
        "",
    ]

    # Create non-root users
    no_root_user = cfg.get("no_root_user", "elasticsearch")
    lines.append(f"RUN useradd -m -u 1000 {no_root_user} 2>/dev/null || true")

    if gradlew_wrapper:
        lines.extend([
            "",
            "# Gradlew wrapper: auto-drops to non-root user when invoked as root",
            "RUN useradd -m -u 1001 agent 2>/dev/null || true",
            "RUN chown -R agent:agent /app",
            "",
            "RUN mv /app/gradlew /app/.gradlew-bin",
            "RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' /app/.gradlew-bin",
            "RUN cat > /app/gradlew << 'GRADLEW_WRAPPER_EOF'",
            "#!/bin/sh",
            'if [ "$(id -u)" = "0" ]; then',
            '    chown -R agent:agent /app 2>/dev/null || true',
            '    exec su -s /bin/bash -c \'exec /app/.gradlew-bin "$@"\' -- agent _ "$@"',
            "fi",
            'exec /app/.gradlew-bin "$@"',
            "GRADLEW_WRAPPER_EOF",
            "RUN chmod +x /app/gradlew",
            "RUN cp /app/gradlew /app/gradlew.real",
            "RUN cp /app/gradlew /app/.gradlew-real",
            "",
        ])

    lines.extend([
        "# Agent config",
        "COPY mini-swe-agent-config.yaml /root/mini-swe-agent-config.yaml",
        "ENV MSWEA_MINI_CONFIG_PATH=/root/mini-swe-agent-config.yaml",
        "",
        "# Pre-warm Gradle distribution",
        "RUN cd /app && ./gradlew --version --no-daemon || true",
    ])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Run script generation
# ---------------------------------------------------------------------------

def _generate_run_script(instance_id: str, gradle_commands: List[str]) -> str:
    """Generate run_script.sh from gradle commands."""
    commands_block = ""
    for i, cmd in enumerate(gradle_commands):
        if "--no-configuration-cache" not in cmd:
            cmd = cmd + " --no-configuration-cache"
        if "--max-workers" not in cmd:
            cmd = cmd + " --max-workers=2"
        commands_block += f"""
echo "=== Running gradle command {i + 1}/{len(gradle_commands)} ==="
{cmd}
CMD_EXIT=$?
if [ $CMD_EXIT -ne 0 ]; then
    echo "Gradle command {i + 1} failed with exit code $CMD_EXIT"
    OVERALL_EXIT=1
fi
"""

    return f"""#!/bin/bash
set -uo pipefail

# Run script for {instance_id}
# Auto-generated by the benchmark pipeline
#
# NOTE: set -e is intentionally NOT used. All gradle commands must run so that
# JUnit XML is produced for every module, even if an earlier module fails.

cd /app
OVERALL_EXIT=0

if [ $# -gt 0 ]; then
    TEST_FILES="$@"
    echo "Running with custom test files: $TEST_FILES"
    for tf in $(echo "$TEST_FILES" | tr ',' ' '); do
        ./gradlew test --tests "$tf" --no-daemon --stacktrace -x javadoc --no-configuration-cache --max-workers=2
        CMD_EXIT=$?
        if [ $CMD_EXIT -ne 0 ]; then
            OVERALL_EXIT=1
        fi
    done
else
    echo "Running pre-configured gradle commands..."
{commands_block}
fi

echo "=== Test execution complete ==="
exit $OVERALL_EXIT
"""


# ---------------------------------------------------------------------------
# Main task generation
# ---------------------------------------------------------------------------

def generate_harbor_task(
    instance: Dict[str, Any],
    output_dir: Path,
    *,
    overwrite: bool = False,
    timeout_sec: int = 3600,
    gradlew_wrapper: bool = True,
    jdk_version: Optional[str] = None,
) -> Path:
    """
    Generate a complete Harbor task directory for a verified instance.

    instance dict must contain:
        instance_id, repo, base_commit, merge_commit, patch, test_patch,
        fail_to_pass, pass_to_pass, gradle_commands, test_files, source_files,
        version, problem_statement_title, problem_statement_description,
        instance_type, missing_methods (optional)
    """
    instance_id = instance["instance_id"]
    task_dir = output_dir / instance_id

    if task_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Task directory already exists: {task_dir}")
        shutil.rmtree(task_dir)

    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "solution").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)

    repo = instance.get("repo", "elastic/elasticsearch")
    repo_url = f"https://github.com/{repo}.git"
    repo_slug = repo
    base_commit = instance["base_commit"]

    # ── instruction.md ──────────────────────────────────────────────
    problem_title = instance.get("problem_statement_title", instance.get("title", ""))
    problem_desc = instance.get("problem_statement_description", instance.get("description", ""))
    problem_statement = f"## {problem_title}\n\n{problem_desc}" if problem_title else problem_desc

    # For feature additions, append method signatures
    instance_type = instance.get("instance_type", "bug_fix")
    if instance_type == "feature_addition":
        missing = instance.get("missing_methods", [])
        if missing:
            hint_lines = ["\n\n---\n\n## Hint: Method Signatures to Implement\n"]
            hint_lines.append("The following methods need to be created as part of this task:\n")
            for m in missing:
                cls = m.get("class", "Unknown")
                method = m.get("method", "unknown")
                params = m.get("params", "")
                hint_lines.append(f"- `{method}({params})` in `{cls}`")
            problem_statement += "\n".join(hint_lines)

    instr = _render(
        _read_template("instruction.md"),
        problem_statement=dedent(problem_statement).strip(),
        repo=repo,
        base_commit=base_commit,
        instance_id=instance_id,
        repo_language=instance.get("repo_language", "Java"),
    )
    if not instr.endswith("\n"):
        instr += "\n"
    (task_dir / "instruction.md").write_text(instr)

    # ── task.toml ───────────────────────────────────────────────────
    fail_to_pass = instance.get("fail_to_pass", instance.get("FAIL_TO_PASS", []))
    if isinstance(fail_to_pass, str):
        fail_to_pass = json.loads(fail_to_pass)

    toml = _render(
        _read_template("task.toml"),
        difficulty=_infer_difficulty(fail_to_pass),
        max_timeout=str(timeout_sec),
    )
    (task_dir / "task.toml").write_text(toml)

    # ── environment/Dockerfile ──────────────────────────────────────
    dockerfile = _generate_dockerfile(
        repo_url, base_commit, repo_slug, instance_id,
        gradlew_wrapper=gradlew_wrapper,
        jdk_version=jdk_version,
    )
    (task_dir / "environment" / "Dockerfile").write_text(dockerfile)

    # ── environment/mini-swe-agent-config.yaml ──────────────────────
    shutil.copy2(
        TEMPLATES_DIR / "mini-swe-agent-config.yaml",
        task_dir / "environment" / "mini-swe-agent-config.yaml",
    )

    # ── solution/solve.sh ───────────────────────────────────────────
    patch_text = (instance.get("patch", "") or "").strip()
    if patch_text and not patch_text.endswith("\n"):
        patch_text += "\n"
    solve_sh = _render(_read_template("solve.sh"), patch=patch_text)
    solve_path = task_dir / "solution" / "solve.sh"
    solve_path.write_text(solve_sh)
    _make_executable(solve_path)

    # ── tests/test.sh ───────────────────────────────────────────────
    test_sh_path = task_dir / "tests" / "test.sh"
    test_sh_path.write_text(_read_template("test.sh"))
    _make_executable(test_sh_path)

    # ── tests/config.json ───────────────────────────────────────────
    # Store the full record so test.sh can read fail_to_pass / pass_to_pass
    config_data = {
        "instance_id": instance_id,
        "repo": repo,
        "repo_language": instance.get("repo_language", "Java"),
        "base_commit": base_commit,
        "merge_commit": instance.get("merge_commit", ""),
        "version": instance.get("version", ""),
        "pr_number": instance.get("pr_number", 0),
        "instance_type": instance_type,
        "problem_statement_title": problem_title,
        "problem_statement_description": problem_desc,
        "patch": instance.get("patch", ""),
        "test_patch": instance.get("test_patch", ""),
        "fail_to_pass": fail_to_pass,
        "pass_to_pass": instance.get("pass_to_pass", instance.get("PASS_TO_PASS", [])),
        "gradle_commands": instance.get("gradle_commands", []),
        "selected_test_files_to_run": instance.get("test_files", []),
        "source_files": instance.get("source_files", []),
    }
    # Ensure lists are actual lists (not JSON strings)
    for key in ("pass_to_pass", "gradle_commands", "selected_test_files_to_run", "source_files"):
        val = config_data[key]
        if isinstance(val, str):
            try:
                config_data[key] = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                pass

    (task_dir / "tests" / "config.json").write_text(json.dumps(config_data, indent=2))

    # ── tests/run_script.sh ─────────────────────────────────────────
    gradle_cmds = config_data["gradle_commands"]
    if isinstance(gradle_cmds, str):
        gradle_cmds = json.loads(gradle_cmds)
    run_script = _generate_run_script(instance_id, gradle_cmds)
    run_script_path = task_dir / "tests" / "run_script.sh"
    run_script_path.write_text(run_script)
    _make_executable(run_script_path)

    # ── tests/parser.py ─────────────────────────────────────────────
    # Copy from harbor_templates or an existing task
    parser_src = TEMPLATES_DIR / "parser.py"
    if not parser_src.exists():
        # Fall back to any existing task's parser
        existing_parsers = list((ROOT / "harbor_tasks").glob("*/tests/parser.py"))
        if existing_parsers:
            parser_src = existing_parsers[0]
    if parser_src.exists():
        shutil.copy2(parser_src, task_dir / "tests" / "parser.py")
    else:
        print(f"  WARNING: No parser.py template found for {instance_id}")

    return task_dir
