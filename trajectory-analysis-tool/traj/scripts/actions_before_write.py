"""Actions before first Write analysis.

Counts how many operations occur before the agent makes its first Write,
comparing resolved vs unresolved instances.

Usage:
    traj actions-before-write <trajectory_dir>
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from traj.scripts.file_recall import (
    _detect_run_format,
    _collect_instances_zip,
    _collect_instances_dir,
)
from traj.loader import _detect_adapter


def _count_before_first_write(traj_data: list | dict, source_file: str = "") -> dict:
    """Count operations before the first Write action.

    Returns a dict with total ops, actions before first write,
    and a breakdown by action type.
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    total = len(ops)
    before_counts = {"Read": 0, "Write": 0, "Explore": 0, "Other": 0}
    first_write_index = None

    for i, op in enumerate(ops):
        if op.action == "Write":
            first_write_index = i
            break
        before_counts[op.action] = before_counts.get(op.action, 0) + 1

    return {
        "total_operations": total,
        "first_write_at": first_write_index,
        "actions_before_first_write": first_write_index if first_write_index is not None else total,
        "breakdown_before_write": before_counts,
        "has_write": first_write_index is not None,
    }


def analyse_directory(trajectory_dir: str) -> dict:
    """Run actions-before-write analysis on a benchmark run directory."""
    traj_dir = Path(trajectory_dir)
    run_format = _detect_run_format(traj_dir)
    if run_format == "dir":
        instance_data = _collect_instances_dir(traj_dir)
    else:
        instance_data = _collect_instances_zip(traj_dir)

    per_instance = []
    resolved_results = []
    unresolved_results = []

    for instance_id, traj_data, resolved in instance_data:
        metrics = _count_before_first_write(traj_data, instance_id)
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
        return round(sum(r[key] for r in results) / len(results), 2)

    def _section(results: list[dict]) -> dict:
        return {
            "count": len(results),
            "avg_actions_before_first_write": _avg(results, "actions_before_first_write"),
            "avg_total_operations": _avg(results, "total_operations"),
            "instances_without_write": sum(1 for r in results if not r["has_write"]),
        }

    summary = {
        "total_instances": len(per_instance),
        "overall": _section(per_instance),
        "resolved": _section(resolved_results),
        "unresolved": _section(unresolved_results),
    }

    return {
        "summary": summary,
        "per_instance": per_instance,
    }


def print_summary(result: dict):
    """Print a human-readable summary."""
    s = result["summary"]
    print("Actions Before First Write")
    print("=" * 60)
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved']['count']} resolved, {s['unresolved']['count']} unresolved")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} avg_before_write={data['avg_actions_before_first_write']:<8} "
              f"avg_total_ops={data['avg_total_operations']:<8} "
              f"no_write={data['instances_without_write']}")

    _row("Overall", s["overall"])
    _row("Resolved", s["resolved"])
    _row("Unresolved", s["unresolved"])
    print()
    print("Use -o <file> to save full per-instance JSON results.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Actions before first Write analysis")
    parser.add_argument("trajectory_dir", help="Directory with benchmark run output")
    parser.add_argument("-o", "--output", help="Write output to file instead of stdout")
    args = parser.parse_args()

    result = analyse_directory(args.trajectory_dir)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"Written to {args.output}")
    else:
        print_summary(result)
