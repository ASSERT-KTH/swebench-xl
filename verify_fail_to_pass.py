"""
Fail-to-Pass Verification for SWE-Bench Candidates

Validates that elasticsearch PRs with unit tests can serve as SWE-Bench-style
benchmark instances. For each PR:
  1. Checkout the repo at the base commit (before the PR)
  2. Apply only the test changes -> tests should FAIL
  3. Apply the source fix -> tests should PASS

A PR that passes both checks is a valid "fail-to-pass" candidate.
"""

import os
import sys
import json
import re
import time
import subprocess
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

INPUT_FILE = "pr_analysis_results_full.json"
OUTPUT_FILE = "fail_to_pass_results.json"
CLONE_DIR = os.environ.get("ES_CLONE_DIR", "/tmp/elasticsearch-ftpcheck")
REPO_URL = "https://github.com/elastic/elasticsearch.git"

# API
MAX_RETRIES = 3
MIN_DELAY_BETWEEN_REQUESTS = 0.5
RATE_LIMIT_BUFFER = 100
GRAPHQL_BATCH_SIZE = 20

# Test execution
TEST_TIMEOUT = 600  # 10 minutes per test run
GRADLE_FLAGS = ["--no-daemon", "--stacktrace", "-x", "javadoc"]

# ============================================================================
# GITHUB API (reused patterns from fetch_prs.py)
# ============================================================================

def get_github_headers():
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

def handle_rate_limit(response):
    remaining = int(response.headers.get('X-RateLimit-Remaining', 1000))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    if remaining <= RATE_LIMIT_BUFFER:
        wait_time = max(0, reset_time - time.time()) + 5
        if wait_time > 0:
            print(f"  [Rate limit] {remaining} remaining. Waiting {wait_time:.0f}s...")
            time.sleep(wait_time)
    else:
        time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

