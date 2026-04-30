"""Exploration breadth/depth analysis for benchmark runs.

Measures how broadly and deeply an agent explores the directory tree:
- Breadth: number of distinct directories touched
- Depth: how deep in the file tree the agent operates (max and average)
- Spread: number of distinct top-level directories (packages/modules) touched

Breakdowns are provided per resolved/unresolved status and per repository.

Usage:
    traj exploration-breadth <trajectory_dir> [-o output.json]
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path, PurePosixPath

from traj.scripts.file_recall import (
    _detect_run_format,
    _collect_instances_zip,
    _collect_instances_dir,
    _collect_instances_output_dir,
    _normalise_path,
)
from traj.loader import _detect_adapter
from traj.scripts import extract_repo


def _compute_exploration_metrics(traj_data: list | dict, source_file: str = "") -> dict:
    """Compute exploration breadth/depth metrics from a single trajectory.

    Returns a dict with:
    - unique_files: number of distinct files touched (Read or Write)
    - unique_dirs: number of distinct directories touched
    - max_depth: deepest directory level reached
    - avg_depth: average depth across all touched files
    - top_level_dirs: list of distinct top-level directories
    - top_level_count: number of distinct top-level directories
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    files: set[str] = set()
    dirs: set[str] = set()
    depths: list[int] = []

    for op in ops:
        if op.action not in ("Read", "Write") or not op.path:
            continue
        normalised = _normalise_path(op.path)
        if not normalised:
            continue

        p = PurePosixPath(normalised)
        # Count depth as number of path components (file itself excluded)
        parts = p.parts
        depth = len(parts) - 1  # directory depth (0 = root-level file)

        files.add(normalised)
        depths.append(depth)

        # Collect all ancestor directories
        for i in range(1, len(parts)):
            dirs.add(str(PurePosixPath(*parts[:i])))

    top_level = sorted({PurePosixPath(f).parts[0] for f in files if len(PurePosixPath(f).parts) > 1})

    return {
        "unique_files": len(files),
        "unique_dirs": len(dirs),
        "max_depth": max(depths) if depths else 0,
        "avg_depth": round(sum(depths) / len(depths), 2) if depths else 0.0,
        "top_level_dirs": top_level,
        "top_level_count": len(top_level),
    }


def analyse_directory(trajectory_dir: str) -> dict:
    """Run exploration breadth/depth analysis on a benchmark run directory."""
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
        metrics = _compute_exploration_metrics(traj_data, instance_id)
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
            "avg_unique_files": _avg(results, "unique_files"),
            "avg_unique_dirs": _avg(results, "unique_dirs"),
            "avg_max_depth": _avg(results, "max_depth"),
            "avg_avg_depth": _avg(results, "avg_depth"),
            "avg_top_level_count": _avg(results, "top_level_count"),
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
    print("Exploration Breadth/Depth Analysis")
    print("=" * 70)
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved']['count']} resolved, {s['unresolved']['count']} unresolved")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} files={data['avg_unique_files']:<8} "
              f"dirs={data['avg_unique_dirs']:<8} "
              f"max_depth={data['avg_max_depth']:<8} "
              f"avg_depth={data['avg_avg_depth']:<8} "
              f"top_level={data['avg_top_level_count']}")

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

    parser = argparse.ArgumentParser(description="Exploration breadth/depth analysis")
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
