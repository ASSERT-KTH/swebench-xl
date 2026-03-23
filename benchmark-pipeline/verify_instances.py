#!/usr/bin/env python3
"""
verify_instances.py — Step 1: Verify fail-to-pass behaviour for PR candidates.

Reads PR data from pr_analysis_results_full.json, runs fail-to-pass verification,
and outputs verified_instances.json with all data needed for packaging.

Usage:
    python verify_instances.py --repo elastic/elasticsearch --limit 5
    python verify_instances.py --repo elastic/elasticsearch --resume

The output JSON can then be fed to package_instances.py to generate Harbor tasks.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

# Local modules
from adapters import get_adapter
from github_api import fetch_commit_shas
from instance_detector import detect_instance_type
from patch_builder import build_gold_patch, build_test_patch
from repo_config import RepoConfig, get_config, registered_repos

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "pr_analysis_results_full.json"
DEFAULT_OUTPUT = ROOT / "benchmark-pipeline" / "verified_instances.json"

TEST_TIMEOUT = 600  # 10 minutes per test run


# ─── Git operations ───────────────────────────────────────────────────────────

def ensure_clone(repo_url: str, clone_dir: str) -> bool:
    """Ensure a fresh clone of the repo. Removes any existing clone first. Returns True on success."""
    if os.path.isdir(clone_dir):
        print(f"  Removing existing clone at {clone_dir}")
        shutil.rmtree(clone_dir)

    print(f"  Cloning to {clone_dir} (this will take a while)...")
    os.makedirs(os.path.dirname(clone_dir), exist_ok=True)
    result = subprocess.run(
        ["git", "clone", repo_url, clone_dir],
        capture_output=True,
        timeout=3600,
    )
    if result.returncode != 0:
        print(f"  Clone failed: {result.stderr.decode()[:500]}")
        return False
    return True


def reset_repo(clone_dir: str, commit: str, exclude_patterns: Optional[List[str]] = None) -> bool:
    """Hard reset the repo to a specific commit.
    
    Args:
        exclude_patterns: paths to exclude from ``git clean`` (e.g. node_modules).
    """
    result = subprocess.run(
        ["git", "checkout", "--force", commit],
        cwd=clone_dir,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  git checkout failed: {result.stderr.decode()[:300]}")
        return False

    clean_cmd = ["git", "clean", "-fdx"]
    for pattern in (exclude_patterns or []):
        clean_cmd.extend(["-e", pattern])
    result = subprocess.run(
        clean_cmd,
        cwd=clone_dir,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  git clean failed: {result.stderr.decode()[:300]}")
        return False
    return True


def checkout_files(clone_dir: str, commit: str, files: List[str]) -> Tuple[bool, str]:
    """Checkout specific files from a commit."""
    if not files:
        return True, ""
    result = subprocess.run(
        ["git", "checkout", commit, "--"] + files,
        cwd=clone_dir,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        return False, result.stderr.decode()[:500]
    return True, ""


def extract_version(clone_dir: str, config: Optional[RepoConfig] = None) -> str:
    """Extract project version from the checked-out repo using config."""
    version_files = (
        config.version_files
        if config
        else [
            "build-tools-internal/version.properties",
            "buildSrc/version.properties",
        ]
    )
    version_key = config.version_key if config else "elasticsearch"

    if not version_key:
        return ""

    for relpath in version_files:
        candidate = os.path.join(clone_dir, relpath)
        if os.path.isfile(candidate):
            try:
                with open(candidate) as f:
                    for line in f:
                        if line.strip().startswith(version_key):
                            return line.split("=", 1)[1].strip()
            except OSError:
                pass
    return ""


# ─── Candidate filtering ─────────────────────────────────────────────────────

def _has_java_test_files(pr: Dict, adapter) -> bool:
    """Check if a PR's patches include test files for the configured language."""
    return adapter.has_test_files_in_pr(pr)