def github_graphql(query: str, variables: dict) -> requests.Response:
    headers = {"Authorization": f"bearer {GITHUB_TOKEN}"}

    for attempt in range(MAX_RETRIES):
        response = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={"query": query, "variables": variables}
        )

        if response.status_code == 200:
            handle_rate_limit(response)
            return response

        if response.status_code in (403, 429):
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_time = max(0, reset_time - time.time()) + 5
            if 0 < wait_time < 3700:
                print(f"  [GraphQL rate limited] Waiting {wait_time:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait_time)
                continue

        if response.status_code >= 500:
            wait = 2 ** attempt * 10
            print(f"  [GraphQL error {response.status_code}] Retrying in {wait}s...")
            time.sleep(wait)
            continue

        break

    return response

# ============================================================================
# SHA FETCHING
# ============================================================================

def fetch_commit_shas_batch(pr_numbers: List[int]) -> Dict[int, dict]:
    """
    Batch-fetch mergeCommit OID + parent for multiple PRs via GraphQL.
    Returns {pr_number: {"merge_commit": ..., "base_commit": ...}}
    """
    results = {}

    for batch_start in range(0, len(pr_numbers), GRAPHQL_BATCH_SIZE):
        batch = pr_numbers[batch_start:batch_start + GRAPHQL_BATCH_SIZE]

        pr_queries = []
        for i, pr_num in enumerate(batch):
            pr_queries.append(f"""
            pr{i}: pullRequest(number: {pr_num}) {{
              number
              mergeCommit {{
                oid
                parents(first: 1) {{
                  nodes {{ oid }}
                }}
              }}
            }}""")

        query = f"""
        query($owner: String!, $repo: String!) {{
          repository(owner: $owner, name: $repo) {{
            {"".join(pr_queries)}
          }}
        }}
        """

        response = github_graphql(query, {"owner": "elastic", "repo": "elasticsearch"})

        if response.status_code != 200:
            print(f"  Error fetching SHAs: {response.status_code}")
            continue

        data = response.json()
        if "errors" in data:
            print(f"  GraphQL errors: {data['errors'][:2]}")

        repo_data = data.get("data", {}).get("repository", {})
        for i, pr_num in enumerate(batch):
            pr_data = repo_data.get(f"pr{i}")
            if not pr_data or not pr_data.get("mergeCommit"):
                continue

            merge_commit = pr_data["mergeCommit"]["oid"]
            parents = pr_data["mergeCommit"].get("parents", {}).get("nodes", [])
            base_commit = parents[0]["oid"] if parents else None

            if merge_commit and base_commit:
                results[pr_num] = {
                    "merge_commit": merge_commit,
                    "base_commit": base_commit
                }

        print(f"  Fetched SHAs for batch {batch_start // GRAPHQL_BATCH_SIZE + 1} "
              f"({len(batch)} PRs, {len(results)} total resolved)")

    return results

# ============================================================================
# FILE CLASSIFICATION
# ============================================================================

def is_test_file(filename: str) -> bool:
    """Classify a file as test or source using elasticsearch conventions."""
    # Test directories
    if "/src/test/java/" in filename:
        return True
    if "/src/test/resources/" in filename:
        return True
    # Test file naming patterns (in case of unconventional paths)
    basename = filename.split("/")[-1]
    if basename.endswith(("Test.java", "Tests.java", "IT.java", "TestCase.java")):
        return True
    # Test fixtures in compute/test module
    if "/compute/test/" in filename:
        return True
    return False

def is_java_test_file(filename: str) -> bool:
    """Check if a file is a Java unit test (not YAML, csv-spec, etc.)."""
    return filename.endswith(".java") and is_test_file(filename)

def classify_files(patches: List[Dict]) -> Tuple[List[str], List[str]]:
    """
    Split patch files into (test_files, source_files).
    Only includes files that exist in the merge commit (excludes 'removed').
    """
    test_files = []
    source_files = []

    for patch in patches:
        filename = patch["filename"]
        status = patch.get("status", "modified")

        # Skip removed files - they won't exist in the merge commit
        if status == "removed":
            continue

        if is_test_file(filename):
            test_files.append(filename)
        else:
            source_files.append(filename)

    return test_files, source_files

# ============================================================================
# GRADLE COMMAND EXTRACTION
# ============================================================================

def extract_gradle_module(filepath: str) -> Optional[str]:
    """
    Extract the Gradle module path from a file path.
    e.g. 'x-pack/plugin/esql/src/test/java/...' -> ':x-pack:plugin:esql'
         'server/src/test/java/...' -> ':server'
    """
    parts = filepath.split("/")
    try:
        src_idx = parts.index("src")
        module_path = "/".join(parts[:src_idx])
        return ":" + module_path.replace("/", ":")
    except ValueError:
        return None

def extract_test_fqn(filepath: str) -> Optional[str]:
    """
    Extract the fully-qualified class name from a test file path.
    e.g. 'x-pack/.../src/test/java/org/elasticsearch/.../FooTests.java'
         -> 'org.elasticsearch....FooTests'
    """
    parts = filepath.split("/")
    try:
        java_idx = parts.index("java")
        fqn = ".".join(parts[java_idx + 1:])
        return fqn.replace(".java", "")
    except ValueError:
        return None

def build_gradle_commands(test_files: List[str]) -> List[str]:
    """
    Build Gradle test commands for the given test files.
    Groups tests by module to minimize Gradle invocations.
    """
    # Group test files by module
    module_tests: Dict[str, List[str]] = {}
    for filepath in test_files:
        if not filepath.endswith(".java"):
            continue

        module = extract_gradle_module(filepath)
        fqn = extract_test_fqn(filepath)

        if not module or not fqn:
            continue

        module_tests.setdefault(module, []).append(fqn)

    commands = []
    for module, fqns in module_tests.items():
        test_filters = " ".join(f"--tests {fqn}" for fqn in fqns)
        cmd = f"./gradlew {module}:test {test_filters} {' '.join(GRADLE_FLAGS)}"
        commands.append(cmd)

    return commands

# ============================================================================
# GIT OPERATIONS
# ============================================================================

def ensure_clone() -> bool:
    """Ensure the elasticsearch repo is cloned. Returns True on success."""
    if os.path.isdir(os.path.join(CLONE_DIR, ".git")):
        print(f"  Using existing clone at {CLONE_DIR}")
        # Fetch latest to ensure we have all commits
        result = subprocess.run(
            ["git", "fetch", "--all"],
            cwd=CLONE_DIR,
            capture_output=True,
            timeout=300
        )
        return result.returncode == 0

    print(f"  Cloning elasticsearch to {CLONE_DIR} (this will take a while)...")
    os.makedirs(os.path.dirname(CLONE_DIR), exist_ok=True)
    result = subprocess.run(
        ["git", "clone", REPO_URL, CLONE_DIR],
        capture_output=True,
        timeout=3600  # 1 hour for initial clone
    )
    if result.returncode != 0:
        print(f"  Clone failed: {result.stderr.decode()[:500]}")
        return False
    return True

def reset_repo(commit: str) -> bool:
    """Hard reset the repo to a specific commit."""
    # Force checkout
    result = subprocess.run(
        ["git", "checkout", "--force", commit],
        cwd=CLONE_DIR,
        capture_output=True,
        timeout=120
    )
    if result.returncode != 0:
        print(f"  git checkout failed: {result.stderr.decode()[:300]}")
        return False

    # Clean untracked files
    result = subprocess.run(
        ["git", "clean", "-fdx"],
        cwd=CLONE_DIR,
        capture_output=True,
        timeout=120
    )
    if result.returncode != 0:
        print(f"  git clean failed: {result.stderr.decode()[:300]}")
        return False

    return True

def checkout_files(commit: str, files: List[str]) -> Tuple[bool, str]:
    """Checkout specific files from a commit. Returns (success, error_msg)."""
    if not files:
        return True, ""

    result = subprocess.run(
        ["git", "checkout", commit, "--"] + files,
        cwd=CLONE_DIR,
        capture_output=True,
        timeout=60
    )
    if result.returncode != 0:
        return False, result.stderr.decode()[:500]
    return True, ""

# ============================================================================
# TEST EXECUTION
# ============================================================================

def run_gradle_tests(commands: List[str]) -> Tuple[bool, str]:
    """
    Run Gradle test commands. Returns (all_passed, output_summary).
    Tests pass if ALL commands return exit code 0.
    """
    all_output = []

    for cmd in commands:
        print(f"    Running: {cmd[:120]}...")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=CLONE_DIR,
                capture_output=True,
                timeout=TEST_TIMEOUT
            )
            stdout = result.stdout.decode(errors="replace")
            stderr = result.stderr.decode(errors="replace")

            # Capture last 50 lines for diagnostics
            output_lines = (stdout + "\n" + stderr).strip().split("\n")
            summary = "\n".join(output_lines[-50:])
            all_output.append(summary)

            if result.returncode != 0:
                print(f"    FAILED (exit code {result.returncode})")
                return False, "\n---\n".join(all_output)
            else:
                print(f"    PASSED")

        except subprocess.TimeoutExpired:
            all_output.append(f"TIMEOUT after {TEST_TIMEOUT}s")
            print(f"    TIMEOUT")
            return False, "\n---\n".join(all_output)

    return True, "\n---\n".join(all_output)

