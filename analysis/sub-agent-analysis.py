#!/usr/bin/env python3
"""
Analyze sub-agent usage in Claude Code trajectories.

Reads zipped trajectory outputs from a directory and produces statistics on:
- How many sub-agents are summoned per instance
- How many steps each sub-agent takes
- Aggregate statistics across the full run
"""

import argparse
import glob
import json
import os
import statistics
import sys
import zipfile
from collections import Counter, defaultdict


def extract_instance_id(zip_path: str) -> str:
    """Extract instance ID from zip filename."""
    basename = os.path.basename(zip_path)
    # Pattern: swebench-xl-v1.eval.x86_64.<instance_id>-output.zip
    return (
        basename.replace("swebench-xl-v1.eval.x86_64.", "")
        .replace("-output.zip", "")
    )


def parse_agent_log(zf: zipfile.ZipFile) -> list[dict]:
    """Parse agent.log from a zip file into structured message dicts."""
    with zf.open("output/agent.log") as f:
        lines = f.read().decode("utf-8").splitlines()

    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def analyze_trajectory(zip_path: str) -> dict | None:
    """Analyze a single trajectory zip for sub-agent usage."""
    instance_id = extract_instance_id(zip_path)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            messages = parse_agent_log(zf)
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError) as e:
        print(f"  WARN: Could not read agent.log for {instance_id}: {e}", file=sys.stderr)
        return None

    # Extract tool_use calls from log messages, tracking parent_tool_use_id
    agent_calls = []
    subagent_steps_by_parent = defaultdict(list)
    main_tool_calls = 0
    total_tool_calls = 0

    for msg in messages:
        parent_id = msg.get("parent_tool_use_id")
        inner = msg.get("message", {})
        content = inner.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue

            total_tool_calls += 1
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})

            if tool_name == "Agent":
                agent_calls.append({
                    "subagent_type": tool_input.get("subagent_type", "unknown"),
                    "description": tool_input.get("description", ""),
                    "tool_call_id": block.get("id", ""),
                })
            elif parent_id:
                subagent_steps_by_parent[parent_id].append({
                    "tool": tool_name,
                    "parent_id": parent_id,
                })
            else:
                main_tool_calls += 1

    # Match agent calls to their sub-agent steps
    subagent_details = []
    for agent_call in agent_calls:
        tcid = agent_call["tool_call_id"]
        steps = subagent_steps_by_parent.get(tcid, [])
        tool_counts = Counter(s["tool"] for s in steps)

        subagent_details.append({
            "subagent_type": agent_call["subagent_type"],
            "description": agent_call["description"],
            "num_steps": len(steps),
            "tools_used": dict(tool_counts),
        })

    total_subagent_steps = sum(len(v) for v in subagent_steps_by_parent.values())
    # main_tool_calls excludes Agent calls themselves; add them back for total main steps
    main_agent_steps = main_tool_calls + len(agent_calls)

    return {
        "instance_id": instance_id,
        "total_steps": total_tool_calls,
        "main_agent_steps": main_agent_steps,
        "num_subagent_calls": len(agent_calls),
        "total_subagent_steps": total_subagent_steps,
        "subagents": subagent_details,
    }


def compute_aggregate_stats(results: list[dict]) -> dict:
    """Compute aggregate statistics across all instances."""
    num_instances = len(results)
    subagent_counts = [r["num_subagent_calls"] for r in results]
    subagent_step_counts = [r["total_subagent_steps"] for r in results]
    main_step_counts = [r["main_agent_steps"] for r in results]
    total_step_counts = [r["total_steps"] for r in results]

    instances_with_subagents = sum(1 for c in subagent_counts if c > 0)
    all_subagent_step_lists = [
        sa["num_steps"] for r in results for sa in r["subagents"]
    ]

    # Per-subagent-type breakdown
    type_stats = defaultdict(lambda: {"count": 0, "step_counts": []})
    for r in results:
        for sa in r["subagents"]:
            st = sa["subagent_type"]
            type_stats[st]["count"] += 1
            type_stats[st]["step_counts"].append(sa["num_steps"])

    type_summary = {}
    for st, data in type_stats.items():
        type_summary[st] = {
            "total_invocations": data["count"],
            "steps_per_invocation": {
                "mean": round(statistics.mean(data["step_counts"]), 1),
                "median": round(statistics.median(data["step_counts"]), 1),
                "min": min(data["step_counts"]),
                "max": max(data["step_counts"]),
            },
        }

    def safe_stats(values):
        if not values:
            return {"mean": 0, "median": 0, "min": 0, "max": 0, "stdev": 0}
        result = {
            "mean": round(statistics.mean(values), 2),
            "median": round(statistics.median(values), 1),
            "min": min(values),
            "max": max(values),
        }
        if len(values) >= 2:
            result["stdev"] = round(statistics.stdev(values), 2)
        return result

    return {
        "num_instances": num_instances,
        "instances_with_subagents": instances_with_subagents,
        "instances_without_subagents": num_instances - instances_with_subagents,
        "subagent_calls_per_instance": safe_stats(subagent_counts),
        "total_subagent_calls": sum(subagent_counts),
        "subagent_steps_per_instance": safe_stats(subagent_step_counts),
        "main_agent_steps_per_instance": safe_stats(main_step_counts),
        "total_steps_per_instance": safe_stats(total_step_counts),
        "per_subagent_invocation": {
            "steps": safe_stats(all_subagent_step_lists),
        },
        "by_subagent_type": type_summary,
    }