def load_candidates(
    input_file: Path,
    repo_filter: Optional[str] = None,
    config: Optional[RepoConfig] = None,
) -> List[Dict]:
    """
    Load PR data and filter to candidates.

    Works with both old-format JSON (with verifiability_audit from LLM) and
    new-format JSON (from fetch_prs.py, no LLM fields).
    """
    adapter = get_adapter(config.adapter_name) if config else get_adapter("java-gradle")

    with open(input_file, "r", encoding="utf-8") as f:
        all_prs = json.load(f)

    min_files = config.extra.get("min_files_changed", 2) if config else 2
    max_files = config.extra.get("max_files_changed", 100) if config else 100

    candidates = []
    for pr in all_prs:
        if repo_filter and pr.get("repo") != repo_filter:
            continue

        # File count filter
        files_changed = pr.get("files_changed", 0)
        if files_changed < min_files or files_changed > max_files:
            continue

        # Test presence: use LLM audit if available, otherwise detect from patches
        audit = pr.get("verifiability_audit")
        if audit:
            if not audit.get("has_tests"):
                continue
            if audit.get("test_type") != "unit":
                continue
        else:
            if not _has_java_test_files(pr, adapter):
                continue

        candidates.append(pr)

    return candidates


# ─── Results I/O ──────────────────────────────────────────────────────────────

def load_results(results_file: Path) -> Tuple[List[Dict], set]:
    """Load existing results for resume support."""
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        done = {r["pr_number"] for r in results}
        return results, done
    except (FileNotFoundError, json.JSONDecodeError):
        return [], set()


def save_results(results: List[Dict], results_file: Path) -> None:
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


# ─── Single PR verification ──────────────────────────────────────────────────

