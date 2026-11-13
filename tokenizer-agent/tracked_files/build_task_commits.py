"""Join every task of the per-file tokenizer runs to its repository and base commit.

Reads the ``*_perfile`` jobs (for each task's instance id) and the commit sources in
``inputs/``, and writes results/task_commits.tsv with columns
benchmark, instance, job_dir, repo, base_commit.

    python build_task_commits.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS = HERE.parent / "jobs"
BENCHMARKS = ("xl_subset", "deepswe", "pro", "verified")


def commit_sources() -> dict[tuple[str, str], tuple[str, str]]:
    src: dict[tuple[str, str], tuple[str, str]] = {}
    # SWE-bench XL: instance, repo, merge commit, comma-separated parents; the base is the first parent.
    for line in (HERE / "inputs" / "xl_bases.txt").read_text().splitlines():
        iid, repo, _merge, parents = line.split()[:4]
        src[("xl_subset", iid)] = (repo, parents.split(",")[0])
    # DeepSWE: task, repo, base commit, ... (from each task's task.toml).
    with (HERE / "inputs" / "deepswe_tasks.tsv").open() as f:
        for row in csv.reader(f, delimiter="\t"):
            src[("deepswe", row[0])] = (row[1], row[2])
    # Verified and Pro: from the Hugging Face datasets (fetch_hf_commits.py). Pro ids differ in case only.
    for name in ("verified", "pro"):
        for line in (HERE / "inputs" / f"{name}_commits.jsonl").read_text().splitlines():
            x = json.loads(line)
            src[(name, x["instance_id"].lower())] = (x["repo"], x["base_commit"])
    return src


def main() -> None:
    src = commit_sources()
    rows, missing = [], []
    for bench in BENCHMARKS:
        for job in sorted((JOBS / f"{bench}_perfile").iterdir()):
            if "__" not in job.name:
                continue
            iid = json.loads((job / "agent" / "token_counts.json").read_text())["instance_id"]
            key_id = iid.removeprefix("bp_")
            key = (bench, key_id.lower() if bench == "pro" else key_id)
            if key in src:
                rows.append((bench, iid, job.name, *src[key]))
            else:
                missing.append(key)
    if missing:
        raise SystemExit(f"{len(missing)} tasks without a base commit, e.g. {missing[:3]}")
    out = HERE / "results" / "task_commits.tsv"
    with out.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["benchmark", "instance", "job_dir", "repo", "base_commit"])
        w.writerows(rows)
    print(f"{len(rows)} tasks, {len({(r[3], r[4]) for r in rows})} distinct commits -> {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
