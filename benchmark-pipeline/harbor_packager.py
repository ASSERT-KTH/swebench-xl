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

# Import repo config and adapter
from adapters import get_adapter
from repo_config import RepoConfig, get_config


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
    runtime_version: Optional[str] = None,
) -> str:
    """Generate a self-contained Dockerfile for an instance using the adapter."""
    cfg = get_config(repo_slug)
    adapter = get_adapter(cfg.adapter_name)

    lines = adapter.generate_dockerfile_lines(
        cfg, repo_url, base_commit, instance_id,
        runtime_version=runtime_version,
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Run script generation
# ---------------------------------------------------------------------------

def _generate_run_script(instance_id: str, commands: List[str], repo_slug: str) -> str:
    """Generate run_script.sh using the adapter."""
    cfg = get_config(repo_slug)
    adapter = get_adapter(cfg.adapter_name)
    return adapter.generate_run_script(instance_id, commands, cfg)


# ---------------------------------------------------------------------------
# Main task generation
# ---------------------------------------------------------------------------

def generate_harbor_task(
    instance: Dict[str, Any],
    output_dir: Path,
    *,
    overwrite: bool = False,
    timeout_sec: int = 3600,
    runtime_version: Optional[str] = None,
) -> Path:
    """
    Generate a complete Harbor task directory for a verified instance.

    instance dict must contain:
        instance_id, repo, base_commit, merge_commit, patch, test_patch,
        fail_to_pass, pass_to_pass, test_commands, test_files, source_files,
        version, problem_statement_title, problem_statement_description,
        instance_type, missing_symbols (optional)
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
    cfg = get_config(repo_slug)
    adapter = get_adapter(cfg.adapter_name)

    # ── instruction.md ──────────────────────────────────────────────
    problem_title = instance.get("problem_statement_title", instance.get("title", ""))
    problem_desc = instance.get("problem_statement_description", instance.get("description", ""))
    problem_statement = f"## {problem_title}\n\n{problem_desc}" if problem_title else problem_desc

    # For feature additions, append symbol hints
    instance_type = instance.get("instance_type", "bug_fix")
    if instance_type == "feature_addition":
        missing = instance.get("missing_symbols", instance.get("missing_methods", []))
        if missing:
            problem_statement += "\n" + adapter.format_symbol_hints(missing)

    instr = _render(
        _read_template("instruction.md"),
        problem_statement=dedent(problem_statement).strip(),
        repo=repo,
        base_commit=base_commit,
        instance_id=instance_id,
        repo_language=instance.get("repo_language", adapter.language_name),
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
        runtime_version=runtime_version,
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
    test_sh = _render(_read_template("test.sh"), no_root_user=cfg.no_root_user)
    test_sh_path = task_dir / "tests" / "test.sh"
    test_sh_path.write_text(test_sh)
    _make_executable(test_sh_path)

    # ── tests/config.json ───────────────────────────────────────────
    test_cmds = instance.get("test_commands", instance.get("gradle_commands", []))
    config_data = {
        "instance_id": instance_id,
        "repo": repo,
        "repo_language": instance.get("repo_language", adapter.language_name),
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
        "test_commands": test_cmds,
        "selected_test_files_to_run": instance.get("test_files", []),
        "source_files": instance.get("source_files", []),
    }
    # Ensure lists are actual lists (not JSON strings)
    for key in ("pass_to_pass", "test_commands", "selected_test_files_to_run", "source_files"):
        val = config_data[key]
        if isinstance(val, str):
            try:
                config_data[key] = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                pass

    (task_dir / "tests" / "config.json").write_text(json.dumps(config_data, indent=2))

    # ── tests/run_script.sh ─────────────────────────────────────────
    cmds = config_data["test_commands"]
    if isinstance(cmds, str):
        cmds = json.loads(cmds)
    run_script = _generate_run_script(instance_id, cmds, repo_slug)
    run_script_path = task_dir / "tests" / "run_script.sh"
    run_script_path.write_text(run_script)
    _make_executable(run_script_path)

    # ── tests/parser.py ─────────────────────────────────────────────
    # Use adapter-provided parser if available, otherwise fall back to template
    custom_parser = adapter.generate_test_parser_script()
    if custom_parser:
        (task_dir / "tests" / "parser.py").write_text(custom_parser)
    else:
        parser_src = TEMPLATES_DIR / "parser.py"
        if not parser_src.exists():
            existing_parsers = list((ROOT / "harbor_tasks").glob("*/tests/parser.py"))
            if existing_parsers:
                parser_src = existing_parsers[0]
        if parser_src.exists():
            shutil.copy2(parser_src, task_dir / "tests" / "parser.py")
        else:
            print(f"  WARNING: No parser.py template found for {instance_id}")

    return task_dir
