"""Per-task counts over the files git tracks at the base commit.

The agent walks the task container's repository directory, so it also counts files that
are not part of the repository: build output and files generated when the environment
was set up (e.g. microsoft/vscode's gitignored ``out/``, Cython-generated C files in
scikit-learn). This script keeps the agent's own rules (skipped directories, skipped and
binary files, the source-code extension list) and adds one more: the file must be
tracked by git at the task's base commit.

Inputs: the per-file runs (``jobs/<benchmark>_perfile/<task>/agent/files.csv.gz``),
results/task_commits.tsv, the cached trees from fetch_trees.py, and the extension
categories of ``results/file_types/extension_categories.csv``.
Output: results/tracked_counts.tsv, one row per task.

    python tracked_counts.py
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tokenizer_core import SKIP_DIRS, SOURCE_CODE_EXTENSIONS  # noqa: E402

JOBS = HERE.parent / "jobs"
TREES = HERE / ".trees"
SRC = {e.lower() for e in SOURCE_CODE_EXTENSIONS}
CATEGORIES = ["source_code", "other_code", "docs", "config_build", "localization",
              "data_fixtures", "no_extension", "other"]
FIELDS = (["benchmark", "instance", "repo", "base_commit",
           "untracked_source_tokens", "untracked_source_files",
           "tracked_source_files_found_pct", "tracked_source_files_in_skipped_dirs",
           "source_code_tokens", "source_code_files", "source_code_lines",
           "source_code_nonblank_lines", "source_code_bytes", "total_tokens", "total_files"]
          + [f"{c}_{k}" for c in CATEGORIES for k in ("tokens", "files")])


def load_categories() -> dict[str, str]:
    with (HERE.parent / "results" / "file_types" / "extension_categories.csv").open() as f:
        return {r["extension"]: r["category"] for r in csv.DictReader(f)}


def in_skipped_dir(path: str) -> bool:
    return any(seg in SKIP_DIRS for seg in path.split("/")[:-1])


def count(task: dict, cats: dict[str, str]) -> dict:
    with gzip.open(TREES / f"{task['repo'].replace('/', '__')}__{task['base_commit']}.json.gz", "rt") as f:
        tracked = set(json.load(f)["blobs"])
    tracked_src = {p for p in tracked if os.path.splitext(p)[1].lower() in SRC}
    reachable = {p for p in tracked_src if not in_skipped_dir(p)}
    c: Counter = Counter()
    found = 0
    files_csv = JOBS / f"{task['benchmark']}_perfile" / task["job_dir"] / "agent" / "files.csv.gz"
    with gzip.open(files_csv, "rt") as fh:
        for r in csv.DictReader(fh):
            if r["tokenized"] not in ("True", "true", "1"):
                continue
            tokens, is_src = int(r["tokens"]), r["ext"] in SRC
            if r["path"] not in tracked:
                if is_src:
                    c["untracked_source_tokens"] += tokens
                    c["untracked_source_files"] += 1
                continue
            cat = "no_extension" if r["ext"] == "(no extension)" else cats.get(r["ext"], "other")
            c[f"{cat}_tokens"] += tokens
            c[f"{cat}_files"] += 1
            c["total_tokens"] += tokens
            c["total_files"] += 1
            if is_src:
                found += 1
                c["source_code_lines"] += int(r["lines"])
                c["source_code_nonblank_lines"] += int(r["nonblank_lines"])
                c["source_code_bytes"] += int(r["bytes"] or 0)
    row = {k: c[k] for k in FIELDS[4:]}
    row.update(benchmark=task["benchmark"], instance=task["instance"], repo=task["repo"],
               base_commit=task["base_commit"],
               tracked_source_files_found_pct=round(100 * found / max(1, len(reachable)), 2),
               tracked_source_files_in_skipped_dirs=len(tracked_src) - len(reachable))
    return row


def main() -> None:
    cats = load_categories()
    with (HERE / "results" / "task_commits.tsv").open() as f:
        tasks = list(csv.DictReader(f, delimiter="\t"))
    out = HERE / "results" / "tracked_counts.tsv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for task in tasks:
            w.writerow(count(task, cats))
    print(f"{len(tasks)} tasks -> {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