# ============================================================================
# JUNIT XML PARSING
# ============================================================================

def find_test_report_xmls(gradle_cmds: List[str]) -> List[str]:
    """
    Find JUnit XML report files for the modules referenced by the Gradle commands.
    Reports live at <module>/build/test-results/test/TEST-*.xml
    """
    xml_files = []
    for cmd in gradle_cmds:
        # Extract module from command like './gradlew :x-pack:plugin:ml:test ...'
        match = re.search(r'\s(:\S+):test\s', cmd)
        if not match:
            continue
        gradle_module = match.group(1)  # e.g. ':x-pack:plugin:ml'
        module_dir = gradle_module.lstrip(':').replace(':', '/')
        report_dir = os.path.join(CLONE_DIR, module_dir, 'build', 'test-results', 'test')
        if os.path.isdir(report_dir):
            for fname in os.listdir(report_dir):
                if fname.startswith('TEST-') and fname.endswith('.xml'):
                    xml_files.append(os.path.join(report_dir, fname))
    return xml_files

def parse_test_results(xml_files: List[str]) -> Tuple[List[str], List[str]]:
    """
    Parse JUnit XML reports and return (failed_tests, passed_tests).
    Each entry is 'classname::testName' (SWE-Bench convention).
    """
    failed = []
    passed = []
    for xml_path in xml_files:
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for tc in root.findall('.//testcase'):
                classname = tc.get('classname', '')
                name = tc.get('name', '')
                if not classname or not name:
                    continue
                test_id = f"{classname}::{name}"
                if tc.find('failure') is not None or tc.find('error') is not None:
                    failed.append(test_id)
                elif tc.get('skipped') is not None or tc.find('skipped') is not None:
                    continue  # skip skipped tests
                else:
                    passed.append(test_id)
        except ET.ParseError:
            continue
    return failed, passed

