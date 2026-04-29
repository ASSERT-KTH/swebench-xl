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
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
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
    file_recall_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
    )

    # --- actions-before-write ---
    abw_parser = subparsers.add_parser(
        "actions-before-write",
        help="Count operations before the first Write action",
    )
    abw_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
    )
    abw_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    abw_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
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

    # --- reread-rate ---
    rr_parser = subparsers.add_parser(
        "reread-rate",
        help="Analyse how often an agent re-reads the same file",
    )
    rr_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
    )
    rr_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    rr_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
    )

    # --- exploration-breadth ---
    eb_parser = subparsers.add_parser(
        "exploration-breadth",
        help="Analyse how broadly and deeply an agent explores the directory tree",
    )
    eb_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
    )
    eb_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    eb_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
    )

    # --- edit-churn ---
    ec_parser = subparsers.add_parser(
        "edit-churn",
        help="Analyse how often an agent rewrites the same file",
    )
    ec_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
    )
    ec_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    ec_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
    )

    # --- time-to-correct ---
    ttc_parser = subparsers.add_parser(
        "time-to-correct",
        help="Count operations before the agent first touches a correct file",
    )
    ttc_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
    )
    ttc_parser.add_argument(
        "--instance-stats",
        required=True,
        help="Path to instance_stats_output.json with ground-truth source files",
    )
    ttc_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    ttc_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
    )

    # --- collect ---
    collect_parser = subparsers.add_parser(
        "collect",
        help="Run all analyses and export a flat per-instance CSV",
    )
    collect_parser.add_argument(
        "trajectory_dir",
        help="Directory containing benchmark run output (zips or instance dirs)",
    )
    collect_parser.add_argument(
        "--agent",
        required=True,
        help="Agent identifier (e.g. copilot-cli-opus-4.6)",
    )
    collect_parser.add_argument(
        "--benchmark",
        required=True,
        help="Benchmark identifier (e.g. swebench-verified)",
    )
    collect_parser.add_argument(
        "--size-metrics",
        required=True,
        help="Path to CSV with per-instance size metrics (source_code_files, etc.)",
    )
    collect_parser.add_argument(
        "--instance-stats",
        default=None,
        help="Path to instance_stats_output.json (optional; file_recall/time_to_correct/read_to_write columns will be NaN if omitted)",
    )
    collect_parser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to output CSV file",
    )
    collect_parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing CSV instead of overwriting",
    )

    # --- read-to-write ---
    rtw_parser = subparsers.add_parser(
        "read-to-write",
        help="Analyse read-to-write conversion for ground-truth files",
    )
    rtw_parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output",
    )
    rtw_parser.add_argument(
        "--instance-stats",
        required=True,
        help="Path to instance_stats_output.json with ground-truth source files",
    )
    rtw_parser.add_argument(
        "-o", "--output",
        help="Write output to a file instead of stdout",
    )
    rtw_parser.add_argument(
        "--per-repo",
        action="store_true",
        help="Include per-repository breakdown in output",
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
    elif args.command == "reread-rate":
        _cmd_reread_rate(args)
    elif args.command == "exploration-breadth":
        _cmd_exploration_breadth(args)
    elif args.command == "edit-churn":
        _cmd_edit_churn(args)
    elif args.command == "time-to-correct":
        _cmd_time_to_correct(args)
    elif args.command == "read-to-write":
        _cmd_read_to_write(args)
    elif args.command == "collect":
        _cmd_collect(args)


def _print_run_header(directory: str, index: int, total: int):
    """Print a header separating output from different run directories."""
    name = Path(directory).name
    print(f"\n{'#' * 70}")
    print(f"# Run {index}/{total}: {name}")
    print(f"# {directory}")
    print(f"{'#' * 70}\n")


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

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir, args.instance_stats))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            _print_file_recall_summary(result, per_repo=args.per_repo)


def _print_file_recall_summary(result: dict, *, per_repo: bool = False):
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

    # Per-repo breakdown
    if per_repo:
        per_repo_data = result.get("per_repo", {})
        if per_repo_data:
            print(f"Per Repository")
            print(f"{'-'*60}")
            for repo, repo_data in per_repo_data.items():
                count = repo_data["total_instances"]
                resolved = repo_data["resolved_count"]
                print(f"\n{repo} ({count} instances, {resolved} resolved):")
                _row("Write", repo_data["overall"]["write"])
                _row("Read", repo_data["overall"]["read"])

    print()
    print(f"Use -o <file> to save full per-instance JSON results.")


def _cmd_actions_before_write(args):
    from traj.scripts.actions_before_write import analyse_directory, print_summary

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            print_summary(result, per_repo=args.per_repo)


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


def _cmd_reread_rate(args):
    from traj.scripts.reread_rate import analyse_directory, print_summary

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            print_summary(result, per_repo=args.per_repo)


def _cmd_exploration_breadth(args):
    from traj.scripts.exploration_breadth import analyse_directory, print_summary

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            print_summary(result, per_repo=args.per_repo)


def _cmd_edit_churn(args):
    from traj.scripts.edit_churn import analyse_directory, print_summary

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            print_summary(result, per_repo=args.per_repo)


def _cmd_time_to_correct(args):
    from traj.scripts.time_to_correct import analyse_directory, print_summary

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir, args.instance_stats))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            print_summary(result, per_repo=args.per_repo)


def _cmd_read_to_write(args):
    from traj.scripts.read_to_write import analyse_directory, print_summary

    results = []
    for traj_dir in args.trajectory_dirs:
        results.append(analyse_directory(traj_dir, args.instance_stats))

    if args.output:
        output = results if len(results) > 1 else results[0]
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Written to {args.output}")
    else:
        for i, result in enumerate(results):
            if len(results) > 1:
                _print_run_header(args.trajectory_dirs[i], i + 1, len(results))
            print_summary(result, per_repo=args.per_repo)


def _cmd_collect(args):
    from traj.scripts.collect import collect, write_csv

    rows = collect(
        run_dir=args.trajectory_dir,
        agent=args.agent,
        benchmark=args.benchmark,
        size_metrics_csv=args.size_metrics,
        instance_stats=args.instance_stats,
    )
    write_csv(rows, args.output, append=args.append)


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
