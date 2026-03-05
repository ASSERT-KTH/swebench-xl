#!/usr/bin/env python3
"""
Package verified instances from fail_to_pass_results.json into SWE-bench Pro format.

Generates:
  1. benchmark/dataset.jsonl              - Clean dataset file with standardized schema
  2. benchmark/run_scripts/<instance_id>/ - Per-instance run_script.sh, instance_info.txt
"""

import json
import os
import stat
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT_DIR / "fail_to_pass_results.json"
INPUT_FILE_FULL = ROOT_DIR / "pr_analysis_results_full.json"
OUTPUT_DIR = ROOT_DIR / "benchmark"
DATASET_FILE = OUTPUT_DIR / "dataset.jsonl"
FILTERED_DATASET_FILE = OUTPUT_DIR / "filtered_dataset.jsonl"
RUN_SCRIPTS_DIR = OUTPUT_DIR / "run_scripts"


def load_verified_instances(path: Path, path_full: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    verified = [d for d in data if d["status"] == "verified"]
    with open(path_full) as f:
        full_data = json.load(f)
        for inst in verified:
            pr = inst["pr_number"]
            full_inst = next((i for i in full_data if i["pr_number"] == pr), None)
            if full_inst:
                inst.update(full_inst)

    print(f"Loaded {len(data)} total instances, {len(verified)} verified")
    return verified

def update_problem_statements() -> None:
    """
    For each entry in dataset.jsonl, find the matching entry in pr_analysis_results_full.json
    by instance_id and replace problem_statement_title and problem_statement_description
    with the combined titles and bodies from the matching entry's 'issues' array.
    """
    # Load pr_analysis_results_full.json and index by instance_id
    with open(INPUT_FILE_FULL, "r", encoding="utf-8") as f:
        pr_data = json.load(f)

    pr_lookup: dict = {
        f"{entry['repo'].replace('/', '__')}-{entry['pr_number']}": entry
        for entry in pr_data
    }

    # Process each line in dataset.jsonl
    updated_entries = []
    matched = 0
    skipped = 0

    with open(FILTERED_DATASET_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            entry = json.loads(line)
            instance_id = entry.get("instance_id")

            pr_entry = pr_lookup.get(instance_id)

            if pr_entry is None:
                print(f"[Line {line_num}] No match found for instance_id: {instance_id}")
                skipped += 1
                updated_entries.append(entry)
                continue

            issues = pr_entry.get("issues", [])
            if not issues:
                print(f"[Line {line_num}] No issues found for instance_id: {instance_id}")
                skipped += 1
                updated_entries.append(entry)
                continue

            if len(issues) == 1:
                entry["problem_statement_title"] = issues[0].get("title", "")
                entry["problem_statement_description"] = issues[0].get("body", "")
            else:
                entry["problem_statement_title"] = " | ".join(
                    issue.get("title", "") for issue in issues
                )
                entry["problem_statement_description"] = "\n\n---\n\n".join(
                    f"### Issue {i + 1}: {issue.get('title', '')}\n\n{issue.get('body', '')}"
                    for i, issue in enumerate(issues)
                )

            matched += 1
            updated_entries.append(entry)

    # Write updated entries back to output file
    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        for entry in updated_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"\nDone. Matched: {matched}, Skipped: {skipped}, Total: {len(updated_entries)}")

def create_dataset_jsonl(instances: list[dict], output_path: Path):
    """Export verified instances to JSONL with standardized SWE-bench Pro schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for inst in instances:
        record = {
            "instance_id": inst["instance_id"],
            "repo": "elastic/elasticsearch",
            "repo_language": "Java",
            "base_commit": inst["base_commit"],
            "patch": inst["patch"],
            "test_patch": inst["test_patch"],
            "problem_statement_title": inst["title"],
            "problem_statement_description": inst["description"],
            "fail_to_pass": json.dumps(inst["FAIL_TO_PASS"]),
            "pass_to_pass": json.dumps(inst["PASS_TO_PASS"]),
            "version": inst["version"],
            "selected_test_files_to_run": json.dumps(inst["test_files"]),
            "source_files": json.dumps(inst["source_files"]),
            "gradle_commands": json.dumps(inst["gradle_commands"]),
            "pr_number": inst["pr_number"],
            "merge_commit": inst["merge_commit"],
        }
        records.append(record)

    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    update_problem_statements()

    print(f"Wrote {len(records)} instances to {output_path}")
    return records


def generate_run_script(instance: dict, output_dir: Path):
    """Generate run_script.sh from gradle_commands."""
    gradle_commands = instance["gradle_commands"]

    # Build the script with each gradle command
    commands_block = ""
    for i, cmd in enumerate(gradle_commands):
        if "--no-configuration-cache" not in cmd:
            cmd = cmd + " --no-configuration-cache"
        commands_block += f"""
echo "=== Running gradle command {i + 1}/{len(gradle_commands)} ==="
{cmd}
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "Gradle command {i + 1} failed with exit code $EXIT_CODE"
fi
"""

    script = f"""#!/bin/bash
set -eo pipefail

# Run script for {instance["instance_id"]}
# Auto-generated by package_benchmark.py

cd /app

# Accept test files as arguments (comma-separated), but default to
# the pre-configured gradle commands if none are provided.
if [ $# -gt 0 ]; then
    TEST_FILES="$@"
    echo "Running with custom test files: $TEST_FILES"
    for tf in $(echo "$TEST_FILES" | tr ',' ' '); do
        ./gradlew test --tests "$tf" --no-daemon --stacktrace -x javadoc --no-configuration-cache
    done
else
    echo "Running pre-configured gradle commands..."
{commands_block}
fi

echo "=== Test execution complete ==="
"""
    script_path = output_dir / "run_script.sh"
    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)


def generate_instance_info(instance: dict, output_dir: Path):
    """Generate instance_info.txt with fail-to-pass and pass-to-pass test lists."""
    info_path = output_dir / "instance_info.txt"

    lines = []
    lines.append(f"instance_id: {instance['instance_id']}")
    lines.append(f"repo: elastic/elasticsearch")
    lines.append(f"version: {instance['version']}")
    lines.append(f"base_commit: {instance['base_commit']}")
    lines.append(f"pr_number: {instance['pr_number']}")
    lines.append("")
    lines.append("FAIL_TO_PASS:")
    for test in instance["FAIL_TO_PASS"]:
        lines.append(f"  - {test}")
    lines.append("")
    lines.append("PASS_TO_PASS:")
    for test in instance["PASS_TO_PASS"]:
        lines.append(f"  - {test}")

    with open(info_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found", file=sys.stderr)
        sys.exit(1)

    instances = load_verified_instances(INPUT_FILE, INPUT_FILE_FULL)

    # Step 1: Create dataset JSONL
    print("\n=== Step 1: Creating dataset JSONL ===")
    create_dataset_jsonl(instances, DATASET_FILE)

    # Step 2: Generate per-instance run scripts
    print("\n=== Step 2: Generating per-instance run scripts ===")
    for i, inst in enumerate(instances):
        instance_id = inst["instance_id"]
        instance_dir = RUN_SCRIPTS_DIR / instance_id
        instance_dir.mkdir(parents=True, exist_ok=True)

        generate_run_script(inst, instance_dir)
        generate_instance_info(inst, instance_dir)

        if (i + 1) % 20 == 0 or i == len(instances) - 1:
            print(f"  Generated {i + 1}/{len(instances)} instance scripts")

    print(f"\n=== Done ===")
    print(f"Dataset:     {DATASET_FILE}")
    print(f"Run scripts: {RUN_SCRIPTS_DIR}/")
    print(f"Total instances packaged: {len(instances)}")


if __name__ == "__main__":
    main()
