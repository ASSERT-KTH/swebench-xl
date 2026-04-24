"""CLI entry point for the trajectory analysis tool."""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

from traj.loader import load_trajectories


def main():
    parser = argparse.ArgumentParser(
        prog="traj",
        description="Normalise agent trajectories into Read/Write/Explore operations",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- extract ---
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract normalised operations from trajectory files",
    )
    extract_parser.add_argument(
        "path",
        help="Path to a trajectory JSON file, zip archive, or directory of trajectories",
    )
    extract_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )

    # --- analyse ---
    analyse_parser = subparsers.add_parser(
        "analyse",
        help="Run an analysis script on normalised trajectories",
    )
    analyse_parser.add_argument(
        "script",
        help="Name of the analysis script (from traj/scripts/) or path to a .py file",
    )
    analyse_parser.add_argument(
        "path",
        help="Path to a trajectory JSON file, zip archive, or directory of trajectories",
    )
    analyse_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )

    # --- file-recall ---
    file_recall_parser = subparsers.add_parser(
        "file-recall",
        help="Calculate file recall/precision for a benchmark run",
    )
    file_recall_parser.add_argument(
        "trajectory_dir",
        help="Directory containing output zips from a benchmark run",
    )
    file_recall_parser.add_argument(
        "--instance-stats",
        required=True,
        help="Path to instance_stats_output.json with ground-truth source files",
    )
    file_recall_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )

    # --- actions-before-write ---
    abw_parser = subparsers.add_parser(
        "actions-before-write",
        help="Count operations before the first Write action",
    )
    abw_parser.add_argument(
        "trajectory_dir",
        help="Directory containing benchmark run output",
    )
    abw_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )

    # --- subagent-usage ---
    sub_parser = subparsers.add_parser(
        "subagent-usage",
        help="Analyse subagent (task tool) usage in Copilot CLI trajectories",
    )
    sub_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output zips",
    )
    sub_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "extract":
        _cmd_extract(args)
    elif args.command == "analyse":
        _cmd_analyse(args)
    elif args.command == "file-recall":
        _cmd_file_recall(args)
    elif args.command == "actions-before-write":
        _cmd_actions_before_write(args)
    elif args.command == "subagent-usage":
        _cmd_subagent_usage(args)


def _cmd_extract(args):
    results = load_trajectories(args.path)
    output = [r.to_dict() for r in results]

    # Single file -> unwrap from array
    if len(output) == 1:
        output = output[0]

    json_str = json.dumps(output, indent=2)

    if args.output:
        Path(args.output).write_text(json_str)
        print(f"Written to {args.output}")
    else:
        for r in results:
            for op in r.operations:
                print(f"{op.action:<8} {op.path}")


def _cmd_analyse(args):
    results = load_trajectories(args.path)

    # Load the analysis script
    script_mod = _load_script(args.script)
    if not hasattr(script_mod, "run"):
        print(f"Error: script '{args.script}' has no run() function", file=sys.stderr)
        sys.exit(1)

    analysis = script_mod.run(results)
    json_str = json.dumps(analysis, indent=2)

    if args.output:
        Path(args.output).write_text(json_str)
        print(f"Written to {args.output}")
    else:
        print(json_str)


def _cmd_file_recall(args):
    from traj.scripts.file_recall import analyse_directory

    result = analyse_directory(args.trajectory_dir, args.instance_stats)
    json_str = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(json_str)
        print(f"Written to {args.output}")
    else:
        _print_file_recall_summary(result)


def _print_file_recall_summary(result: dict):
    """Print a human-readable summary table to stdout."""
    s = result["summary"]
    excluded = s.get("excluded_files", [])

    print(f"File Recall/Precision Analysis")
    print(f"{'='*60}")
    print(f"Instances: {s['total_instances']} total, "
          f"{s['resolved_count']} resolved, {s['unresolved_count']} unresolved")
    if excluded:
        print(f"Excluded:  {', '.join(excluded)}")
    print()

    def _row(label: str, data: dict):
        print(f"  {label:<14} recall={data['avg_recall']:.4f}  "
              f"precision={data['avg_precision']:.4f}  f1={data['avg_f1']:.4f}")

    for group_name, group_key in [("Overall", "overall"),
                                   ("Resolved", "resolved"),
                                   ("Unresolved", "unresolved")]:
        group = s[group_key]
        count = group.get("count", s["total_instances"])
        print(f"{group_name} ({count}):")
        _row("Write", group["write"])
        _row("Read", group["read"])
        if excluded:
            _row("Write (excl)", group["write_excluding"])
            _row("Read (excl)", group["read_excluding"])
        print()

    print(f"Use -o <file> to save full per-instance JSON results.")


def _cmd_actions_before_write(args):
    from traj.scripts.actions_before_write import analyse_directory, print_summary

    result = analyse_directory(args.trajectory_dir)
    json_str = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(json_str)
        print(f"Written to {args.output}")
    else:
        print_summary(result)


def _cmd_subagent_usage(args):
    from traj.scripts.subagent_usage import (
        analyse_directory, analyse_directories, print_summary,
    )

    dirs = args.trajectory_dirs
    if len(dirs) == 1:
        result = analyse_directory(dirs[0])
        full_result = {"comparison": [result], "runs": [result]}
    else:
        full_result = analyse_directories(dirs)

    if args.output:
        json_str = json.dumps(full_result, indent=2)
        Path(args.output).write_text(json_str)
        print(f"Written to {args.output}")
    else:
        print_summary(full_result)


def _load_script(name: str):
    """Load an analysis script by name or path."""
    # Try as a built-in script first
    try:
        return importlib.import_module(f"traj.scripts.{name}")
    except ImportError:
        pass

    # Try as a file path
    script_path = Path(name)
    if script_path.exists() and script_path.suffix == ".py":
        spec = importlib.util.spec_from_file_location("user_script", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    print(f"Error: could not find script '{name}'", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
