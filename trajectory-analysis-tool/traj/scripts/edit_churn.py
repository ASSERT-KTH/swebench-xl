"""Edit churn rate analysis for benchmark runs.

Measures how often an agent writes to the same file multiple times:
- Edit churn rate: fraction of Write operations targeting an already-written file
- Avg writes per file: average number of times each unique file is written
- Churned files: files written more than once (potential struggle indicators)

Breakdowns are provided per resolved/unresolved status and per repository.

Usage:
    traj edit-churn <trajectory_dir> [-o output.json]
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from traj.scripts.file_recall import (
    _detect_run_format,
    _collect_instances_zip,
    _collect_instances_dir,
    _collect_instances_output_dir,
    _normalise_path,
)
from traj.loader import _detect_adapter
from traj.scripts import extract_repo


def _compute_churn_metrics(traj_data: list | dict, source_file: str = "") -> dict:
    """Compute edit churn metrics from a single trajectory.

    Returns a dict with:
    - total_writes: total number of Write operations
    - unique_files_written: number of distinct files written
    - rewrites: number of writes targeting an already-written file
    - churn_rate: rewrites / total_writes (0.0 if no writes)
    - avg_writes_per_file: total_writes / unique_files_written
    - churned_files: list of {file, writes} for files written more than once
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    write_counts: Counter[str] = Counter()
    for op in ops:
        if op.action != "Write" or not op.path:
            continue
        normalised = _normalise_path(op.path)
        if not normalised or normalised.endswith("/"):
            continue
        if "." not in normalised.split("/")[-1]:
            continue
        write_counts[normalised] += 1

    total_writes = sum(write_counts.values())
    unique_files = len(write_counts)
    rewrites = total_writes - unique_files  # first write to each file is not churn

    churned = [
        {"file": f, "writes": count}
        for f, count in write_counts.most_common()
        if count > 1
    ]

    return {
        "total_writes": total_writes,
        "unique_files_written": unique_files,
        "rewrites": rewrites,
        "churn_rate": round(rewrites / total_writes, 4) if total_writes > 0 else 0.0,
        "avg_writes_per_file": round(total_writes / unique_files, 2) if unique_files > 0 else 0.0,
        "churned_file_count": len(churned),
        "churned_files": churned,
    }


def analyse_directory(trajectory_dir: str) -> dict:
    """Run edit churn analysis on a benchmark run directory."""
    traj_dir = Path(trajectory_dir)
    run_format = _detect_run_format(traj_dir)
    if run_format == "dir":
        instance_data = _collect_instances_dir(traj_dir)
    elif run_format == "output_dir":
        instance_data = _collect_instances_output_dir(traj_dir)
    else:
        instance_data = _collect_instances_zip(traj_dir)

    per_instance = []
    resolved_results = []
    unresolved_results = []

    for instance_id, traj_data, resolved in instance_data:
        metrics = _compute_churn_metrics(traj_data, instance_id)
        result = {
            "instance_id": instance_id,
            "resolved": resolved,
            **metrics,
        }
        per_instance.append(result)

        if resolved is True:
            resolved_results.append(result)
        elif resolved is False:
            unresolved_results.append(result)

    def _avg(results: list[dict], key: str) -> float:
        if not results:
            return 0.0
        return round(sum(r[key] for r in results) / len(results), 4)

    def _section(results: list[dict]) -> dict:
        return {
            "count": len(results),
            "avg_churn_rate": _avg(results, "churn_rate"),
            "avg_writes_per_file": _avg(results, "avg_writes_per_file"),
            "avg_total_writes": _avg(results, "total_writes"),
            "avg_unique_files_written": _avg(results, "unique_files_written"),
            "avg_rewrites": _avg(results, "rewrites"),
            "avg_churned_file_count": _avg(results, "churned_file_count"),
        }

    # Group by repo
    repo_groups: dict[str, list[dict]] = defaultdict(list)
    for result in per_instance:
        repo = extract_repo(result["instance_id"])
        repo_groups[repo].append(result)

    def _repo_section(results: list[dict]) -> dict:
        resolved = [r for r in results if r["resolved"] is True]
        unresolved = [r for r in results if r["resolved"] is False]
        return {
            "total_instances": len(results),
            "overall": _section(results),
            "resolved": _section(resolved),
            "unresolved": _section(unresolved),
        }

    per_repo = {repo: _repo_section(results) for repo, results in sorted(repo_groups.items())}

    summary = {
        "total_instances": len(per_instance),
        "overall": _section(per_instance),
        "resolved": _section(resolved_results),
        "unresolved": _section(unresolved_results),
    }

    return {
        "summary": summary,
        "per_repo": per_repo,
        "per_instance": per_instance,
    }


def print_summary(result: dict, *, per_repo: bool = False):
    """Print a human-readable summary."""
    s = result["summary"]
    print("Edit Churn Rate Analysis")
    print("=" * 70)
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved']['count']} resolved, {s['unresolved']['count']} unresolved")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} churn_rate={data['avg_churn_rate']:<8.4f} "
              f"writes/file={data['avg_writes_per_file']:<8} "
              f"total_writes={data['avg_total_writes']:<8} "
              f"rewrites={data['avg_rewrites']:<8} "
              f"churned_files={data['avg_churned_file_count']}")

    _row("Overall", s["overall"])
    _row("Resolved", s["resolved"])
    _row("Unresolved", s["unresolved"])

    if per_repo:
        repo_data = result.get("per_repo", {})
        if repo_data:
            print()
            print("Per Repository")
            print("-" * 70)
            for repo, data in repo_data.items():
                count = data["total_instances"]
                print(f"\n{repo} ({count} instances):")
                _row("Overall", data["overall"])
                _row("Resolved", data["resolved"])
                _row("Unresolved", data["unresolved"])

    print()
    print("Use -o <file> to save full per-instance JSON results.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Edit churn rate analysis")
    parser.add_argument("trajectory_dir", help="Directory with benchmark run output")
    parser.add_argument("-o", "--output", help="Write output to a file instead of stdout")
    parser.add_argument("--per-repo", action="store_true", help="Include per-repository breakdown")
    args = parser.parse_args()

    result = analyse_directory(args.trajectory_dir)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"Written to {args.output}")
    else:
        print_summary(result, per_repo=args.per_repo)
