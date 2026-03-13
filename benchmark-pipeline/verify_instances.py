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
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

# Local modules
from file_classifier import classify_files
from github_api import fetch_commit_shas
from gradle_runner import (
    build_test_commands,
    extract_test_fqn,
    run_tests,
)
from instance_detector import detect_instance_type
from patch_builder import build_gold_patch, build_test_patch
from test_parser import find_report_xmls, parse_results

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "pr_analysis_results_full.json"
DEFAULT_OUTPUT = ROOT / "benchmark-pipeline" / "verified_instances.json"
DEFAULT_CLONE_DIR = os.environ.get("ES_CLONE_DIR", "/tmp/elasticsearch-pipeline")

TEST_TIMEOUT = 600  # 10 minutes per test run


# ─── Git operations ───────────────────────────────────────────────────────────

def ensure_clone(repo_url: str, clone_dir: str) -> bool:
    """Ensure the repo is cloned. Returns True on success."""
    if os.path.isdir(os.path.join(clone_dir, ".git")):
        print(f"  Using existing clone at {clone_dir}")
        result = subprocess.run(
            ["git", "fetch", "--all"],
            cwd=clone_dir,
            capture_output=True,
            timeout=300,
        )
        return result.returncode == 0

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


def reset_repo(clone_dir: str, commit: str) -> bool:
    """Hard reset the repo to a specific commit."""
    result = subprocess.run(
        ["git", "checkout", "--force", commit],
        cwd=clone_dir,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  git checkout failed: {result.stderr.decode()[:300]}")
        return False

    result = subprocess.run(
        ["git", "clean", "-fdx"],
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


def extract_version(clone_dir: str) -> str:
    """Extract project version from the checked-out repo."""
    for candidate in [
        os.path.join(clone_dir, "build-tools-internal", "version.properties"),
        os.path.join(clone_dir, "buildSrc", "version.properties"),
    ]:
        if os.path.isfile(candidate):
            try:
                with open(candidate) as f:
                    for line in f:
                        if line.strip().startswith("elasticsearch"):
                            return line.split("=", 1)[1].strip()
            except OSError:
                pass
    return ""


def detect_jdk_version(clone_dir: str) -> Optional[str]:
    """Try to detect required JDK version from the repo."""
    java_version_file = os.path.join(clone_dir, ".java-version")
    if os.path.isfile(java_version_file):
        try:
            with open(java_version_file) as f:
                version = f.read().strip()
            if version:
                return version
        except OSError:
            pass
    return None


def check_jdk() -> bool:
    """Check that JDK 21+ is available."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            timeout=10,
        )
        version_output = result.stderr.decode() + result.stdout.decode()
        print(f"  Java: {version_output.strip().split(chr(10))[0]}")
        for token in version_output.split():
            token = token.strip('"')
            if token[0:1].isdigit():
                major = int(token.split(".")[0])
                if major >= 21:
                    return True
                print(f"  ERROR: JDK 21+ required, found JDK {major}")
                return False
    except Exception as e:
        print(f"  ERROR: Could not determine Java version: {e}")
    return False


# ─── Candidate filtering ─────────────────────────────────────────────────────

def load_candidates(
    input_file: Path, repo_filter: Optional[str] = None
) -> List[Dict]:
    """Load PR data and filter to candidates."""
    with open(input_file, "r", encoding="utf-8") as f:
        all_prs = json.load(f)

    candidates = []
    for pr in all_prs:
        if repo_filter and pr.get("repo") != repo_filter:
            continue
        if not pr.get("verifiability_audit", {}).get("has_tests"):
            continue
        if pr.get("verifiability_audit", {}).get("test_type") != "unit":
            continue
        if pr.get("files_changed", 0) < 4 or pr.get("files_changed", 0) > 100:
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
    instance_id = f"{owner}__{repo_name}-{pr_number}"

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

    # Classify files
    test_files, source_files, test_support_files = classify_files(pr["patches"])
    java_test_files = [f for f in test_files if f.endswith(".java")]

    if not java_test_files:
        result["status"] = "skipped"
        result["details"] = "No Java test files found"
        return result

    # Skip renamed files (not supported yet)
    if any(p.get("status") == "renamed" for p in pr["patches"]):
        result["status"] = "skipped"
        result["details"] = "PR contains renamed files"
        return result

    # Build gradle commands
    gradle_cmds = build_test_commands(java_test_files)
    if not gradle_cmds:
        result["status"] = "skipped"
        result["details"] = "Could not build Gradle test commands"
        return result

    # ── PHASE 1: Reset to base commit ──
    print(f"  [1/4] Resetting to base commit {base_commit[:10]}...")
    if not reset_repo(clone_dir, base_commit):
        result["details"] = "Failed to reset to base commit"
        return result

    if not os.path.isfile(os.path.join(clone_dir, "gradlew")):
        result["status"] = "skipped"
        result["details"] = "No gradlew at base commit"
        return result

    version = extract_version(clone_dir)
    jdk_version = detect_jdk_version(clone_dir)

    # ── PHASE 2: Apply test patch and detect instance type ──
    all_test_files = test_files + test_support_files
    print(f"  [2/4] Applying {len(all_test_files)} test files from {merge_commit[:10]}...")
    ok, err = checkout_files(clone_dir, merge_commit, all_test_files)
    if not ok:
        result["details"] = f"Failed to checkout test files: {err}"
        return result

    print(f"  [2/4] Detecting instance type...")
    detection = detect_instance_type(java_test_files, clone_dir, TEST_TIMEOUT)

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
    tests_passed, pass_output = run_tests(java_test_files, clone_dir, TEST_TIMEOUT)

    # Parse JUnit XML regardless of overall exit code — we need method-level
    # results to cross-check fail_to_pass and collect pass_to_pass.
    xml_files = find_report_xmls(gradle_cmds, clone_dir)
    failed_in_pass, pass_to_pass = parse_results(xml_files)

    if not tests_passed:
        result["status"] = "invalid_tests_fail_with_fix"
        result["details"] = (
            f"Tests still fail after applying source fix "
            f"({len(failed_in_pass)} failed: {failed_in_pass[:3]})"
        )
        return result

    # Cross-check: every fail_to_pass test from Phase 2 must now be passing.
    # This catches cases where the overall run passes but a specific fail_to_pass
    # test was skipped or never ran.
    # For feature additions, also expand base IDs to actual JUnit IDs (e.g.
    # ClassName::method -> ClassName::method[0], ClassName::method[1]).
    pass_set = set(pass_to_pass)
    not_confirmed: list[str] = []
    confirmed_fail_to_pass: list[str] = []
    for ftp in detection.fail_to_pass:
        if ftp in pass_set:
            confirmed_fail_to_pass.append(ftp)
        elif detection.instance_type == "feature_addition":
            # Expand to actual JUnit IDs (handles parameterized tests)
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
    result["repo_language"] = "Java"
    result["version"] = version
    result["jdk_version"] = jdk_version
    result["instance_type"] = detection.instance_type
    result["problem_statement_title"] = ps_title
    result["problem_statement_description"] = ps_desc
    result["patch"] = gold_patch
    result["test_patch"] = test_patch
    result["fail_to_pass"] = confirmed_fail_to_pass
    result["pass_to_pass"] = pass_to_pass
    result["gradle_commands"] = gradle_cmds
    result["test_files"] = java_test_files
    result["source_files"] = source_files
    result["test_support_files"] = test_support_files
    result["missing_methods"] = detection.missing_methods

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
        help="Repository to filter PRs (default: elastic/elasticsearch)",
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
        default=DEFAULT_CLONE_DIR,
        help=f"Directory for repo clone (default: {DEFAULT_CLONE_DIR})",
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

    print("=" * 70)
    print("  Step 1: Verify Instances")
    print("=" * 70)

    # Prerequisites
    print("\n[Prerequisites]")
    if not check_jdk():
        print("JDK 21+ is required. Set JAVA_HOME or install JDK 21.")
        sys.exit(1)

    # Load candidates
    print(f"\n[Loading data]")
    if not args.input.exists():
        print(f"Error: {args.input} not found")
        sys.exit(1)

    candidates = load_candidates(args.input, args.repo)
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
    if not ensure_clone(repo_url, args.clone_dir):
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
            result = verify_pr(pr, shas, args.clone_dir)
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
