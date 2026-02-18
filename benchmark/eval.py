#!/usr/bin/env python3
"""
Evaluation script for the Elasticsearch benchmark.

Evaluates model-generated patches against benchmark instances by:
  1. Loading instance metadata from dataset.jsonl
  2. Reading model predictions from a patches JSON file
  3. For each prediction, running inside a Docker container:
     a. Apply test_patch (adds test files that verify the fix)
     b. Apply model_patch (the agent's attempted fix)
     c. Run the test suite via run_script.sh
     d. Parse test output via parser.py
     e. Score: all FAIL_TO_PASS must pass, all PASS_TO_PASS must still pass
  4. Writing results to output directory

Usage:
  python eval.py --patches patches.json [--output_dir results/] [--num_workers 4] [--timeout 3600]

patches.json format:
  [
    {
      "instance_id": "elastic__elasticsearch-141775",
      "patch": "diff --git a/...",
      "prefix": "model_name"
    },
    ...
  ]

Alternatively, "model_patch" can be used instead of "patch".
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import docker
except ImportError:
    print("Error: docker package required. Install with: pip install docker", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BENCHMARK_DIR = Path(__file__).resolve().parent
DATASET_FILE = BENCHMARK_DIR / "dataset.jsonl"
RUN_SCRIPTS_DIR = BENCHMARK_DIR / "run_scripts"
PARSER_FILE = BENCHMARK_DIR / "parser.py"
DOCKER_IMAGE_PREFIX = "es-bench"


def load_dataset(path: Path) -> dict[str, dict]:
    """Load dataset.jsonl into a dict keyed by instance_id."""
    dataset = {}
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            dataset[record["instance_id"]] = record
    logger.info(f"Loaded {len(dataset)} instances from {path}")
    return dataset


def load_patches(path: Path) -> list[dict]:
    """Load patches JSON file."""
    with open(path) as f:
        patches = json.load(f)
    logger.info(f"Loaded {len(patches)} patches from {path}")
    return patches


def build_entry_script(instance: dict, instance_id: str) -> str:
    """Build the entry script that runs inside the Docker container.

    Order of operations:
      1. Apply test_patch (adds test files that define pass/fail criteria)
      2. Apply model_patch (the agent's attempted fix)
      3. Run the test suite
      4. Parse test output into structured JSON
    """
    return f"""#!/bin/bash
set -o pipefail

cd /app

# Disable Gradle file watcher to prevent crashes in Docker
export GRADLE_OPTS="-Dorg.gradle.vfs.watch=false"

echo "=== Instance: {instance_id} ==="
echo "=== Step 1: Applying test patch ==="
git apply --verbose /workspace/test_patch.diff 2>&1
TEST_PATCH_EXIT=$?
if [ $TEST_PATCH_EXIT -ne 0 ]; then
    echo "ERROR: Failed to apply test patch (exit code $TEST_PATCH_EXIT)"
    echo "Attempting with --reject to see partial results..."
    git apply --reject --verbose /workspace/test_patch.diff 2>&1 || true
fi

echo ""
echo "=== Step 2: Applying model patch ==="
git apply --verbose /workspace/model_patch.diff 2>&1
MODEL_PATCH_EXIT=$?
if [ $MODEL_PATCH_EXIT -ne 0 ]; then
    echo "WARNING: Failed to apply model patch (exit code $MODEL_PATCH_EXIT)"
    echo "Attempting with --reject..."
    git apply --reject --verbose /workspace/model_patch.diff 2>&1 || true
fi

echo ""
echo "=== Step 3: Running tests ==="
bash /workspace/run_script.sh > /workspace/stdout.log 2> /workspace/stderr.log
TEST_EXIT=$?
echo "Test exit code: $TEST_EXIT"

echo ""
echo "=== Step 4: Parsing test output ==="
cd /workspace
python3 parser.py /app stdout.log stderr.log 2>&1
PARSE_EXIT=$?
if [ $PARSE_EXIT -ne 0 ]; then
    echo "WARNING: Parser failed (exit code $PARSE_EXIT)"
fi

echo ""
echo "=== Evaluation complete ==="
echo "test_patch_applied: $TEST_PATCH_EXIT"
echo "model_patch_applied: $MODEL_PATCH_EXIT"
echo "test_exit_code: $TEST_EXIT"
echo "parser_exit_code: $PARSE_EXIT"
"""


def evaluate_instance(
    client: docker.DockerClient,
    instance: dict,
    model_patch: str,
    run_scripts_dir: Path,
    timeout: int,
    allow_network: bool = False,
) -> dict:
    """Evaluate a single instance inside a Docker container.

    Returns a result dict with scoring information.
    """
    instance_id = instance["instance_id"]
    image_name = f"{DOCKER_IMAGE_PREFIX}-{instance_id}"
    result = {
        "instance_id": instance_id,
        "resolved": False,
        "test_patch_applied": False,
        "model_patch_applied": False,
        "tests_ran": False,
        "error": None,
        "fail_to_pass_results": {},
        "pass_to_pass_results": {},
    }

    # Create a temp directory with all workspace files
    with tempfile.TemporaryDirectory(prefix=f"esbench_{instance_id}_") as tmpdir:
        workspace = Path(tmpdir)

        # Write test_patch.diff (ensure trailing newline for git apply)
        test_patch = instance.get("test_patch", "")
        if test_patch and not test_patch.endswith("\n"):
            test_patch += "\n"
        (workspace / "test_patch.diff").write_text(test_patch)

        # Write model_patch.diff (ensure trailing newline for git apply)
        if model_patch and not model_patch.endswith("\n"):
            model_patch += "\n"
        (workspace / "model_patch.diff").write_text(model_patch)

        # Copy run_script.sh from per-instance directory
        instance_scripts = run_scripts_dir / instance_id
        run_script_src = instance_scripts / "run_script.sh"
        if not run_script_src.exists():
            result["error"] = f"Missing run_script.sh in {instance_scripts}"
            logger.error(f"[{instance_id}] {result['error']}")
            return result
        (workspace / "run_script.sh").write_text(run_script_src.read_text())

        # Copy shared parser.py
        if not PARSER_FILE.exists():
            result["error"] = f"Missing shared parser: {PARSER_FILE}"
            logger.error(f"[{instance_id}] {result['error']}")
            return result
        (workspace / "parser.py").write_text(PARSER_FILE.read_text())

        # Write entry script
        entry_script = build_entry_script(instance, instance_id)
        (workspace / "entry.sh").write_text(entry_script)

        # Run the container
        try:
            logger.info(f"[{instance_id}] Starting container (image: {image_name})")
            container = client.containers.run(
                image=image_name,
                entrypoint="",
                command=["bash", "-c", """
set -e
useradd -m -u 1000 elasticsearch 2>/dev/null || true
chown -R elasticsearch:elasticsearch /app /workspace
su elasticsearch -s /bin/bash -c 'bash /workspace/entry.sh'
"""],
                volumes={str(workspace): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/app",
                detach=True,
                mem_limit="16g",
                network_mode=None if allow_network else "none", # None means default network, "none" disables all networking
                user="root",
                environment={
                    "GRADLE_OPTS": "-Dorg.gradle.vfs.watch=false",
                    "ES_JAVA_OPTS": "-Des.enforce.bootstrap.checks=false",
                },
            )

            # Wait for completion with timeout
            try:
                client.api.timeout = timeout + 10  # Add buffer to API timeout
                exit_result = container.wait(timeout=timeout)
                exit_code = exit_result.get("StatusCode", -1)
            except Exception as e:
                logger.warning(f"[{instance_id}] Container timed out after {timeout}s, killing...")
                container.kill()
                result["error"] = f"Timeout after {timeout}s"
                return result

            # Collect logs
            stdout_log = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr_log = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            # Save full logs
            (workspace / "container_stdout.log").write_text(stdout_log)
            (workspace / "container_stderr.log").write_text(stderr_log)

            # Parse entry script output for status flags
            if "test_patch_applied: 0" in stdout_log:
                result["test_patch_applied"] = True
            if "model_patch_applied: 0" in stdout_log:
                result["model_patch_applied"] = True

            # Read parsed test output
            output_json_path = workspace / "output.json"
            if output_json_path.exists():
                result["tests_ran"] = True
                with open(output_json_path) as f:
                    test_output = json.load(f)

                # Score the results
                result = score_instance(instance, test_output, result)
            else:
                result["error"] = "No output.json produced by parser"
                logger.warning(f"[{instance_id}] {result['error']}")

                # Check if we can get info from stdout.log directly
                stdout_path = workspace / "stdout.log"
                stderr_path = workspace / "stderr.log"
                if stdout_path.exists():
                    logger.info(f"[{instance_id}] stdout.log exists ({stdout_path.stat().st_size} bytes)")
                if stderr_path.exists():
                    logger.info(f"[{instance_id}] stderr.log exists ({stderr_path.stat().st_size} bytes)")

        except docker.errors.ImageNotFound:
            result["error"] = f"Docker image not found: {image_name}"
            logger.error(f"[{instance_id}] {result['error']}")
            logger.error(f"[{instance_id}] Build it with: docker build -t {image_name} benchmark/dockerfiles/instances/{instance_id}/")
        except docker.errors.APIError as e:
            result["error"] = f"Docker API error: {str(e)[:200]}"
            logger.error(f"[{instance_id}] {result['error']}")
        finally:
            # Save workspace files for debugging (NEW)
            debug_dir = Path(f"debug_{instance_id}")
            debug_dir.mkdir(exist_ok=True)
            for log_file in ["stdout.log", "stderr.log", "container_stdout.log", "container_stderr.log", "output.json"]:
                src = workspace / log_file
                if src.exists():
                    import shutil
                    shutil.copy(src, debug_dir / log_file)
                    logger.info(f"[{instance_id}] Saved {log_file} to {debug_dir}/")
            # Clean up container
            try:
                container.remove(force=True)
            except Exception:
                pass

    return result


def score_instance(instance: dict, test_output: dict, result: dict) -> dict:
    """Score an instance based on parsed test output.

    An instance is "resolved" if:
      - ALL tests in fail_to_pass have status PASSED
      - ALL tests in pass_to_pass have status PASSED
    """
    instance_id = instance["instance_id"]
    tests = test_output.get("tests", [])

    # Build sets of test names by status
    passed_tests = set()
    failed_tests = set()
    skipped_tests = set()
    all_test_names = set()
    for t in tests:
        name = t["name"]
        all_test_names.add(name)
        if t["status"] == "PASSED":
            passed_tests.add(name)
        elif t["status"] == "SKIPPED":
            skipped_tests.add(name)
        else:
            failed_tests.add(name)

    # Load expected test sets
    fail_to_pass = set(json.loads(instance["fail_to_pass"]))
    pass_to_pass = set(json.loads(instance["pass_to_pass"]))

    # Check fail_to_pass: these tests MUST now pass (they failed before the fix)
    # Tests not found in any output are skipped (e.g. utility classes, abstract bases)
    f2p_results = {}
    for test in fail_to_pass:
        f2p_results[test] = _find_test_match(test, passed_tests, skipped_tests, all_test_names)
    result["fail_to_pass_results"] = f2p_results

    # Check pass_to_pass: these tests MUST still pass
    p2p_results = {}
    for test in pass_to_pass:
        p2p_results[test] = _find_test_match(test, passed_tests, skipped_tests, all_test_names)
    result["pass_to_pass_results"] = p2p_results

    f2p_passed = sum(1 for v in f2p_results.values() if v == "PASSED")
    f2p_failed = sum(1 for v in f2p_results.values() if v == "FAILED")
    f2p_skipped = sum(1 for v in f2p_results.values() if v == "SKIPPED")
    f2p_not_found = sum(1 for v in f2p_results.values() if v == "NOT_FOUND")
    f2p_total = f2p_passed + f2p_failed  # exclude NOT_FOUND and SKIPPED from scoring. #TODO: include skipped in total, ensure they are not skipped!

    p2p_passed = sum(1 for v in p2p_results.values() if v == "PASSED")
    p2p_failed = sum(1 for v in p2p_results.values() if v == "FAILED")
    p2p_skipped = sum(1 for v in p2p_results.values() if v == "SKIPPED")
    p2p_not_found = sum(1 for v in p2p_results.values() if v == "NOT_FOUND")
    p2p_total = p2p_passed + p2p_failed + p2p_skipped  # include skipped for ratio check

    # F2P: all found tests must pass
    f2p_ok = (f2p_total > 0) and (f2p_passed == f2p_total)

    # P2P: fail if any test explicitly failed, or if >50% of tests were skipped
    p2p_ok = (p2p_failed == 0)
    if p2p_total > 0 and p2p_skipped > p2p_total * 0.5:
        p2p_ok = False

    result["resolved"] = f2p_ok and p2p_ok

    status = "RESOLVED" if result["resolved"] else "FAILED"
    f2p_info = f"F2P: {f2p_passed}/{f2p_total}"
    p2p_info = f"P2P: {p2p_passed}/{p2p_total}"
    if f2p_skipped:
        f2p_info += f" ({f2p_skipped} skipped)"
    if f2p_not_found:
        f2p_info += f" ({f2p_not_found} not found)"
    if p2p_skipped:
        p2p_info += f" ({p2p_skipped} skipped)"
    if p2p_not_found:
        p2p_info += f" ({p2p_not_found} not found)"
    logger.info(
        f"[{instance_id}] {status} | "
        f"{f2p_info} | "
        f"{p2p_info} | "
        f"Total tests parsed: {len(tests)}"
    )

    return result


def _find_test_match(test_name: str, passed_tests: set, skipped_tests: set, all_tests: set) -> str:
    """Check if a test passed, using exact or substring matching.

    Gradle test names may differ in format from the names stored in the dataset.
    For example:
      Dataset: "org.elasticsearch.foo.BarTests::testMethod" (full package)
      Gradle:  "BarTests::testMethod" (short class name from JUnit XML)

    We try exact match first, then various substring matches.

    Returns:
      "PASSED" if the test was found and passed,
      "SKIPPED" if the test was found but only skipped (not passed or failed),
      "FAILED" if the test was found but failed,
      "NOT_FOUND" if the test was not found in any test output.
    """
    # Helper: check if test_name matches any test in a given set
    def _matches_any(test_name: str, test_set: set) -> bool:
        if test_name in test_set:
            return True

        # Extract short class name from fully-qualified name
        # e.g. "org.elasticsearch...AvgTests" -> "AvgTests"
        # e.g. "org.elasticsearch...AvgTests::testMethod" -> "AvgTests::testMethod"
        short_name = test_name.split(".")[-1] if "." in test_name else test_name

        for t in test_set:
            # Prefix match (class-level): test output starts with expected name
            if t.startswith(test_name + "::") or t.startswith(test_name + " "):
                return True
            # Compare short class names (exact match to avoid AvgTests matching WeightedAvgTests)
            # Extract class part from output test name: "AvgTests::testMethod {TC}" -> "AvgTests"
            t_class = t.split("::")[0] if "::" in t else t
            if "::" in short_name:
                # F2P has method: "AvgTests::testMethod" == "AvgTests::testMethod"
                if short_name == t or t.startswith(short_name + " "):
                    return True
            else:
                # F2P is class-level: "AvgTests" == "AvgTests"
                if short_name == t_class:
                    return True
        return False

    if _matches_any(test_name, passed_tests):
        return "PASSED"

    if _matches_any(test_name, skipped_tests):
        return "SKIPPED"

    if _matches_any(test_name, all_tests):
        return "FAILED"

    logger.warning(f"  Test not found in output (skipping from scoring): {test_name}")
    return "NOT_FOUND"


def run_evaluation(
    patches: list[dict],
    dataset: dict[str, dict],
    run_scripts_dir: Path,
    output_dir: Path,
    num_workers: int,
    timeout: int,
    allow_network: bool = False,
):
    """Run evaluation for all patches."""
    output_dir.mkdir(parents=True, exist_ok=True)

    client = docker.from_env()

    # Validate patches against dataset
    valid_patches = []
    for p in patches:
        instance_id = p.get("instance_id")
        # Allow empty string patches (for validation), but skip if key is missing entirely
        model_patch = p.get("patch") if "patch" in p else p.get("model_patch")
        if model_patch is None:
            model_patch = ""
        prefix = p.get("prefix", "unknown")

        if not instance_id:
            logger.warning(f"Skipping patch with no instance_id")
            continue
        if instance_id not in dataset:
            logger.warning(f"Skipping {instance_id}: not found in dataset")
            continue

        valid_patches.append({
            "instance_id": instance_id,
            "model_patch": model_patch,
            "prefix": prefix,
        })

    logger.info(f"Evaluating {len(valid_patches)} patches ({len(patches) - len(valid_patches)} skipped)")

    results = []
    prefix = valid_patches[0]["prefix"] if valid_patches else "unknown"

    if num_workers <= 1:
        # Sequential execution
        for i, p in enumerate(valid_patches):
            instance = dataset[p["instance_id"]]
            logger.info(f"[{i+1}/{len(valid_patches)}] Evaluating {p['instance_id']}...")
            result = evaluate_instance(
                client, instance, p["model_patch"], run_scripts_dir, timeout,
                allow_network=allow_network,
            )
            result["prefix"] = p["prefix"]
            results.append(result)
    else:
        # Parallel execution
        futures = {}
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            for p in valid_patches:
                instance = dataset[p["instance_id"]]
                future = executor.submit(
                    evaluate_instance,
                    client, instance, p["model_patch"], run_scripts_dir, timeout,
                    allow_network=allow_network,
                )
                futures[future] = p

            for i, future in enumerate(as_completed(futures)):
                p = futures[future]
                try:
                    result = future.result()
                    result["prefix"] = p["prefix"]
                    results.append(result)
                except Exception as e:
                    logger.error(f"[{p['instance_id']}] Unexpected error: {e}")
                    results.append({
                        "instance_id": p["instance_id"],
                        "prefix": p["prefix"],
                        "resolved": False,
                        "error": str(e),
                    })

                if (i + 1) % 10 == 0 or i == len(futures) - 1:
                    resolved = sum(1 for r in results if r.get("resolved"))
                    logger.info(f"Progress: {i+1}/{len(futures)} evaluated, {resolved} resolved so far")

    # Write results
    write_results(results, output_dir, prefix)

    return results


def write_results(results: list[dict], output_dir: Path, prefix: str):
    """Write evaluation results to output directory."""

    # Full results JSON
    results_path = output_dir / f"eval_results_{prefix}.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Full results: {results_path}")

    # Summary: instance_id -> resolved (bool)
    summary = {r["instance_id"]: r.get("resolved", False) for r in results}
    summary_path = output_dir / f"eval_summary_{prefix}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Summary: {summary_path}")

    # Print summary to stdout
    total = len(results)
    resolved = sum(1 for r in results if r.get("resolved"))
    errors = sum(1 for r in results if r.get("error"))
    patch_applied = sum(1 for r in results if r.get("model_patch_applied"))
    tests_ran = sum(1 for r in results if r.get("tests_ran"))

    print("\n" + "=" * 60)
    print(f"  EVALUATION RESULTS: {prefix}")
    print("=" * 60)
    print(f"  Total instances:     {total}")
    print(f"  Resolved:            {resolved}/{total} ({100*resolved/total:.1f}%)" if total else "  Resolved: 0")
    print(f"  Patch applied:       {patch_applied}/{total}")
    print(f"  Tests ran:           {tests_ran}/{total}")
    print(f"  Errors:              {errors}/{total}")
    print("=" * 60)

    if errors > 0:
        print("\nErrors:")
        for r in results:
            if r.get("error"):
                print(f"  {r['instance_id']}: {r['error']}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate model patches against the Elasticsearch benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate with gold patches (validation - all tests should pass)
  python eval.py --patches gold_patches.json --output_dir results/gold/

  # Evaluate with empty patches (validation - fail_to_pass should fail, pass_to_pass should pass)
  python eval.py --patches empty_patches.json --output_dir results/empty/

  # Evaluate model predictions
  python eval.py --patches predictions.json --output_dir results/my_model/ --num_workers 4

  # Generate gold patches for validation
  python eval.py --generate_gold_patches gold_patches.json

  # Generate empty patches for validation
  python eval.py --generate_empty_patches empty_patches.json
        """,
    )

    parser.add_argument(
        "--patches",
        type=Path,
        help="Path to patches JSON file with model predictions",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_FILE,
        help=f"Path to dataset JSONL file (default: {DATASET_FILE})",
    )
    parser.add_argument(
        "--run_scripts",
        type=Path,
        default=RUN_SCRIPTS_DIR,
        help=f"Path to run_scripts directory (default: {RUN_SCRIPTS_DIR})",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("results"),
        help="Output directory for results (default: results/)",
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Container timeout in seconds (default: 3600 = 1 hour)",
    )
    parser.add_argument(
        "--generate_gold_patches",
        type=Path,
        metavar="OUTPUT_FILE",
        help="Generate gold patches JSON from dataset (for validation runs)",
    )
    parser.add_argument(
        "--generate_empty_patches",
        type=Path,
        metavar="OUTPUT_FILE",
        help="Generate empty patches JSON from dataset (to verify fail_to_pass tests fail without fix)",
    )
    parser.add_argument(
        "--instances",
        type=str,
        nargs="+",
        help="Only evaluate these instance IDs (for debugging)",
    )
    parser.add_argument(
        "--allow_network",
        action="store_true",
        help="Allow network access in containers (for validation before deps are cached in images)",
    )

    args = parser.parse_args()

    # Load dataset
    dataset = load_dataset(args.dataset)

    # Generate gold patches mode
    if args.generate_gold_patches:
        gold_patches = []
        for instance_id, instance in dataset.items():
            gold_patches.append({
                "instance_id": instance_id,
                "patch": instance["patch"],
                "prefix": "gold",
            })
        with open(args.generate_gold_patches, "w") as f:
            json.dump(gold_patches, f, indent=2)
        logger.info(f"Generated {len(gold_patches)} gold patches -> {args.generate_gold_patches}")
        return

    # Generate empty patches mode (for validation: fail_to_pass should fail, pass_to_pass should pass)
    if args.generate_empty_patches:
        empty_patches = []
        for instance_id, instance in dataset.items():
            empty_patches.append({
                "instance_id": instance_id,
                "patch": "",
                "prefix": "empty",
            })
        with open(args.generate_empty_patches, "w") as f:
            json.dump(empty_patches, f, indent=2)
        logger.info(f"Generated {len(empty_patches)} empty patches -> {args.generate_empty_patches}")
        return

    # Evaluation mode
    if not args.patches:
        parser.error("--patches is required for evaluation (or use --generate_gold_patches / --generate_empty_patches)")

    patches = load_patches(args.patches)

    # Filter to specific instances if requested
    if args.instances:
        instance_set = set(args.instances)
        patches = [p for p in patches if p.get("instance_id") in instance_set]
        logger.info(f"Filtered to {len(patches)} patches matching --instances")

    if args.allow_network:
        logger.warning("Network access ENABLED - only use for validation, not real evals!")

    start_time = time.time()
    results = run_evaluation(
        patches=patches,
        dataset=dataset,
        run_scripts_dir=args.run_scripts,
        output_dir=args.output_dir,
        num_workers=args.num_workers,
        timeout=args.timeout,
        allow_network=args.allow_network,
    )
    elapsed = time.time() - start_time
    logger.info(f"Total evaluation time: {elapsed:.1f}s ({elapsed/60:.1f}m)")


if __name__ == "__main__":
    main()