def print_report(agg: dict, results: list[dict]):
    """Print a human-readable report."""
    print("=" * 70)
    print("SUB-AGENT ANALYSIS REPORT")
    print("=" * 70)
    print()
    print(f"Total instances analyzed:       {agg['num_instances']}")
    print(f"Instances with sub-agents:      {agg['instances_with_subagents']}")
    print(f"Instances without sub-agents:   {agg['instances_without_subagents']}")
    print(f"Total sub-agent invocations:    {agg['total_subagent_calls']}")
    print()

    print("--- Sub-agent calls per instance ---")
    s = agg["subagent_calls_per_instance"]
    print(f"  Mean:   {s['mean']}")
    print(f"  Median: {s['median']}")
    print(f"  Min:    {s['min']}")
    print(f"  Max:    {s['max']}")
    if "stdev" in s:
        print(f"  Stdev:  {s['stdev']}")
    print()

    print("--- Steps per sub-agent invocation ---")
    s = agg["per_subagent_invocation"]["steps"]
    print(f"  Mean:   {s['mean']}")
    print(f"  Median: {s['median']}")
    print(f"  Min:    {s['min']}")
    print(f"  Max:    {s['max']}")
    if "stdev" in s:
        print(f"  Stdev:  {s['stdev']}")
    print()

    print("--- Main agent steps per instance ---")
    s = agg["main_agent_steps_per_instance"]
    print(f"  Mean:   {s['mean']}")
    print(f"  Median: {s['median']}")
    print(f"  Min:    {s['min']}")
    print(f"  Max:    {s['max']}")
    if "stdev" in s:
        print(f"  Stdev:  {s['stdev']}")
    print()

    print("--- Total steps per instance (main + sub-agents) ---")
    s = agg["total_steps_per_instance"]
    print(f"  Mean:   {s['mean']}")
    print(f"  Median: {s['median']}")
    print(f"  Min:    {s['min']}")
    print(f"  Max:    {s['max']}")
    if "stdev" in s:
        print(f"  Stdev:  {s['stdev']}")
    print()

    if agg["by_subagent_type"]:
        print("--- Breakdown by sub-agent type ---")
        for stype, info in sorted(agg["by_subagent_type"].items()):
            print(f"  {stype}:")
            print(f"    Invocations: {info['total_invocations']}")
            print(f"    Steps/invocation:  mean={info['steps_per_invocation']['mean']}, "
                  f"median={info['steps_per_invocation']['median']}, "
                  f"min={info['steps_per_invocation']['min']}, "
                  f"max={info['steps_per_invocation']['max']}")
        print()

    # Per-instance table
    print("--- Per-instance details ---")
    print(f"{'Instance ID':<50} {'SubAgents':>9} {'SA Steps':>9} {'Main Steps':>10} {'Total':>6}")
    print("-" * 90)
    for r in sorted(results, key=lambda x: x["num_subagent_calls"], reverse=True):
        print(f"{r['instance_id']:<50} {r['num_subagent_calls']:>9} "
              f"{r['total_subagent_steps']:>9} {r['main_agent_steps']:>10} {r['total_steps']:>6}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Analyze sub-agent usage in Claude Code trajectories")
    parser.add_argument("input_dir", help="Directory containing *-output.zip trajectory files")
    parser.add_argument("--output-json", "-o", help="Path to write detailed JSON results")
    args = parser.parse_args()

    zip_files = sorted(glob.glob(os.path.join(args.input_dir, "*-output.zip")))
    if not zip_files:
        print(f"No *-output.zip files found in {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(zip_files)} trajectory zips in {args.input_dir}")
    print()

    results = []
    for zf_path in zip_files:
        result = analyze_trajectory(zf_path)
        if result:
            results.append(result)

    if not results:
        print("No valid trajectories found.", file=sys.stderr)
        sys.exit(1)

    agg = compute_aggregate_stats(results)
    print_report(agg, results)

    if args.output_json:
        output = {
            "aggregate": agg,
            "per_instance": results,
        }
        with open(args.output_json, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Detailed results written to {args.output_json}")


if __name__ == "__main__":
    main()
