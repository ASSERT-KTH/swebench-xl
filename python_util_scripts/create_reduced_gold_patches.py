#!/usr/bin/env python3
"""
Create reduced_gold_patches.json containing only the required (source) files
from each Harbor benchmark instance's gold patch, stripping out changelogs,
test files, test fixtures, documentation, and CI configuration.

Reads from: harbor_tasks/*/solution/solve.sh  (gold patch)
            harbor_tasks/*/tests/config.json   (instance metadata)
Writes to:  reduced_gold_patches.json
"""

from __future__ import annotations

import os
import re
import json
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
TASKS_DIR = os.path.join(REPO_ROOT, "harbor_tasks")
OUTPUT_PATH = os.path.join(REPO_ROOT, "reduced_gold_patches.json")


def extract_diff(solve_content: str) -> str | None:
    """Extract the unified diff from solve.sh between __SOLUTION__ markers."""
    match = re.search(
        r"cat > solution_patch\.diff << '__SOLUTION__'\n(.*?)\n__SOLUTION__",
        solve_content,
        re.DOTALL,
    )
    return match.group(1) if match else None


def split_diff_into_file_chunks(diff_text: str) -> list[dict]:
    """
    Split a unified diff into per-file chunks.
    Returns a list of dicts: {filepath, old_path, new_path, is_new, is_deleted, chunk_text}
    """
    chunks = []
    lines = diff_text.split("\n")
    i = 0

    while i < len(lines):
        if lines[i].startswith("--- "):
            old_line = lines[i]
            if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                new_line = lines[i + 1]
                old_path = old_line[4:].strip()
                new_path = new_line[4:].strip()
                is_new = old_path == "/dev/null"
                is_deleted = new_path == "/dev/null"

                if is_new:
                    filepath = new_path.replace("b/", "", 1)
                elif is_deleted:
                    filepath = old_path.replace("a/", "", 1)
                else:
                    filepath = new_path.replace("b/", "", 1)

                # Collect all lines for this file until next --- / +++ pair
                chunk_lines = [old_line, new_line]
                j = i + 2
                while j < len(lines):
                    if (
                        lines[j].startswith("--- ")
                        and j + 1 < len(lines)
                        and lines[j + 1].startswith("+++ ")
                    ):
                        break
                    chunk_lines.append(lines[j])
                    j += 1

                chunks.append(
                    {
                        "filepath": filepath,
                        "old_path": old_path,
                        "new_path": new_path,
                        "is_new": is_new,
                        "is_deleted": is_deleted,
                        "chunk_text": "\n".join(chunk_lines),
                    }
                )
                i = j
                continue
        i += 1

    return chunks


def is_required_file(filepath: str) -> bool:
    """
    Return True if the file is a required source file (not a changelog,
    test, test fixture, doc, or CI config).
    """
    fp = filepath.lower()
    basename = os.path.basename(filepath).lower()

    # Changelog / release notes
    if "changelog" in fp or "docs/changelog" in fp:
        return False

    # Muted tests config
    if basename == "muted-tests.yml":
        return False

    # Documentation (non-changelog)
    if "/docs/" in fp and "changelog" not in fp and "test" not in fp and "/qa/" not in fp:
        return False

    # Test spec / fixture files
    if fp.endswith(".csv-spec") or fp.endswith(".csv"):
        if "/qa/" in fp or "test" in fp or "fixture" in fp:
            return False

    # Test framework code
    if "/test/framework/" in fp or "/test/external/" in fp:
        return False

    # Test source code
    if "/src/test/" in fp or "/test/java/" in fp:
        return False

    # YAML REST tests
    if "/yamlresttest/" in fp.replace("-", "").replace("_", ""):
        return False

    # Java REST tests
    if "/javaresttest/" in fp.replace("-", "").replace("_", ""):
        return False

    # Test directories
    if re.search(r"/tests?/", fp):
        return False

    # QA directories
    if "/qa/" in fp:
        return False

    return True


def main():
    results = []
    total_original = 0
    total_reduced = 0

    for task_id in sorted(os.listdir(TASKS_DIR)):
        task_path = os.path.join(TASKS_DIR, task_id)
        if not os.path.isdir(task_path):
            continue

        solve_sh = os.path.join(task_path, "solution", "solve.sh")
        config_json = os.path.join(task_path, "tests", "config.json")

        if not os.path.exists(solve_sh) or not os.path.exists(config_json):
            continue

        with open(solve_sh, "r") as f:
            solve_content = f.read()
        with open(config_json, "r") as f:
            config = json.load(f)

        gold_diff = extract_diff(solve_content)
        if not gold_diff:
            print(f"WARNING: Could not extract diff from {task_id}", file=sys.stderr)
            continue

        chunks = split_diff_into_file_chunks(gold_diff)
        total_original += len(chunks)

        required_chunks = [c for c in chunks if is_required_file(c["filepath"])]
        removed_chunks = [c for c in chunks if not is_required_file(c["filepath"])]
        total_reduced += len(required_chunks)

        # Reassemble the reduced diff
        reduced_diff = "\n".join(c["chunk_text"] for c in required_chunks)

        entry = {
            "instance_id": config.get("instance_id", task_id),
            "repo": config.get("repo", ""),
            "base_commit": config.get("base_commit", ""),
            "original_patch": config.get("patch", ""),
            "reduced_patch": reduced_diff,
            "original_file_count": len(chunks),
            "reduced_file_count": len(required_chunks),
            "removed_files": [c["filepath"] for c in removed_chunks],
            "required_files": [c["filepath"] for c in required_chunks],
        }
        results.append(entry)

        removed_str = (
            f" (removed: {', '.join(c['filepath'] for c in removed_chunks)})"
            if removed_chunks
            else ""
        )
        print(f"{task_id}: {len(chunks)} → {len(required_chunks)} files{removed_str}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote {OUTPUT_PATH}")
    print(f"Total: {total_original} files → {total_reduced} files across {len(results)} instances")


if __name__ == "__main__":
    main()
