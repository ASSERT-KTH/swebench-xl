#!/usr/bin/env python3
"""
smoke_test.py — End-to-end pipeline validation using a known-good PR.

Validates the full chain: PR data → verify_instances → package → docker build → oracle → reward 1.

This does NOT run a Harbor agent. It applies the gold patch (solve.sh) directly
and executes test.sh to confirm reward=1. This is much faster than
``harbor run`` because it skips the agent entirely — Docker build + test
execution only, typically 10–20 minutes for Elasticsearch.

─── Workflow ───────────────────────────────────────────────────────────────────

    ┌─────────────┐     ┌──────────┐     ┌─────────┐     ┌────────────────┐
    │ PR data     │ ──► │ verify   │ ──► │ package │ ──► │ docker oracle  │
    │ (fixture)   │     │          │     │         │     │ (solve + test) │
    └─────────────┘     └──────────┘     └─────────┘     └────────────────┘

─── Usage ──────────────────────────────────────────────────────────────────────

  First time — build a fixture from a known-good PR:

    # Fetch PR from GitHub, verify, package, and save as fixture:
    python smoke_test.py --repo elastic/elasticsearch --pr 135899 \\
        --save-fixture tests/fixtures/es-135899.json --no-docker

    # Or load PR from an existing fetch_prs.py output file:
    python smoke_test.py --repo elastic/elasticsearch --pr 135899 \\
        --prs-json elastic__elasticsearch_prs.json \\
        --save-fixture tests/fixtures/es-135899.json --no-docker

  After making pipeline changes — fast iteration:

    # Fastest (~1s): only test packaging logic (no clone, no Docker):
    python smoke_test.py --fixture tests/fixtures/es-135899.json \\
        --skip-verify --no-docker

    # Medium (~10-20 min): test packaging + Docker oracle:
    python smoke_test.py --fixture tests/fixtures/es-135899.json \\
        --skip-verify

    # Full (~15-25 min): re-verify from repo clone + Docker oracle:
    python smoke_test.py --fixture tests/fixtures/es-135899.json

  Test a pre-existing Harbor task directory (already packaged):

    python smoke_test.py --task-dir ../harbor_tasks_approved/elastic__elasticsearch-135899

─── Speed comparison vs ``harbor run`` ─────────────────────────────────────────

  ``harbor run`` spins up an LLM agent to solve the task, which is the purpose
  of the benchmark but takes 10–60+ minutes.  This script applies the gold
  patch directly and just checks that test.sh produces reward=1.  Docker build
  time is identical either way — the speedup comes entirely from skipping the
  agent.

  ┌──────────────────────┬──────────────┬──────────────────────────────┐
  │ Mode                 │ Time         │ What it validates            │
  ├──────────────────────┼──────────────┼──────────────────────────────┤
  │ --skip-verify        │ ~1 second    │ packaging logic only         │
  │   --no-docker        │              │                              │
  │ --local              │ ~2-3 min     │ instance correctness (no     │
  │                      │              │ Docker, no build)            │
  │ --local --nop        │ ~2-3 min     │ empty patch → reward=0       │
  │ --skip-verify        │ ~10-20 min   │ packaging + Dockerfile +     │
  │                      │              │ test.sh + parser.py          │
  │ (full, no flags)     │ ~15-25 min   │ full pipeline end-to-end     │
  │ harbor run           │ ~30-90 min   │ agent solving ability        │
  └──────────────────────┴──────────────┴──────────────────────────────┘
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure benchmark-pipeline is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import get_adapter
from base_image import ensure_base_image
from harbor_packager import generate_harbor_task
from repo_config import get_config


# ── PR data loading ───────────────────────────────────────────────────────────


def load_pr_from_prs_json(prs_json: Path, pr_number: int) -> Dict[str, Any]:
    """Find a specific PR in a fetch_prs.py output file."""
    with open(prs_json) as f:
        all_prs = json.load(f)
    for pr in all_prs:
        if pr["pr_number"] == pr_number:
            return pr
    raise ValueError(f"PR #{pr_number} not found in {prs_json}")


def fetch_single_pr(repo: str, pr_number: int) -> Dict[str, Any]:
    """Fetch a single PR from GitHub using fetch_prs.py internals."""
    from fetch_prs import fetch_pr_details_batch, fetch_pr_files

    owner, repo_name = repo.split("/")
    details = fetch_pr_details_batch(owner, repo_name, [pr_number])
    if pr_number not in details:
        raise ValueError(f"Could not fetch PR #{pr_number} from GitHub")
    d = details[pr_number]
    patches = fetch_pr_files(owner, repo_name, pr_number)
    return {
        "repo": repo,
        "pr_number": pr_number,
        "title": d["title"],
        "description": d.get("body", ""),
        "issues": d.get("issues", []),
        "files_changed": len(patches),
        "patches": patches,
        "merged_at": d.get("merged_at", ""),
    }


# ── Pipeline steps ────────────────────────────────────────────────────────────


def step_verify(pr: Dict, repo: str, clone_dir: str) -> Dict[str, Any]:
    """Run verify_pr on a single PR.  Returns the result dict."""
    from github_api import fetch_commit_shas
    from verify_instances import verify_pr

    config = get_config(repo)

    # Ensure the clone exists — if not, clone the repo first
    if not os.path.isdir(clone_dir):
        repo_url = f"https://github.com/{repo}.git"
        print(f"  Clone dir {clone_dir} not found — cloning {repo_url} ...")
        os.makedirs(os.path.dirname(clone_dir), exist_ok=True)
        ret = subprocess.run(
            ["git", "clone", repo_url, clone_dir],
            capture_output=True,
            timeout=3600,
        )
        if ret.returncode != 0:
            return {"status": "error", "details": f"git clone failed: {ret.stderr.decode()[:500]}"}

    owner, repo_name = repo.split("/")
    sha_map = fetch_commit_shas(owner, repo_name, [pr["pr_number"]])
    if pr["pr_number"] not in sha_map:
        return {"status": "error", "details": "Could not fetch commit SHAs"}
    shas = sha_map[pr["pr_number"]]
    print(f"  base={shas['base_commit'][:10]}  merge={shas['merge_commit'][:10]}")
    return verify_pr(pr, shas, clone_dir, config)


def step_package(instance: Dict, output_dir: Path, *, use_base_image: bool = True) -> Path:
    """Package a verified instance into a Harbor task directory."""
    return generate_harbor_task(instance, output_dir, overwrite=True, use_base_image=use_base_image)


def step_docker_oracle(
    task_dir: Path,
    timeout: int = 1800,
    *,
    repo_slug: Optional[str] = None,
    use_base_image: bool = True,
    rebuild_base: bool = False,
) -> int:
    """
    Build Docker image, apply gold patch, run test.sh, return reward.

    Returns 1 on success, 0 on test failure, -1 on build failure.
    """
    env_dir = task_dir / "environment"
    instance_id = task_dir.name
    image_tag = f"smoke-{instance_id}".lower()

    # ── Ensure base image exists ──
    if use_base_image and repo_slug:
        if not ensure_base_image(repo_slug, rebuild=rebuild_base):
            print("[docker] Base image build FAILED")
            return -1

    # ── Build ──
    print(f"\n{'─' * 60}")
    print(f"[docker] Building image {image_tag}...")
    if use_base_image and repo_slug:
        print(f"[docker] Using base image (fast — checkout + cleanup only)")
    else:
        print(f"[docker] Self-contained build (git clone + dependency install)")
    build = subprocess.run(
        ["docker", "build", "-t", image_tag, "."],
        cwd=env_dir,
        timeout=3600,
    )
    if build.returncode != 0:
        print(f"[docker] Build FAILED (exit {build.returncode})")
        return -1
    print("[docker] Build OK")

    # ── Run oracle ──
    # Mount tests/ and solution/ read-only, then apply gold patch and run test.sh.
    # Create a /logs dir inside the container for test.sh's reward file.
    print(f"[docker] Running oracle: solve.sh → test.sh")
    tests_dir = str(task_dir / "tests")
    solution_dir = str(task_dir / "solution")

    run_cmd = [
        "docker", "run", "--rm",
        "-v", f"{tests_dir}:/tests:ro",
        "-v", f"{solution_dir}:/solution:ro",
        image_tag,
        "bash", "-c",
        "bash /solution/solve.sh && bash /tests/test.sh",
    ]
    result = subprocess.run(run_cmd, capture_output=True, timeout=timeout)
    stdout = result.stdout.decode(errors="replace")
    stderr = result.stderr.decode(errors="replace")
    combined = stdout + "\n" + stderr

    # ── Evaluate ──
    if "RESULT: PASSED" in combined:
        print("[docker] RESULT: PASSED — reward=1")
        return 1

    print(f"[docker] RESULT: FAILED — reward=0  (exit code {result.returncode})")
    # Print tail for debugging
    tail = combined.strip().split("\n")[-40:]
    for line in tail:
        print(f"  | {line}")
    return 0


# ── Local oracle ──────────────────────────────────────────────────────────────


def _apply_patch(patch_text: str, cwd: str) -> bool:
    """Apply a unified diff patch.  Try git apply first, fall back to patch."""
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tmp:
        tmp.write(patch_text)
        tmp_path = tmp.name

    try:
        ret = subprocess.run(
            ["git", "apply", "--verbose", tmp_path],
            cwd=cwd, capture_output=True, timeout=30,
        )
        if ret.returncode == 0:
            return True

        print(f"  git apply failed, trying patch --fuzz=5...")
        ret = subprocess.run(
            ["patch", "--fuzz=5", "-p1", "-i", tmp_path],
            cwd=cwd, capture_output=True, timeout=30,
        )
        return ret.returncode == 0
    finally:
        os.unlink(tmp_path)


def _parse_test_list(test_data):
    """Normalise a test list from JSON string or list."""
    if isinstance(test_data, str):
        try:
            return json.loads(test_data)
        except (json.JSONDecodeError, ValueError):
            return []
    elif isinstance(test_data, list):
        return test_data
    return []


def run_local_oracle(
    instance: Dict[str, Any],
    clone_dir: str,
    adapter,
    repo_cfg,
    *,
    nop: bool = False,
    timeout: int = 1800,
) -> int:
    """
    Run the oracle locally without Docker using a verified instance dict.

    Accepts the same dict returned by ``verify_pr()`` (or loaded from a
    fixture / config.json).  Resets the repo, applies patches, runs tests,
    and evaluates the result.

    When *nop* is True, skip applying the gold patch (empty solution) to
    verify that tests fail without the fix (reward should be 0).

    Returns 1 on success (all tests pass), 0 on test failure.
    """
    base_commit = instance["base_commit"]
    test_patch = instance.get("test_patch", "").strip()
    gold_patch = instance.get("patch", "").strip()
    instance_type = instance.get("instance_type", "bug_fix")
    repo_language = instance.get("repo_language", "Java")

    fail_to_pass = _parse_test_list(instance.get("fail_to_pass", []))
    pass_to_pass = _parse_test_list(instance.get("pass_to_pass", []))

    mode_label = "NOP (empty patch)" if nop else "oracle (gold patch)"
    print(f"\n{'─' * 60}")
    print(f"[local] Running {mode_label} in {clone_dir}")
    print(f"[local] base_commit={base_commit[:10]}, language={repo_language}")
    print(f"[local] fail_to_pass={len(fail_to_pass)}, pass_to_pass={len(pass_to_pass)}")

    # ── 1. Reset repo to base commit ──
    print(f"[local] Resetting repo to base commit...")
    ret = subprocess.run(
        ["git", "checkout", base_commit],
        cwd=clone_dir, capture_output=True, timeout=60,
    )
    if ret.returncode != 0:
        subprocess.run(["git", "fetch", "origin"], cwd=clone_dir, capture_output=True, timeout=300)
        ret = subprocess.run(
            ["git", "checkout", base_commit],
            cwd=clone_dir, capture_output=True, timeout=60,
        )
        if ret.returncode != 0:
            print(f"[local] Failed to checkout {base_commit}: {ret.stderr.decode()[:300]}")
            return 0

    subprocess.run(["git", "reset", "--hard", base_commit], cwd=clone_dir, capture_output=True, timeout=60)
    # Use adapter's git_clean_excludes to preserve deps (e.g. node_modules/)
    clean_cmd = ["git", "clean", "-fdx"]
    for pattern in adapter.git_clean_excludes():
        clean_cmd.extend(["-e", pattern])
    subprocess.run(clean_cmd, cwd=clone_dir, capture_output=True, timeout=120)

    # Bootstrap: install/link dependencies if the adapter requires it
    print(f"[local] Bootstrapping...")
    boot_ok, boot_output = adapter.bootstrap_repo(clone_dir, repo_cfg)
    if not boot_ok:
        print(f"[local] Bootstrap failed: {boot_output[:300]}")
        return 0

    # ── 2. Reset files touched by the test patch ──
    # An agent may have modified these files. Reset them to base-commit state
    # so the test_patch applies cleanly.
    test_files_to_reset = list(set(
        instance.get("test_files", instance.get("selected_test_files_to_run", []))
        + instance.get("test_support_files", [])
    ))
    if test_files_to_reset:
        print(f"[local] Resetting {len(test_files_to_reset)} test-patch file(s) to base commit...")
        for f in test_files_to_reset:
            ret = subprocess.run(
                ["git", "checkout", base_commit, "--", f],
                cwd=clone_dir, capture_output=True, timeout=30,
            )
            fpath = os.path.join(clone_dir, f)
            if ret.returncode == 0:
                print(f"  reset: {f}")
            elif os.path.exists(fpath):
                os.remove(fpath)
                print(f"  removed (new in patch): {f}")
            else:
                print(f"  skip (not present): {f}")

    # ── 3. Apply test patch ──
    if test_patch:
        print(f"[local] Applying test_patch...")
        ok = _apply_patch(test_patch, clone_dir)
        if not ok:
            print(f"[local] WARNING: test_patch failed to apply")

    # ── 4. Apply gold patch (unless NOP mode) ──
    if nop:
        print(f"[local] NOP mode — skipping gold patch")
    elif gold_patch:
        print(f"[local] Applying gold patch...")
        ok = _apply_patch(gold_patch, clone_dir)
        if not ok:
            print(f"[local] WARNING: gold patch failed to apply")
            return 0

    # ── 5. Purge old test results ──
    # Gradle: build/test-results/  |  Kibana/Jest: target/junit/
    for d in Path(clone_dir).rglob("test-results"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    junit_dir = Path(clone_dir) / "target" / "junit"
    if junit_dir.is_dir():
        shutil.rmtree(junit_dir, ignore_errors=True)

    # ── 6. Run test commands ──
    test_commands = instance.get("test_commands", instance.get("gradle_commands", []))
    if isinstance(test_commands, str):
        test_commands = json.loads(test_commands)

    # Build environment for test execution
    run_env = os.environ.copy()
    if repo_language == "TypeScript":
        # Kibana/Jest needs these to produce JUnit XML
        run_env["CI"] = "true"
        run_env["NODE_OPTIONS"] = "--max-old-space-size=4096"
        jest_report_dir = str(junit_dir)
        run_env["JEST_REPORT_DIR"] = jest_report_dir
        os.makedirs(jest_report_dir, exist_ok=True)

    print(f"[local] Running {len(test_commands)} test command(s)...")
    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    for i, cmd in enumerate(test_commands):
        print(f"[local] Command {i + 1}/{len(test_commands)}: {cmd[:100]}...")
        result = subprocess.run(
            ["bash", "-c", cmd],
            cwd=clone_dir,
            capture_output=True,
            timeout=timeout,
            env=run_env,
        )
        stdout_parts.append(result.stdout.decode(errors="replace"))
        stderr_parts.append(result.stderr.decode(errors="replace"))
        if result.returncode != 0:
            print(f"[local] Command {i + 1} exited with code {result.returncode}")
            # Print tail of output for debugging
            combined = stdout_parts[-1] + "\n" + stderr_parts[-1]
            tail = combined.strip().split("\n")[-30:]
            for line in tail:
                print(f"  | {line}")

    # ── 7. Parse JUnit XML results ──
    print(f"[local] Parsing test results...")

    from junitparser import JUnitXml, TestCase, TestSuite

    xml_files: List[Path] = []
    # Gradle convention: build/test-results/**/*.xml
    for test_results_dir in Path(clone_dir).rglob("test-results"):
        if test_results_dir.is_dir():
            for xf in test_results_dir.rglob("*.xml"):
                if xf.is_file():
                    xml_files.append(xf)
    # Kibana/Jest convention: target/junit/**/*.xml
    if junit_dir.is_dir():
        for xf in junit_dir.rglob("*.xml"):
            if xf.is_file():
                xml_files.append(xf)

    tests: List[Dict[str, str]] = []
    seen: set = set()
    for xml_file in xml_files:
        try:
            xml = JUnitXml.fromfile(str(xml_file))
        except Exception as e:
            print(f"[local] Warning: Failed to parse {xml_file}: {e}")
            continue

        suites: list = []
        if isinstance(xml, TestSuite):
            suites = [xml]
        else:
            for item in xml:
                if isinstance(item, TestSuite):
                    suites.append(item)

        for suite in suites:
            for case in suite:
                if not isinstance(case, TestCase):
                    continue
                classname = case.classname or ""
                name = case.name or ""
                if not classname or not name:
                    continue
                test_name = f"{classname}::{name}"
                if test_name in seen:
                    continue
                seen.add(test_name)

                if case.result is None:
                    status = "PASSED"
                else:
                    result_items = case.result if isinstance(case.result, list) else [case.result]
                    is_failure = False
                    is_skipped = False
                    for r in result_items:
                        rtype = type(r).__name__.lower()
                        if "skip" in rtype:
                            is_skipped = True
                        elif "fail" in rtype or "error" in rtype:
                            is_failure = True
                    if is_skipped:
                        status = "SKIPPED"
                    elif is_failure:
                        status = "FAILED"
                    else:
                        status = "PASSED"
                tests.append({"name": test_name, "status": status})

    print(f"[local] Found {len(xml_files)} XML file(s), {len(tests)} test(s)")

    # ── 8. Evaluate against fail_to_pass / pass_to_pass ──
    passed_tests = {t["name"] for t in tests if t["status"] == "PASSED"}
    all_output_tests = {t["name"] for t in tests}

    if not all_output_tests:
        combined = "\n".join(stdout_parts + stderr_parts)
        if "BUILD FAILED" in combined or "FAIL" in combined:
            print(f"[local] Build/tests FAILED — no test results produced")
        else:
            print(f"[local] No test results found")
        if nop:
            print(f"[local] NOP: no tests ran (build failed without fix) → reward=0 (expected)")
        return 0

    def check_test_satisfied(req, passed_set):
        if req in passed_set:
            return True
        if instance_type == "feature_addition":
            prefix = req + "["
            for passed in passed_set:
                if passed.startswith(prefix):
                    return True
        return False

    missing = [req for req in fail_to_pass if not check_test_satisfied(req, passed_tests)]
    broken = [req for req in pass_to_pass if req not in passed_tests]

    passed_count = sum(1 for t in tests if t["status"] == "PASSED")
    failed_count = sum(1 for t in tests if t["status"] == "FAILED")
    skipped_count = sum(1 for t in tests if t["status"] == "SKIPPED")
    print(f"[local] Results: {passed_count} passed, {failed_count} failed, {skipped_count} skipped")
    print(f"[local] fail_to_pass: {len(fail_to_pass)} required, "
          f"{len(fail_to_pass) - len(missing)} satisfied, {len(missing)} missing")
    print(f"[local] pass_to_pass: {len(pass_to_pass)} required, {len(broken)} broken")

    success = not missing and not broken

    if success:
        print(f"\n[local] RESULT: PASSED — reward=1")
        return 1
    else:
        print(f"\n[local] RESULT: FAILED — reward=0")
        if missing:
            print(f"  fail_to_pass not satisfied ({len(missing)}): {missing[:5]}")
        if broken:
            print(f"  pass_to_pass broken ({len(broken)}): {broken[:5]}")
        return 0


def step_local_oracle(
    task_dir: Path,
    clone_dir: str,
    *,
    nop: bool = False,
    timeout: int = 1800,
) -> int:
    """
    Thin wrapper around :func:`run_local_oracle` that reads the instance
    data from a packaged task directory's ``tests/config.json``.

    Preserves backward compatibility for ``--task-dir`` and ``--local`` modes.
    """
    config_path = task_dir / "tests" / "config.json"
    with open(config_path) as f:
        instance = json.load(f)

    repo_slug = instance.get("repo", "")
    repo_cfg = get_config(repo_slug)
    adapter = get_adapter(repo_cfg.adapter_name)

    return run_local_oracle(
        instance, clone_dir, adapter, repo_cfg,
        nop=nop, timeout=timeout,
    )


def step_validate_structure(task_dir: Path) -> bool:
    """Check that all expected files exist in the task directory."""
    expected = [
        "instruction.md",
        "task.toml",
        "environment/Dockerfile",
        "tests/config.json",
        "tests/reset_test_files.py",
        "tests/run_script.sh",
        "tests/test.sh",
        "tests/parser.py",
        "solution/solve.sh",
    ]
    ok = True
    for rel in expected:
        if not (task_dir / rel).exists():
            print(f"  MISSING: {rel}")
            ok = False
    return ok


# ── Fixture I/O ───────────────────────────────────────────────────────────────


def save_fixture(pr: Dict, result: Dict, path: Path) -> None:
    """Save a known-good PR + verified result as a reusable fixture."""
    fixture = {"pr": pr, "verified_instance": result}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)
    print(f"[fixture] Saved to {path}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline smoke test using a known-good PR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input sources (mutually exclusive-ish)
    src = parser.add_argument_group("input source (pick one)")
    src.add_argument(
        "--fixture", type=Path,
        help="Load PR + verified instance from a fixture JSON file",
    )
    src.add_argument(
        "--task-dir", type=Path,
        help="Test an already-packaged Harbor task directory (skip verify+package)",
    )
    src.add_argument(
        "--pr", type=int,
        help="PR number to test (fetched from GitHub or --prs-json)",
    )
    src.add_argument(
        "--prs-json", type=Path,
        help="Load PR data from an existing fetch_prs.py output file",
    )

    # Options
    parser.add_argument(
        "--repo", type=str, default="elastic/elasticsearch",
        help="Repository slug (default: elastic/elasticsearch)",
    )
    parser.add_argument(
        "--clone-dir", type=str, default=None,
        help="Directory for repo clone (default: from repo config)",
    )
    parser.add_argument(
        "--skip-verify", action="store_true",
        help="Skip verification step (use fixture's verified_instance directly)",
    )
    parser.add_argument(
        "--no-docker", action="store_true",
        help="Skip Docker build+run (only test verify + package)",
    )
    parser.add_argument(
        "--local", action="store_true",
        help="Run oracle locally without Docker (uses local repo clone, ~2-3 min)",
    )
    parser.add_argument(
        "--nop", action="store_true",
        help="NOP mode: skip gold patch to verify tests fail without fix (use with --local)",
    )
    parser.add_argument(
        "--no-base-image", action="store_true",
        help="Generate self-contained Dockerfiles (skip base image optimization)",
    )
    parser.add_argument(
        "--rebuild-base", action="store_true",
        help="Force rebuild of the repo base Docker image",
    )
    parser.add_argument(
        "--save-fixture", type=Path,
        help="Save the PR data + verified result as a fixture for future runs",
    )
    parser.add_argument(
        "--keep-task-dir", type=Path, default=None,
        help="Write the packaged task here instead of a temp dir (for inspection)",
    )
    args = parser.parse_args()

    # ── Mode: test an existing task directory ──
    if args.task_dir:
        task_dir = args.task_dir.resolve()
        print(f"[task-dir] Testing existing task: {task_dir.name}")
        if not step_validate_structure(task_dir):
            print("\nFAILED: task directory is incomplete")
            sys.exit(1)
        print("[task-dir] Structure OK")

        if args.local or args.nop:
            config = get_config(args.repo)
            clone_dir = args.clone_dir or config.get_clone_dir()
            if not os.path.isdir(clone_dir):
                print(f"[local] Clone dir {clone_dir} not found. "
                      f"Set --clone-dir or ${config.clone_dir_env_var}")
                sys.exit(1)
            reward = step_local_oracle(task_dir, clone_dir, nop=args.nop)
            _exit_with_reward(reward, nop=args.nop)
            return

        if args.no_docker:
            print("\nSMOKE TEST PASSED (structure only, --no-docker)")
            return

        reward = step_docker_oracle(
            task_dir,
            repo_slug=args.repo,
            use_base_image=not args.no_base_image,
            rebuild_base=args.rebuild_base,
        )
        _exit_with_reward(reward)
        return

    # ── Load PR data ──
    pr: Optional[Dict] = None
    verified: Optional[Dict] = None

    if args.fixture:
        with open(args.fixture) as f:
            fixture = json.load(f)
        pr = fixture["pr"]
        verified = fixture.get("verified_instance")
        args.repo = pr.get("repo", args.repo)
        print(f"[load] PR #{pr['pr_number']} from fixture {args.fixture.name}")
    elif args.prs_json and args.pr:
        pr = load_pr_from_prs_json(args.prs_json, args.pr)
        print(f"[load] PR #{args.pr} from {args.prs_json.name}")
    elif args.pr:
        print(f"[fetch] Fetching PR #{args.pr} from GitHub...")
        pr = fetch_single_pr(args.repo, args.pr)
        print(f"[fetch] {pr['title']}")
    else:
        parser.error("Provide --fixture, --task-dir, or --pr")

    config = get_config(args.repo)
    clone_dir = args.clone_dir or config.get_clone_dir()

    # ── Step 1: Verify ──
    print(f"\n{'=' * 60}")
    print("[step 1/3] Verify instance")
    print(f"{'=' * 60}")

    if args.skip_verify and verified and verified.get("status") == "verified":
        print(f"  Skipped (using fixture).  type={verified.get('instance_type')}")
        result = verified
    elif args.skip_verify and verified:
        print(f"  Fixture status is '{verified.get('status')}', not 'verified' — re-verifying")
        result = step_verify(pr, args.repo, clone_dir)
    else:
        result = step_verify(pr, args.repo, clone_dir)

    print(f"\n  Status: {result['status']}")
    if result["status"] != "verified":
        print(f"  Details: {result.get('details', '')}")
        print(f"\nFAILED at verification step")
        sys.exit(1)

    print(f"  Type: {result.get('instance_type')}")
    print(f"  fail_to_pass: {len(result.get('fail_to_pass', []))}")
    print(f"  pass_to_pass: {len(result.get('pass_to_pass', []))}")

    # Save fixture if requested
    if args.save_fixture:
        save_fixture(pr, result, args.save_fixture)

    # ── Step 2: Package ──
    print(f"\n{'=' * 60}")
    print("[step 2/3] Package Harbor task")
    print(f"{'=' * 60}")

    output_dir = args.keep_task_dir or Path(tempfile.mkdtemp(prefix="smoke_"))
    use_base = not args.no_base_image
    task_dir = step_package(result, output_dir, use_base_image=use_base)
    print(f"  Task dir: {task_dir}")

    if not step_validate_structure(task_dir):
        print("\nFAILED: packaged task directory is incomplete")
        sys.exit(1)
    print("  Structure OK")

    # Quick sanity checks on config.json
    cfg_data = json.loads((task_dir / "tests" / "config.json").read_text())
    assert cfg_data["instance_id"] == result["instance_id"], "instance_id mismatch"
    assert len(cfg_data.get("fail_to_pass", [])) > 0, "no fail_to_pass tests"
    print(f"  config.json OK ({len(cfg_data['fail_to_pass'])} fail_to_pass, "
          f"{len(cfg_data.get('pass_to_pass', []))} pass_to_pass)")

    # ── Step 3: Oracle ──
    if args.local or args.nop:
        print(f"\n{'=' * 60}")
        mode = "NOP verification" if args.nop else "local oracle"
        print(f"[step 3/3] Local {mode} (no Docker)")
        print(f"{'=' * 60}")

        if not os.path.isdir(clone_dir):
            print(f"[local] Clone dir {clone_dir} not found")
            sys.exit(1)

        reward = step_local_oracle(task_dir, clone_dir, nop=args.nop)
        _cleanup_temp(output_dir, args.keep_task_dir)
        _exit_with_reward(reward, nop=args.nop)
        return

    if args.no_docker:
        print(f"\n{'=' * 60}")
        print("[step 3/3] Docker oracle — SKIPPED (--no-docker)")
        print(f"{'=' * 60}")
        print("\nSMOKE TEST PASSED (verify + package)")
        _cleanup_temp(output_dir, args.keep_task_dir)
        return

    print(f"\n{'=' * 60}")
    print("[step 3/3] Docker oracle (solve.sh → test.sh)")
    print(f"{'=' * 60}")

    reward = step_docker_oracle(
        task_dir,
        repo_slug=args.repo,
        use_base_image=use_base,
        rebuild_base=args.rebuild_base,
    )
    _cleanup_temp(output_dir, args.keep_task_dir)
    _exit_with_reward(reward)


def _cleanup_temp(output_dir: Path, keep: Optional[Path]) -> None:
    """Remove temp directory if it wasn't explicitly kept."""
    if keep is None and output_dir.exists() and str(output_dir).startswith(tempfile.gettempdir()):
        shutil.rmtree(output_dir, ignore_errors=True)


def _exit_with_reward(reward: int, *, nop: bool = False) -> None:
    if nop:
        # NOP mode: reward=0 is the EXPECTED outcome
        if reward == 0:
            print(f"\n{'=' * 60}")
            print("NOP VERIFICATION PASSED — reward=0 (tests correctly fail without fix)")
            print(f"{'=' * 60}")
        else:
            print(f"\n{'=' * 60}")
            print("NOP VERIFICATION FAILED — reward=1 (tests pass WITHOUT fix!)")
            print("  This means the instance is INVALID: tests don't detect the bug.")
            print(f"{'=' * 60}")
            sys.exit(1)
    elif reward == 1:
        print(f"\n{'=' * 60}")
        print("SMOKE TEST PASSED — reward=1")
        print(f"{'=' * 60}")
    elif reward == 0:
        print(f"\n{'=' * 60}")
        print("SMOKE TEST FAILED — reward=0 (tests did not pass)")
        print(f"{'=' * 60}")
        sys.exit(1)
    else:
        print(f"\n{'=' * 60}")
        print("SMOKE TEST FAILED — Docker build failed")
        print(f"{'=' * 60}")
        sys.exit(2)


if __name__ == "__main__":
    main()