def verify_pr(
    pr: Dict,
    shas: Dict[str, str],
    clone_dir: str,
    config: Optional[RepoConfig] = None,
) -> Dict:
    """
    Run fail-to-pass verification on a single PR.

    Returns a result dict with all data needed for later packaging.
    """
    pr_number = pr["pr_number"]
    repo = pr["repo"]
    merge_commit = shas["merge_commit"]
    base_commit = shas["base_commit"]
    owner, repo_name = repo.split("/")
    instance_id = f"{owner}__{repo_name}-{pr_number}".lower()

    adapter = get_adapter(config.adapter_name) if config else get_adapter("java-gradle")

    result: dict[str, Any] = {
        "pr_number": pr_number,
        "instance_id": instance_id,
        "repo": repo,
        "title": pr["title"],
        "merge_commit": merge_commit,
        "base_commit": base_commit,
        "status": "error",
        "instance_type": "",
        "details": "",
    }

    # Classify files using the adapter
    test_files, source_files, test_support_files = adapter.classify_files(pr["patches"], config)
    lang_test_files = [
        f for f in test_files
        if any(f.endswith(ext) for ext in adapter.source_file_extensions)
    ]

    if not lang_test_files:
        result["status"] = "skipped"
        result["details"] = f"No {adapter.language_name} test files found"
        return result

    # Skip renamed files (not supported yet)
    if any(p.get("status") == "renamed" for p in pr["patches"]):
        result["status"] = "skipped"
        result["details"] = "PR contains renamed files"
        return result

    # Build test commands
    test_cmds = adapter.build_test_commands(lang_test_files, config)
    if not test_cmds:
        result["status"] = "skipped"
        result["details"] = f"Could not build {adapter.build_tool_name} test commands"
        return result

    # ── PHASE 1: Reset to base commit ──
    print(f"  [1/4] Resetting to base commit {base_commit[:10]}...")
    if not reset_repo(clone_dir, base_commit, adapter.git_clean_excludes()):
        result["details"] = "Failed to reset to base commit"
        return result

    if not adapter.check_build_tool_exists(clone_dir, config):
        result["status"] = "skipped"
        result["details"] = f"No {adapter.build_tool_name} wrapper at base commit"
        return result

    version = extract_version(clone_dir, config)
    runtime_version = adapter.detect_runtime_version(clone_dir, config)

    # Bootstrap: install dependencies if the adapter requires it
    print(f"  [1/4] Bootstrapping repo...")
    boot_ok, boot_output = adapter.bootstrap_repo(clone_dir, config)
    if not boot_ok:
        result["details"] = f"Bootstrap failed: {boot_output[:300]}"
        return result

    # ── PHASE 2: Apply test patch and detect instance type ──
    all_test_files = test_files + test_support_files
    print(f"  [2/4] Applying {len(all_test_files)} test files from {merge_commit[:10]}...")
    ok, err = checkout_files(clone_dir, merge_commit, all_test_files)
    if not ok:
        result["details"] = f"Failed to checkout test files: {err}"
        return result

    print(f"  [2/4] Detecting instance type...")
    detection = detect_instance_type(lang_test_files, clone_dir, TEST_TIMEOUT, adapter, config)

    if detection.instance_type == "invalid":
        result["status"] = "invalid_tests_pass_without_fix"
        result["details"] = detection.details
        return result

    if detection.instance_type == "error":
        result["status"] = "error"
        result["details"] = detection.details
        return result

    result["instance_type"] = detection.instance_type

    # ── PHASE 3: Apply source patch and verify tests pass ──
    print(f"  [3/4] Applying {len(source_files)} source files from {merge_commit[:10]}...")
    ok, err = checkout_files(clone_dir, merge_commit, source_files)
    if not ok:
        result["details"] = f"Failed to checkout source files: {err}"
        return result

    print(f"  [3/4] Running tests (expecting PASS)...")
    tests_passed, pass_output = adapter.run_tests(lang_test_files, clone_dir, TEST_TIMEOUT, config)

    # Parse test reports regardless of overall exit code
    report_files = adapter.find_test_reports(test_cmds, clone_dir)
    failed_in_pass, pass_to_pass = adapter.parse_test_results(report_files)

    if not tests_passed:
        result["status"] = "invalid_tests_fail_with_fix"
        result["details"] = (
            f"Tests still fail after applying source fix "
            f"({len(failed_in_pass)} failed: {failed_in_pass[:3]})"
        )
        return result

    # Cross-check: every fail_to_pass test from Phase 2 must now be passing.
    pass_set = set(pass_to_pass)
    not_confirmed: list[str] = []
    confirmed_fail_to_pass: list[str] = []
    for ftp in detection.fail_to_pass:
        if ftp in pass_set:
            confirmed_fail_to_pass.append(ftp)
        elif detection.instance_type == "feature_addition":
            prefix = ftp + "["
            expanded = [p for p in pass_set if p.startswith(prefix)]
            if expanded:
                confirmed_fail_to_pass.extend(expanded)
            else:
                not_confirmed.append(ftp)
        else:
            not_confirmed.append(ftp)

    if not_confirmed:
        result["status"] = "invalid_fail_to_pass_not_confirmed"
        result["details"] = (
            f"{len(not_confirmed)} fail_to_pass test(s) not found in passing results "
            f"after applying fix: {not_confirmed[:3]}"
        )
        return result

    print(f"  [3/4] {len(pass_to_pass)} passing, all {len(detection.fail_to_pass)} fail_to_pass confirmed")

    # Remove fail_to_pass tests from pass_to_pass — the two sets must be disjoint.
    ftp_set = set(confirmed_fail_to_pass)
    pass_to_pass = [t for t in pass_to_pass if t not in ftp_set]

    # ── PHASE 4: Build result record ──
    print(f"  [4/4] Building verified instance record...")

    # Build problem statement from issues
    issues = pr.get("issues", [])
    if len(issues) == 1:
        ps_title = issues[0].get("title", pr["title"])
        ps_desc = issues[0].get("body", pr.get("description", ""))
    elif len(issues) > 1:
        ps_title = " | ".join(iss.get("title", "") for iss in issues)
        ps_desc = "\n\n---\n\n".join(
            f"### Issue {i + 1}: {iss.get('title', '')}\n\n{iss.get('body', '')}"
            for i, iss in enumerate(issues)
        )
    else:
        ps_title = pr["title"]
        ps_desc = pr.get("description", "")

    # Build patches with proper classification
    test_patch = build_test_patch(pr["patches"], test_files, test_support_files)
    gold_patch = build_gold_patch(pr["patches"], source_files)

    result["status"] = "verified"
    result["details"] = (
        f"{detection.instance_type}: {len(confirmed_fail_to_pass)} fail_to_pass, "
        f"{len(pass_to_pass)} pass_to_pass"
    )

    # Store everything needed for packaging
    result["repo_language"] = adapter.language_name
    result["version"] = version
    result["runtime_version"] = runtime_version
    result["instance_type"] = detection.instance_type
    result["problem_statement_title"] = ps_title
    result["problem_statement_description"] = ps_desc
    result["patch"] = gold_patch
    result["test_patch"] = test_patch
    result["fail_to_pass"] = confirmed_fail_to_pass
    result["pass_to_pass"] = pass_to_pass
    result["test_commands"] = test_cmds
    result["test_files"] = lang_test_files
    result["source_files"] = source_files
    result["test_support_files"] = test_support_files
    result["missing_symbols"] = detection.missing_symbols

    return result


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify fail-to-pass behaviour for PR candidates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Output: verified_instances.json → feed to package_instances.py",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="elastic/elasticsearch",
        help="Repository slug (default: elastic/elasticsearch). "
             f"Registered: {', '.join(registered_repos())}",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input JSON file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--clone-dir",
        type=str,
        default=None,
        help="Directory for repo clone (default: from repo config or /tmp/<repo>-pipeline)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of PRs to process",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous run (skip already-processed PRs)",
    )
    args = parser.parse_args()

    # Load repo config
    repo_config = get_config(args.repo)
    adapter = get_adapter(repo_config.adapter_name)
    clone_dir = args.clone_dir or repo_config.get_clone_dir()

    print("=" * 70)
    print("  Step 1: Verify Instances")
    print(f"  Adapter: {adapter.language_name} + {adapter.build_tool_name}")
    print("=" * 70)

    # Prerequisites
    print("\n[Prerequisites]")
    if not adapter.check_prerequisites(repo_config):
        print(f"Prerequisites not met for {adapter.language_name}/{adapter.build_tool_name}.")
        sys.exit(1)

    # Load candidates
    print(f"\n[Loading data]")
    if not args.input.exists():
        print(f"Error: {args.input} not found")
        sys.exit(1)

    candidates = load_candidates(args.input, args.repo, repo_config)
    print(f"  {len(candidates)} candidates for {args.repo}")

    # Resume support
    if args.resume:
        results, already_done = load_results(args.output)
        candidates = [c for c in candidates if c["pr_number"] not in already_done]
        print(f"  {len(already_done)} already processed, {len(candidates)} remaining")
    else:
        results, already_done = [], set()

    if not candidates:
        print("\nNo candidates to process.")
        return

    if args.limit:
        candidates = candidates[: args.limit]

    # Fetch commit SHAs
    print(f"\n[Fetching commit SHAs]")
    owner, repo_name = args.repo.split("/")
    pr_numbers = [pr["pr_number"] for pr in candidates]
    sha_map = fetch_commit_shas(owner, repo_name, pr_numbers)
    print(f"  Resolved SHAs for {len(sha_map)}/{len(pr_numbers)} PRs")
    candidates = [c for c in candidates if c["pr_number"] in sha_map]

    # Ensure clone
    print(f"\n[Repository setup]")
    repo_url = f"https://github.com/{args.repo}.git"
    if not ensure_clone(repo_url, clone_dir):
        print("Failed to clone/update repo. Exiting.")
        sys.exit(1)

    # Process each PR
    stats: dict[str, int] = {}
    print(f"\n[Processing {len(candidates)} PRs]")

    for i, pr in enumerate(candidates):
        pr_number = pr["pr_number"]
        shas = sha_map[pr_number]

        print(f"\n{'─' * 60}")
        print(f"[{i + 1}/{len(candidates)}] PR #{pr_number}: {pr['title'][:55]}")
        print(f"  base={shas['base_commit'][:10]} merge={shas['merge_commit'][:10]}")

        try:
            result = verify_pr(pr, shas, clone_dir, repo_config)
        except Exception as e:
            result = {
                "pr_number": pr_number,
                "instance_id": f"{owner}__{repo_name}-{pr_number}",
                "repo": args.repo,
                "title": pr["title"],
                "merge_commit": shas["merge_commit"],
                "base_commit": shas["base_commit"],
                "status": "error",
                "instance_type": "",
                "details": f"Exception: {str(e)[:500]}",
            }

        status = result["status"]
        stats[status] = stats.get(status, 0) + 1
        print(f"  → {status}: {result.get('details', '')[:80]}")

        results.append(result)
        save_results(results, args.output)

    # Summary
    verified = [r for r in results if r["status"] == "verified"]
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")
    print(f"  Total processed: {sum(stats.values())}")
    print(f"\n  Verified instances: {len(verified)}")
    print(f"  Results saved to: {args.output}")
    print(f"\n  Next step: python package_instances.py --input {args.output}")


if __name__ == "__main__":
    main()