# ============================================================================
# SWE-BENCH DATA EXTRACTION
# ============================================================================

def build_unified_patch(patches: List[Dict], file_filter) -> str:
    """
    Reconstruct a unified diff from GitHub's hunk-only patches.
    file_filter is a callable that returns True for files to include.
    """
    diff_parts = []
    for p in patches:
        filename = p["filename"]
        if not file_filter(filename):
            continue
        raw_patch = p.get("patch", "")
        if not raw_patch:
            continue
        status = p.get("status", "modified")
        if status == "added":
            header = f"--- /dev/null\n+++ b/{filename}"
        elif status == "removed":
            header = f"--- a/{filename}\n+++ /dev/null"
        else:
            header = f"--- a/{filename}\n+++ b/{filename}"
        diff_parts.append(f"{header}\n{raw_patch}")
    return "\n".join(diff_parts)

def extract_version() -> str:
    """Extract elasticsearch version from the checked-out repo."""
    for candidate in [
        os.path.join(CLONE_DIR, "build-tools-internal", "version.properties"),
        os.path.join(CLONE_DIR, "buildSrc", "version.properties"),
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

# ============================================================================
# RESUMABLE LOAD/SAVE (pattern from analyze_prs.py)
# ============================================================================

def load_existing_results() -> Tuple[List[Dict], set]:
    """Load already-verified results for resume support."""
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
        done = {r["pr_number"] for r in results}
        return results, done
    except (FileNotFoundError, json.JSONDecodeError):
        return [], set()

def save_results(results: List[Dict]):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

# ============================================================================
# MAIN VERIFICATION LOGIC
# ============================================================================

def verify_pr(pr: Dict, shas: dict) -> Dict:
    """
    Run fail-to-pass verification on a single PR.
    Returns a result dict with status, SWE-Bench fields, and details.
    """
    pr_number = pr["pr_number"]
    merge_commit = shas["merge_commit"]
    base_commit = shas["base_commit"]

    result = {
        "pr_number": pr_number,
        "title": pr["title"],
        "merge_commit": merge_commit,
        "base_commit": base_commit,
        "status": "error",
        "details": "",
        "fail_phase_output": "",
        "pass_phase_output": "",
        # SWE-Bench fields (populated on success)
        "instance_id": "",
        "patch": "",
        "test_patch": "",
        "FAIL_TO_PASS": [],
        "PASS_TO_PASS": [],
        "version": "",
    }

    # Classify files
    test_files, source_files = classify_files(pr["patches"])

    # Filter to Java test files only
    java_test_files = [f for f in test_files if f.endswith(".java")]

    if not java_test_files:
        result["status"] = "skipped"
        result["details"] = "No Java test files found"
        return result

    # Check for renamed files
    has_renamed = any(p.get("status") == "renamed" for p in pr["patches"])
    if has_renamed:
        result["status"] = "skipped"
        result["details"] = "PR contains renamed files (not supported yet)"
        return result

    # Build Gradle commands
    gradle_cmds = build_gradle_commands(java_test_files)
    if not gradle_cmds:
        result["status"] = "skipped"
        result["details"] = "Could not build Gradle test commands"
        return result

    result["test_files"] = java_test_files
    result["source_files"] = source_files
    result["gradle_commands"] = gradle_cmds

    # ---- PHASE 1: Reset to base commit ----
    print(f"  [1/4] Resetting to base commit {base_commit[:10]}...")
    if not reset_repo(base_commit):
        result["details"] = "Failed to reset to base commit"
        return result

    # Check that gradlew exists at this commit (very old PRs may lack it)
    if not os.path.isfile(os.path.join(CLONE_DIR, "gradlew")):
        result["status"] = "skipped"
        result["details"] = "No gradlew at base commit (too old)"
        return result

    # Extract version while we're at the base commit
    result["version"] = extract_version()

    # ---- PHASE 2: Apply test files only, expect FAIL ----
    print(f"  [2/4] Applying {len(test_files)} test files from {merge_commit[:10]}...")
    ok, err = checkout_files(merge_commit, test_files)
    if not ok:
        result["details"] = f"Failed to checkout test files: {err}"
        return result

    print(f"  [2/4] Running tests (expecting FAIL)...")
    tests_passed, output = run_gradle_tests(gradle_cmds)
    result["fail_phase_output"] = output[-2000:]  # Truncate for storage

    if tests_passed:
        result["status"] = "invalid_tests_pass_without_fix"
        result["details"] = "Tests passed without source fix - not a valid fail-to-pass candidate"
        return result

    # Parse FAIL_TO_PASS from JUnit XML reports (fail phase)
    xml_files = find_test_report_xmls(gradle_cmds)
    fail_phase_failed, fail_phase_passed = parse_test_results(xml_files)
    if fail_phase_failed:
        result["FAIL_TO_PASS"] = fail_phase_failed
        print(f"  [2/4] Parsed {len(fail_phase_failed)} failing, {len(fail_phase_passed)} passing test(s)")
    else:
        # No XML reports = compilation failure. Fall back to test class FQNs.
        fqns = [extract_test_fqn(f) for f in java_test_files]
        result["FAIL_TO_PASS"] = [fqn for fqn in fqns if fqn]
        print(f"  [2/4] No XML reports (compilation failure), using {len(result['FAIL_TO_PASS'])} test class FQN(s)")

    # ---- PHASE 3: Apply source files, expect PASS ----
    print(f"  [3/4] Applying {len(source_files)} source files from {merge_commit[:10]}...")
    ok, err = checkout_files(merge_commit, source_files)
    if not ok:
        result["details"] = f"Failed to checkout source files: {err}"
        return result

    print(f"  [4/4] Running tests (expecting PASS)...")
    tests_passed, output = run_gradle_tests(gradle_cmds)
    result["pass_phase_output"] = output[-2000:]

    if not tests_passed:
        result["status"] = "invalid_tests_fail_with_fix"
        result["details"] = "Tests still fail after applying source fix"
        return result

    # Parse PASS_TO_PASS from JUnit XML reports (pass phase)
    xml_files = find_test_report_xmls(gradle_cmds)
    pass_phase_failed, pass_phase_passed = parse_test_results(xml_files)
    result["PASS_TO_PASS"] = pass_phase_passed
    print(f"  [4/4] Parsed {len(pass_phase_passed)} passing test(s)")

    # Build SWE-Bench fields
    result["instance_id"] = f"elastic__elasticsearch-{pr_number}"
    result["patch"] = build_unified_patch(
        pr["patches"], lambda f: not is_test_file(f)
    )
    result["test_patch"] = build_unified_patch(
        pr["patches"], lambda f: is_test_file(f)
    )

    # Success!
    result["status"] = "verified"
    result["details"] = "Tests fail without fix and pass with fix"
    return result

def check_jdk():
    """Check that JDK 21+ is available (elasticsearch requirement)."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            timeout=10
        )
        version_output = result.stderr.decode() + result.stdout.decode()
        print(f"  Java version: {version_output.strip().split(chr(10))[0]}")

        # Parse version number
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

def main():
    print("=" * 80)
    print("Fail-to-Pass Verification")
    print("=" * 80)

    # ---- JDK check ----
    print("\n[Prerequisites]")
    if not check_jdk():
        print("JDK 21+ is required. Set JAVA_HOME or install JDK 21.")
        sys.exit(1)

    # ---- Load PR data ----
    print(f"\n[Loading data]")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            all_prs = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        sys.exit(1)

    # Filter to elasticsearch PRs with unit tests
    candidates = [
        pr for pr in all_prs
        if pr.get("repo") == "elastic/elasticsearch"
        and pr.get("verifiability_audit", {}).get("has_tests") is True
        and pr.get("verifiability_audit", {}).get("test_type") == "unit"
    ]
    print(f"  {len(all_prs)} total PRs, {len(candidates)} elasticsearch unit-test candidates")

    # ---- Resume support ----
    results, already_done = load_existing_results()
    candidates = [pr for pr in candidates if pr["pr_number"] not in already_done]
    print(f"  {len(already_done)} already processed, {len(candidates)} remaining")

    if not candidates:
        print("\nAll candidates already processed. Nothing to do.")
        return

    # ---- Fetch commit SHAs ----
    print(f"\n[Fetching commit SHAs via GraphQL]")
    pr_numbers = [pr["pr_number"] for pr in candidates]
    sha_map = fetch_commit_shas_batch(pr_numbers)
    print(f"  Resolved SHAs for {len(sha_map)}/{len(pr_numbers)} PRs")

    # Filter candidates to those with resolved SHAs
    candidates = [pr for pr in candidates if pr["pr_number"] in sha_map]

    # ---- Ensure clone ----
    print(f"\n[Repository setup]")
    if not ensure_clone():
        print("Failed to clone/update elasticsearch. Exiting.")
        sys.exit(1)

    # ---- Process each PR ----
    print(f"\n[Processing {len(candidates[:100])} PRs]")
    stats = {"verified": 0, "invalid_tests_pass_without_fix": 0,
             "invalid_tests_fail_with_fix": 0, "error": 0, "skipped": 0}

    for i, pr in enumerate(candidates[:100]):
        pr_number = pr["pr_number"]
        shas = sha_map[pr_number]

        print(f"\n{'─' * 60}")
        print(f"[{i + 1}/{len(candidates[:100])}] PR #{pr_number}: {pr['title'][:60]}")
        print(f"  base={shas['base_commit'][:10]} merge={shas['merge_commit'][:10]}")

        try:
            result = verify_pr(pr, shas)
        except Exception as e:
            result = {
                "pr_number": pr_number,
                "title": pr["title"],
                "merge_commit": shas["merge_commit"],
                "base_commit": shas["base_commit"],
                "status": "error",
                "details": f"Exception: {str(e)[:500]}",
                "fail_phase_output": "",
                "pass_phase_output": "",
            }

        stats[result["status"]] = stats.get(result["status"], 0) + 1
        print(f"  Result: {result['status']} - {result.get('details', '')[:100]}")

        results.append(result)
        save_results(results)

    # ---- Summary ----
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")
    print(f"  Total processed: {sum(stats.values())}")
    print(f"\nResults saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
