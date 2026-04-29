"""Read-to-write conversion analysis for benchmark runs.

Analyses the relationship between reading and writing ground-truth files:
- Read-to-write conversion: % of correctly read files that are later written
- Avg steps from first read to first write per ground-truth file
- Read-only fraction: ground-truth files read but never written (missed edits)
- Write-without-read fraction: ground-truth files written without prior read (blind edits)

Requires --instance-stats with ground-truth source files.

Usage:
    traj read-to-write <trajectory_dir> \
        --instance-stats <instance_stats.json>
"""
from __future__ import annotations

import json
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


def _compute_read_to_write(
    traj_data: list | dict,
    ground_truth: set[str],
    source_file: str = "",
) -> dict:
    """Compute read-to-write conversion metrics for ground-truth files.

    Returns a dict with per-instance metrics.
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    # Track first read and first write step for each ground-truth file
    first_read: dict[str, int] = {}
    first_write: dict[str, int] = {}

    for i, op in enumerate(ops):
        if op.action not in ("Read", "Write") or not op.path:
            continue
        normalised = _normalise_path(op.path)
        if not normalised or normalised.endswith("/"):
            continue
        if normalised not in ground_truth:
            continue

        if op.action == "Read" and normalised not in first_read:
            first_read[normalised] = i
        elif op.action == "Write" and normalised not in first_write:
            first_write[normalised] = i

    gt_read = set(first_read.keys())
    gt_written = set(first_write.keys())

    # Files read then written
    read_then_written = {f for f in gt_read & gt_written if first_read[f] < first_write[f]}
    # Files read but never written (missed edits)
    read_only = gt_read - gt_written
    # Files written without prior read (blind edits)
    write_without_read = {f for f in gt_written if f not in first_read or first_read[f] >= first_write[f]}

    # Steps from first read to first write for files that were read then written
    steps = []
    for f in read_then_written:
        steps.append(first_write[f] - first_read[f])
    avg_steps = round(sum(steps) / len(steps), 2) if steps else 0.0

    gt_count = len(ground_truth)
    read_count = len(gt_read)
    written_count = len(gt_written)

    return {
        "ground_truth_count": gt_count,
        "gt_files_read": read_count,
        "gt_files_written": written_count,
        "read_then_written": len(read_then_written),
        "conversion_rate": round(len(read_then_written) / read_count, 4) if read_count > 0 else 0.0,
        "avg_steps_read_to_write": avg_steps,
        "read_only_count": len(read_only),
        "read_only_fraction": round(len(read_only) / gt_count, 4) if gt_count > 0 else 0.0,
        "write_without_read_count": len(write_without_read),
        "write_without_read_fraction": round(len(write_without_read) / gt_count, 4) if gt_count > 0 else 0.0,
        "read_only_files": sorted(read_only),
        "write_without_read_files": sorted(write_without_read),
    }


def analyse_directory(trajectory_dir: str, instance_stats_path: str) -> dict:
    """Run read-to-write analysis on a benchmark run directory."""
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

        metrics = _compute_read_to_write(traj_data, ground_truth, instance_id)
        result = {
            "instance_id": canonical_id,
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
            "avg_conversion_rate": _avg(results, "conversion_rate"),
            "avg_steps_read_to_write": _avg(results, "avg_steps_read_to_write"),
            "avg_read_only_fraction": _avg(results, "read_only_fraction"),
            "avg_write_without_read_fraction": _avg(results, "write_without_read_fraction"),
            "avg_gt_files_read": _avg(results, "gt_files_read"),
            "avg_gt_files_written": _avg(results, "gt_files_written"),
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
    print("Read-to-Write Conversion Analysis")
    print("=" * 75)
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved']['count']} resolved, {s['unresolved']['count']} unresolved")
    if s["skipped_no_ground_truth"]:
        print(f"Skipped:   {s['skipped_no_ground_truth']} (no ground-truth)")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} "
              f"conversion={data['avg_conversion_rate']:<8.4f} "
              f"steps={data['avg_steps_read_to_write']:<8} "
              f"read_only={data['avg_read_only_fraction']:<8.4f} "
              f"blind_write={data['avg_write_without_read_fraction']:.4f}")

    _row("Overall", s["overall"])
    _row("Resolved", s["resolved"])
    _row("Unresolved", s["unresolved"])

    if per_repo:
        repo_data = result.get("per_repo", {})
        if repo_data:
            print()
            print("Per Repository")
            print("-" * 75)
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

    parser = argparse.ArgumentParser(description="Read-to-write conversion analysis")
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
