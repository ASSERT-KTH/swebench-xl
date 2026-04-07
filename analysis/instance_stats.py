#!/usr/bin/env python3
"""Analyze benchmark instances: test counts, source file counts, and patch line changes."""

import argparse
import csv
import json
import statistics
from pathlib import Path

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "swebench-xl-v0.1-json" / "validated_instances_high_quality.json"


def load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_changelog(filepath: str) -> bool:
    """Return True if the file path looks like a changelog entry (not real source code)."""
    low = filepath.lower()
    return "changelog" in low


def get_module(filepath: str) -> str:
    """Extract the Gradle module from a source file path.

    E.g. 'server/src/main/java/...' -> 'server'
         'x-pack/plugin/core/src/main/java/...' -> 'x-pack/plugin/core'
         'libs/exponential-histogram/src/test/java/...' -> 'libs/exponential-histogram'
    """
    for marker in ("/src/main/java/", "/src/test/java/", "/src/main/resources/", "/src/test/resources/"):
        idx = filepath.find(marker)
        if idx != -1:
            return filepath[:idx]
    # Fallback: use the first path component
    return filepath.split("/")[0]


def count_patch_lines_per_file(patch_text: str) -> dict[str, tuple[int, int]]:
    """Parse a unified diff and return {filepath: (lines_added, lines_removed)} per file."""
    per_file: dict[str, tuple[int, int]] = {}
    current_file = None

    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            if current_file not in per_file:
                per_file[current_file] = (0, 0)
            continue
        if line.startswith("--- "):
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added, removed = per_file[current_file]
            per_file[current_file] = (added + 1, removed)
        elif line.startswith("-") and not line.startswith("---"):
            added, removed = per_file[current_file]
            per_file[current_file] = (added, removed + 1)

    return per_file


def analyze_instance(instance: dict) -> dict:
    """Compute stats for a single instance."""
    f2p = instance.get("fail_to_pass", [])
    p2p = instance.get("pass_to_pass", [])

    all_source_files = instance.get("source_files", [])
    filtered_source = [f for f in all_source_files if f.endswith(".java") and "generated/" not in f and "generated-src/" not in f]

    patch_text = instance.get("patch", "")
    per_file = count_patch_lines_per_file(patch_text)

    lines_added = 0
    lines_removed = 0
    for filepath, (added, removed) in per_file.items():
        if filepath.endswith(".java") and "generated/" not in filepath and "generated-src/" not in filepath:
            lines_added += added
            lines_removed += removed

    modules = sorted(set(get_module(f) for f in filtered_source))
    cross_module = len(modules) > 1

    return {
        "instance_id": instance["instance_id"],
        "instance_type": instance.get("instance_type", ""),
        "f2p_count": len(f2p),
        "p2p_count": len(p2p),
        "source_file_count": len(filtered_source),
        "source_files": filtered_source,
        "modules": modules,
        "module_count": len(modules),
        "cross_module": cross_module,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "total_lines_changed": lines_added + lines_removed,
    }


def print_table(results: list[dict]) -> None:
    """Print a formatted table of per-instance stats."""
    header = f"{'Instance ID':<45} {'Type':<20} {'F2P':>4} {'P2P':>5} {'Src':>4} {'Mods':>5} {'XMod':>5} {'+Lines':>7} {'-Lines':>7} {'Total':>7}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in results:
        xmod = "YES" if r['cross_module'] else ""
        print(
            f"{r['instance_id']:<45} {r['instance_type']:<20} "
            f"{r['f2p_count']:>4} {r['p2p_count']:>5} {r['source_file_count']:>4} "
            f"{r['module_count']:>5} {xmod:>5} "
            f"{r['lines_added']:>7} {r['lines_removed']:>7} {r['total_lines_changed']:>7}"
        )
    print(sep)


def print_summary(results: list[dict]) -> None:
    """Print aggregate statistics."""
    n = len(results)
    if n == 0:
        print("No instances to summarize.")
        return

    cross_module_count = sum(1 for r in results if r["cross_module"])
    single_module_count = n - cross_module_count

    metrics = {
        "Fail-to-Pass tests": [r["f2p_count"] for r in results],
        "Pass-to-Pass tests": [r["p2p_count"] for r in results],
        "Source files (.java only)": [r["source_file_count"] for r in results],
        "Modules touched": [r["module_count"] for r in results],
        "Lines added": [r["lines_added"] for r in results],
        "Lines removed": [r["lines_removed"] for r in results],
        "Total lines changed": [r["total_lines_changed"] for r in results],
    }

    print(f"\n{'='*60}")
    print(f" SUMMARY  ({n} instances)")
    print(f"{'='*60}")
    print(f" Cross-module: {cross_module_count}  |  Single-module: {single_module_count}")
    print(f"{'Metric':<32} {'Min':>6} {'Max':>6} {'Mean':>8} {'Median':>8} {'Total':>8}")
    print(f"{'-'*32} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
    for name, values in metrics.items():
        mn = min(values)
        mx = max(values)
        avg = statistics.mean(values)
        med = statistics.median(values)
        total = sum(values)
        print(f"{name:<32} {mn:>6} {mx:>6} {avg:>8.1f} {med:>8.1f} {total:>8}")


def write_json_output(results: list[dict], summary: dict, path: str) -> None:
    output = {"instances": results, "summary": summary}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nJSON output written to {path}")


def write_csv_output(results: list[dict], path: str) -> None:
    fieldnames = [
        "instance_id", "instance_type", "f2p_count", "p2p_count",
        "source_file_count", "module_count", "cross_module",
        "lines_added", "lines_removed", "total_lines_changed",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"CSV output written to {path}")


def build_summary(results: list[dict]) -> dict:
    """Build a summary dict for JSON output."""
    n = len(results)
    if n == 0:
        return {}
    metric_keys = [
        ("f2p_count", "fail_to_pass"),
        ("p2p_count", "pass_to_pass"),
        ("source_file_count", "source_files"),
        ("lines_added", "lines_added"),
        ("lines_removed", "lines_removed"),
        ("total_lines_changed", "total_lines_changed"),
    ]
    summary = {"total_instances": n}
    for key, label in metric_keys:
        values = [r[key] for r in results]
        summary[label] = {
            "min": min(values),
            "max": max(values),
            "mean": round(statistics.mean(values), 2),
            "median": statistics.median(values),
            "total": sum(values),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark instance stats")
    parser.add_argument("input", nargs="?", default=str(DEFAULT_INPUT), help="Path to validated instances JSON")
    parser.add_argument("-o", "--output", default=None, help="Path for JSON output (default: analysis/instance_stats_output.json)")
    parser.add_argument("--csv", default=None, help="Path for CSV output")
    args = parser.parse_args()

    if args.output is None:
        args.output = str(Path(__file__).resolve().parent / "instance_stats_output.json")

    instances = load_json(args.input)
    results = [analyze_instance(inst) for inst in instances]
    results.sort(key=lambda r: r["instance_id"])

    print_table(results)
    print_summary(results)

    summary = build_summary(results)
    write_json_output(results, summary, args.output)

    if args.csv:
        write_csv_output(results, args.csv)


if __name__ == "__main__":
    main()
