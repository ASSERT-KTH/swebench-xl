"""Time-to-first-correct-file analysis for benchmark runs.

Measures how many operations occur before the agent first touches a
ground-truth source file (from instance stats), for both Read and Write
actions separately.

A low count means the agent quickly navigates to the right area of the
codebase; a high count suggests it wanders before finding the relevant files.

Requires --instance-stats with ground-truth source files.

Usage:
    traj time-to-correct <trajectory_dir> \
        --instance-stats <instance_stats.json>
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from traj.scripts.file_recall import (
    _detect_run_format,
    _collect_instances_zip,
    _collect_instances_dir,
    _normalise_path,
)
from traj.loader import _detect_adapter
from traj.scripts import extract_repo


def _compute_time_to_correct(
    traj_data: list | dict,
    ground_truth: set[str],
    source_file: str = "",
) -> dict:
    """Compute how many operations before the agent first touches a correct file.

    Returns a dict with:
    - total_operations: total number of operations
    - first_correct_read: step index of first Read on a ground-truth file (None if never)
    - first_correct_write: step index of first Write on a ground-truth file (None if never)
    - first_correct_any: step index of first Read or Write on a ground-truth file
    - ops_before_correct_read: number of ops before first correct Read
    - ops_before_correct_write: number of ops before first correct Write
    - ops_before_correct_any: number of ops before first correct touch
    - first_correct_read_file: the file path (None if never)
    - first_correct_write_file: the file path (None if never)
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    total = len(ops)
    first_read = None
    first_write = None
    first_read_file = None
    first_write_file = None

    for i, op in enumerate(ops):
        if op.action not in ("Read", "Write") or not op.path:
            continue
        normalised = _normalise_path(op.path)
        if not normalised or normalised.endswith("/"):
            continue
        if normalised not in ground_truth:
            continue

        if op.action == "Read" and first_read is None:
            first_read = i
            first_read_file = normalised
        elif op.action == "Write" and first_write is None:
            first_write = i
            first_write_file = normalised

        if first_read is not None and first_write is not None:
            break

    first_any = None
    if first_read is not None and first_write is not None:
        first_any = min(first_read, first_write)
    elif first_read is not None:
        first_any = first_read
    elif first_write is not None:
        first_any = first_write

    return {
        "total_operations": total,
        "first_correct_read": first_read,
        "first_correct_write": first_write,
        "first_correct_any": first_any,
        "ops_before_correct_read": first_read if first_read is not None else total,
        "ops_before_correct_write": first_write if first_write is not None else total,
        "ops_before_correct_any": first_any if first_any is not None else total,
        "first_correct_read_file": first_read_file,
        "first_correct_write_file": first_write_file,
        "found_correct_read": first_read is not None,
        "found_correct_write": first_write is not None,
    }


def analyse_directory(trajectory_dir: str, instance_stats_path: str) -> dict:
    """Run time-to-first-correct-file analysis on a benchmark run directory."""
    # Load instance stats
    with open(instance_stats_path) as f:
        stats_data = json.load(f)

    instances = stats_data if isinstance(stats_data, list) else stats_data.get("instances", [])
    source_files_map: dict[str, list[str]] = {}
    canonical_id_map: dict[str, str] = {}
    for inst in instances:
        iid = inst["instance_id"]
        source_files_map[iid] = inst.get("source_files", [])
        canonical_id_map[iid.lower()] = iid

    traj_dir = Path(trajectory_dir)
    run_format = _detect_run_format(traj_dir)
    if run_format == "dir":
        instance_data = _collect_instances_dir(traj_dir)
    else:
        instance_data = _collect_instances_zip(traj_dir)

    per_instance = []
    resolved_results = []
    unresolved_results = []
    skipped = []

    for instance_id, traj_data, resolved in instance_data:
        canonical_id = canonical_id_map.get(instance_id.lower(), instance_id)
        ground_truth = set(source_files_map.get(canonical_id, []))
        if not ground_truth:
            skipped.append(instance_id)
            continue

        metrics = _compute_time_to_correct(traj_data, ground_truth, instance_id)
        result = {
            "instance_id": canonical_id,
            "resolved": resolved,
            "ground_truth_count": len(ground_truth),
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
        return round(sum(r[key] for r in results) / len(results), 2)

    def _section(results: list[dict]) -> dict:
        return {
            "count": len(results),
            "avg_ops_before_correct_read": _avg(results, "ops_before_correct_read"),
            "avg_ops_before_correct_write": _avg(results, "ops_before_correct_write"),
            "avg_ops_before_correct_any": _avg(results, "ops_before_correct_any"),
            "avg_total_operations": _avg(results, "total_operations"),
            "never_found_correct_read": sum(1 for r in results if not r["found_correct_read"]),
            "never_found_correct_write": sum(1 for r in results if not r["found_correct_write"]),
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

    if skipped:
        ellipsis = "..." if len(skipped) > 5 else ""
        print(f"Warning: {len(skipped)} instance(s) skipped (no ground-truth): "
              f"{', '.join(skipped[:5])}{ellipsis}")

    summary = {
        "total_instances": len(per_instance),
        "skipped_no_ground_truth": len(skipped),
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
    print("Time to First Correct File")
    print("=" * 70)
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved']['count']} resolved, {s['unresolved']['count']} unresolved")
    if s["skipped_no_ground_truth"]:
        print(f"Skipped:   {s['skipped_no_ground_truth']} (no ground-truth)")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} "
              f"any={data['avg_ops_before_correct_any']:<8} "
              f"read={data['avg_ops_before_correct_read']:<8} "
              f"write={data['avg_ops_before_correct_write']:<8} "
              f"total_ops={data['avg_total_operations']:<8} "
              f"never_read={data['never_found_correct_read']} "
              f"never_write={data['never_found_correct_write']}")

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

    parser = argparse.ArgumentParser(description="Time to first correct file analysis")
    parser.add_argument("trajectory_dir", help="Directory with benchmark run output")
    parser.add_argument("--instance-stats", required=True,
                        help="Path to instance_stats_output.json")
    parser.add_argument("-o", "--output", help="Write output to a file instead of stdout")
    parser.add_argument("--per-repo", action="store_true", help="Include per-repository breakdown")
    args = parser.parse_args()

    result = analyse_directory(args.trajectory_dir, args.instance_stats)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"Written to {args.output}")
    else:
        print_summary(result, per_repo=args.per_repo)
