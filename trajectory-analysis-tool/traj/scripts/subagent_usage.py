"""Subagent usage analysis for Copilot CLI trajectories.

Analyses how frequently the Copilot CLI delegates work to subagents via the
``task`` tool, broken down by agent type, mode, and resolved/unresolved status.

Supports comparing multiple run directories side-by-side.

Usage:
    traj subagent-usage <dir1> [<dir2> ...] [-o output.json]
"""
from __future__ import annotations

import json
import os
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from traj.scripts import extract_repo


def _load_from_zip(zip_path: str) -> tuple[dict | None, bool | None]:
    """Load trajectory.json and resolved status from a zip archive."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            traj_data = None
            for candidate in [
                "output/trajectories/trajectory.json",
                "trajectory.json",
            ]:
                if candidate in names:
                    traj_data = json.loads(zf.read(candidate))
                    break
            if traj_data is None:
                return None, None

            resolved = None
            if "output/eval.json" in names:
                eval_data = json.loads(zf.read("output/eval.json"))
                for val in eval_data.values():
                    if isinstance(val, dict):
                        resolved = val.get("resolved")
                        break

            return traj_data, resolved
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: failed to read {zip_path}: {e}")
        return None, None


def _load_from_output_dir(output_dir: str) -> tuple[dict | None, bool | None]:
    """Load trajectory.json and resolved status from an unzipped output directory."""
    traj_path = os.path.join(output_dir, "output", "trajectories", "trajectory.json")
    eval_path = os.path.join(output_dir, "output", "eval.json")

    traj_data = None
    resolved = None

    try:
        if os.path.exists(traj_path):
            with open(traj_path) as f:
                traj_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: failed to read {traj_path}: {e}")

    try:
        if os.path.exists(eval_path):
            with open(eval_path) as f:
                eval_data = json.load(f)
            for val in eval_data.values():
                if isinstance(val, dict):
                    resolved = val.get("resolved")
                    break
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: failed to read {eval_path}: {e}")

    return traj_data, resolved


def _extract_instance_id(name: str) -> str:
    """Extract a readable instance id from a zip filename or output directory name."""
    import re
    basename = name.removesuffix(".zip")
    # Strip common prefixes and -output suffix
    basename = re.sub(r'-output$', '', basename)
    # Try to find owner__repo-id pattern
    match = re.search(r'([a-zA-Z0-9_-]+__[a-zA-Z0-9_-]+-[a-zA-Z0-9_-]+)', basename)
    if match:
        return match.group(1)
    return basename


def _analyse_trajectory(traj_data: dict) -> list[dict]:
    """Extract all task tool calls from an ATIF trajectory.

    Returns a list of dicts, one per subagent invocation.
    """
    invocations = []
    if not isinstance(traj_data, dict) or "steps" not in traj_data:
        return invocations

    for step in traj_data.get("steps", []):
        for tc in step.get("tool_calls", []):
            if tc.get("function_name") != "task":
                continue
            args = tc.get("arguments", {})
            invocations.append({
                "agent_type": args.get("agent_type", "unknown"),
                "mode": args.get("mode", "sync"),
                "model": args.get("model") or "(default)",
                "name": args.get("name", ""),
                "description": args.get("description", ""),
            })
    return invocations


def analyse_directory(trajectory_dir: str) -> dict:
    """Analyse subagent usage for a single run directory."""
    traj_dir = Path(trajectory_dir)

    # Collect instances from zips and/or unzipped output directories
    entries: list[tuple[str, str]] = []  # (name, source_type)
    zip_files = sorted(traj_dir.glob("*-output.zip"))
    if not zip_files:
        zip_files = sorted(traj_dir.glob("*.zip"))
    for zf in zip_files:
        entries.append((str(zf), "zip"))

    # Also check for unzipped output directories
    for entry in sorted(traj_dir.iterdir()):
        if entry.is_dir() and entry.name.endswith("-output"):
            if (entry / "output" / "trajectories" / "trajectory.json").exists():
                entries.append((str(entry), "output_dir"))

    per_instance = []
    agent_type_counts = Counter()
    mode_counts = Counter()
    model_counts = Counter()
    total_invocations = 0
    instances_with_subagent = 0
    resolved_with = 0
    resolved_without = 0
    unresolved_with = 0
    unresolved_without = 0

    for path, source_type in entries:
        name = os.path.basename(path)
        instance_id = _extract_instance_id(name)

        if source_type == "zip":
            traj_data, resolved = _load_from_zip(path)
        else:
            traj_data, resolved = _load_from_output_dir(path)

        if traj_data is None:
            continue

        invocations = _analyse_trajectory(traj_data)
        count = len(invocations)
        total_invocations += count

        types = Counter(inv["agent_type"] for inv in invocations)
        modes = Counter(inv["mode"] for inv in invocations)
        models = Counter(inv["model"] for inv in invocations)

        for k, v in types.items():
            agent_type_counts[k] += v
        for k, v in modes.items():
            mode_counts[k] += v
        for k, v in models.items():
            model_counts[k] += v

        has_subagent = count > 0
        if has_subagent:
            instances_with_subagent += 1

        if resolved is True:
            if has_subagent:
                resolved_with += 1
            else:
                resolved_without += 1
        elif resolved is False:
            if has_subagent:
                unresolved_with += 1
            else:
                unresolved_without += 1

        per_instance.append({
            "instance_id": instance_id,
            "resolved": resolved,
            "subagent_count": count,
            "agent_types": dict(types),
            "modes": dict(modes),
            "models": dict(models),
            "invocations": invocations,
        })

    total_instances = len(per_instance)
    counts_list = [inst["subagent_count"] for inst in per_instance]
    nonzero = [c for c in counts_list if c > 0]

    # Group by repo
    repo_groups: dict[str, list[dict]] = defaultdict(list)
    for inst in per_instance:
        repo = extract_repo(inst["instance_id"])
        repo_groups[repo].append(inst)

    def _repo_summary(instances: list[dict]) -> dict:
        total = len(instances)
        with_sub = sum(1 for i in instances if i["subagent_count"] > 0)
        all_counts = [i["subagent_count"] for i in instances]
        nz = [c for c in all_counts if c > 0]
        r_with = sum(1 for i in instances if i["resolved"] is True and i["subagent_count"] > 0)
        r_without = sum(1 for i in instances if i["resolved"] is True and i["subagent_count"] == 0)
        u_with = sum(1 for i in instances if i["resolved"] is False and i["subagent_count"] > 0)
        u_without = sum(1 for i in instances if i["resolved"] is False and i["subagent_count"] == 0)
        type_counts = Counter()
        for i in instances:
            for k, v in i["agent_types"].items():
                type_counts[k] += v
        return {
            "total_instances": total,
            "instances_with_subagent": with_sub,
            "pct_with_subagent": round(100.0 * with_sub / total, 1) if total else 0,
            "total_invocations": sum(all_counts),
            "avg_per_instance": round(sum(all_counts) / total, 2) if total else 0,
            "avg_when_used": round(sum(nz) / len(nz), 2) if nz else 0,
            "max_per_instance": max(all_counts) if all_counts else 0,
            "agent_type_counts": dict(type_counts),
            "resolved_with_subagent": r_with,
            "resolved_without_subagent": r_without,
            "unresolved_with_subagent": u_with,
            "unresolved_without_subagent": u_without,
        }

    per_repo = {repo: _repo_summary(instances) for repo, instances in sorted(repo_groups.items())}

    return {
        "directory": str(traj_dir),
        "label": traj_dir.name,
        "total_instances": total_instances,
        "instances_with_subagent": instances_with_subagent,
        "pct_with_subagent": round(100.0 * instances_with_subagent / total_instances, 1) if total_instances else 0,
        "total_invocations": total_invocations,
        "avg_per_instance": round(total_invocations / total_instances, 2) if total_instances else 0,
        "avg_when_used": round(sum(nonzero) / len(nonzero), 2) if nonzero else 0,
        "max_per_instance": max(counts_list) if counts_list else 0,
        "agent_type_counts": dict(agent_type_counts),
        "mode_counts": dict(mode_counts),
        "model_counts": dict(model_counts),
        "resolved_with_subagent": resolved_with,
        "resolved_without_subagent": resolved_without,
        "unresolved_with_subagent": unresolved_with,
        "unresolved_without_subagent": unresolved_without,
        "per_repo": per_repo,
        "per_instance": per_instance,
    }


def analyse_directories(dirs: list[str]) -> dict:
    """Analyse and compare subagent usage across multiple run directories."""
    runs = []
    for d in dirs:
        runs.append(analyse_directory(d))

    comparison = []
    for run in runs:
        comparison.append({
            "label": run["label"],
            "total_instances": run["total_instances"],
            "instances_with_subagent": run["instances_with_subagent"],
            "pct_with_subagent": run["pct_with_subagent"],
            "total_invocations": run["total_invocations"],
            "avg_per_instance": run["avg_per_instance"],
            "avg_when_used": run["avg_when_used"],
            "max_per_instance": run["max_per_instance"],
            "agent_type_counts": run["agent_type_counts"],
            "resolved_with_subagent": run["resolved_with_subagent"],
            "resolved_without_subagent": run["resolved_without_subagent"],
            "unresolved_with_subagent": run["unresolved_with_subagent"],
            "unresolved_without_subagent": run["unresolved_without_subagent"],
        })

    return {
        "comparison": comparison,
        "runs": runs,
    }


def print_summary(result: dict):
    """Print a human-readable comparison table."""
    comparison = result.get("comparison", [])
    if not comparison:
        # Single-directory result
        comparison = [result]

    print("Subagent Usage Analysis (Copilot CLI)")
    print("=" * 80)
    print()

    # Header
    labels = [r["label"] for r in comparison]
    col_w = max(20, *(len(l) + 2 for l in labels))
    header = f"{'Metric':<34}" + "".join(f"{l:<{col_w}}" for l in labels)
    print(header)
    print("-" * len(header))

    def _row(label: str, key: str, fmt: str = ""):
        vals = []
        for r in comparison:
            v = r.get(key, "")
            if fmt == "pct":
                vals.append(f"{v}%")
            else:
                vals.append(str(v))
        print(f"{label:<34}" + "".join(f"{v:<{col_w}}" for v in vals))

    _row("Total instances", "total_instances")
    _row("Instances with subagent", "instances_with_subagent")
    _row("% with subagent", "pct_with_subagent", "pct")
    _row("Total subagent invocations", "total_invocations")
    _row("Avg invocations / instance", "avg_per_instance")
    _row("Avg invocations (when used)", "avg_when_used")
    _row("Max invocations / instance", "max_per_instance")
    print()

    # Agent type breakdown
    all_types = set()
    for r in comparison:
        all_types.update(r.get("agent_type_counts", {}).keys())
    if all_types:
        print("Agent type breakdown:")
        for at in sorted(all_types):
            vals = [str(r.get("agent_type_counts", {}).get(at, 0)) for r in comparison]
            print(f"  {at:<32}" + "".join(f"{v:<{col_w}}" for v in vals))
        print()

    # Resolved vs unresolved
    print("Resolution breakdown:")
    _row("  Resolved + subagent", "resolved_with_subagent")
    _row("  Resolved − subagent", "resolved_without_subagent")
    _row("  Unresolved + subagent", "unresolved_with_subagent")
    _row("  Unresolved − subagent", "unresolved_without_subagent")

    # Resolution rates
    print()
    print("Resolution rates:")
    for r in comparison:
        rw = r["resolved_with_subagent"]
        uw = r["unresolved_with_subagent"]
        rwo = r["resolved_without_subagent"]
        uwo = r["unresolved_without_subagent"]
        rate_with = round(100.0 * rw / (rw + uw), 1) if (rw + uw) > 0 else 0
        rate_without = round(100.0 * rwo / (rwo + uwo), 1) if (rwo + uwo) > 0 else 0
        print(f"  {r['label']}:")
        print(f"    With subagent:    {rate_with}% ({rw}/{rw+uw})")
        print(f"    Without subagent: {rate_without}% ({rwo}/{rwo+uwo})")

    print()
    print("Use -o <file> to save full per-instance JSON results.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Subagent usage analysis for Copilot CLI")
    parser.add_argument(
        "trajectory_dirs",
        nargs="+",
        help="One or more directories containing benchmark run output zips",
    )
    parser.add_argument("-o", "--output", help="Write JSON output to file")
    args = parser.parse_args()

    if len(args.trajectory_dirs) == 1:
        result = analyse_directory(args.trajectory_dirs[0])
        full_result = {"comparison": [result], "runs": [result]}
    else:
        full_result = analyse_directories(args.trajectory_dirs)

    if args.output:
        Path(args.output).write_text(json.dumps(full_result, indent=2))
        print(f"Written to {args.output}")
    else:
        print_summary(full_result)
