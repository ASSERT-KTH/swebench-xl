"""Re-read rate analysis for benchmark runs.

Measures how often an agent reads the same file multiple times, computing:
- Re-read rate: fraction of Read operations targeting an already-read file
- Avg reads per file: average number of times each unique file is read

Breakdowns are provided per resolved/unresolved status and per repository.

Usage:
    traj reread-rate <trajectory_dir> [-o output.json]
"""
from __future__ import annotations

import json
import os
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


def _compute_reread_metrics(traj_data: list | dict, source_file: str = "") -> dict:
    """Compute re-read metrics from a single trajectory.

    Returns a dict with:
    - total_reads: total number of Read operations
    - unique_files_read: number of distinct files read
    - rereads: number of reads that target an already-read file
    - reread_rate: rereads / total_reads (0.0 if no reads)
    - avg_reads_per_file: total_reads / unique_files_read
    - read_counts: dict mapping file -> number of times read
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    read_counts: Counter[str] = Counter()
    for op in ops:
        if op.action != "Read" or not op.path:
            continue
        normalised = _normalise_path(op.path)
        if not normalised or normalised.endswith("/"):
            continue
        # Only count actual files (must have an extension in the last segment)
        if "." not in normalised.split("/")[-1]:
            continue
        read_counts[normalised] += 1

    total_reads = sum(read_counts.values())
    unique_files = len(read_counts)
    rereads = total_reads - unique_files  # each file's first read is not a re-read

    return {
        "total_reads": total_reads,
        "unique_files_read": unique_files,
        "rereads": rereads,
        "reread_rate": round(rereads / total_reads, 4) if total_reads > 0 else 0.0,
        "avg_reads_per_file": round(total_reads / unique_files, 2) if unique_files > 0 else 0.0,
        "read_counts": dict(read_counts.most_common()),
    }


def analyse_directory(trajectory_dir: str) -> dict:
    """Run re-read rate analysis on a benchmark run directory."""
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
        metrics = _compute_reread_metrics(traj_data, instance_id)
        # Don't include per-file breakdown in the instance result (too verbose)
        read_counts = metrics.pop("read_counts")
        most_reread = []
        for f, count in sorted(read_counts.items(), key=lambda x: -x[1])[:5]:
            if count > 1:
                most_reread.append({"file": f, "reads": count})

        result = {
            "instance_id": instance_id,
            "resolved": resolved,
            **metrics,
            "most_reread_files": most_reread,
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
            "avg_reread_rate": _avg(results, "reread_rate"),
            "avg_reads_per_file": _avg(results, "avg_reads_per_file"),
            "avg_total_reads": _avg(results, "total_reads"),
            "avg_unique_files_read": _avg(results, "unique_files_read"),
            "avg_rereads": _avg(results, "rereads"),
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
    print("Re-read Rate Analysis")
    print("=" * 60)
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved']['count']} resolved, {s['unresolved']['count']} unresolved")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} reread_rate={data['avg_reread_rate']:<8.4f} "
              f"reads/file={data['avg_reads_per_file']:<8} "
              f"total_reads={data['avg_total_reads']:<8} "
              f"rereads={data['avg_rereads']}")

    _row("Overall", s["overall"])
    _row("Resolved", s["resolved"])
    _row("Unresolved", s["unresolved"])

    if per_repo:
        repo_data = result.get("per_repo", {})
        if repo_data:
            print()
            print("Per Repository")
            print("-" * 60)
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

    parser = argparse.ArgumentParser(description="Re-read rate analysis")
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
