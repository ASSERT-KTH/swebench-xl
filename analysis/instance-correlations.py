#!/usr/bin/env python3
"""
Instance Feature vs. Resolve Rate Correlation Analysis

Joins instance features (from instance_stats_output.json) with resolve rates
(from export.csv) and prints Spearman rank correlations + group comparisons.

Usage:
    python analysis/instance-correlations.py
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
from scipy import stats as sp_stats

SCRIPT_DIR = Path(__file__).resolve().parent
STATS_JSON = SCRIPT_DIR / "instance_stats_output.json"
EXPORT_CSV = Path.home() / "Downloads" / "export.csv"


def load_stats():
    with open(STATS_JSON) as f:
        data = json.load(f)
    return {inst["instance_id"]: inst for inst in data["instances"]}


def load_resolve_rates():
    rows = {}
    with open(EXPORT_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            iid = row["InstanceId"]
            rows[iid] = {
                "resolve_rate": float(row["ResolveRate"].replace(",", ".")),
                "difficulty": row["Difficulty"],
            }
    return rows


def build_dataset():
    stats = load_stats()
    rates = load_resolve_rates()
    dataset = []
    for iid, s in stats.items():
        if iid not in rates:
            continue
        r = rates[iid]
        dataset.append({
            "instance_id": iid,
            "instance_type": s["instance_type"],
            "f2p_count": s["f2p_count"],
            "p2p_count": s["p2p_count"],
            "source_file_count": s["source_file_count"],
            "module_count": s["module_count"],
            "cross_module": int(s["cross_module"]),
            "lines_added": s["lines_added"],
            "lines_removed": s["lines_removed"],
            "total_lines_changed": s["total_lines_changed"],
            "resolve_rate": r["resolve_rate"],
            "difficulty": r["difficulty"],
            "lines_per_file": s["total_lines_changed"] / max(s["source_file_count"], 1),
            "add_remove_ratio": s["lines_added"] / max(s["lines_removed"], 1),
            "f2p_to_p2p_ratio": s["f2p_count"] / max(s["p2p_count"], 1),

            "is_esql": int(any("esql" in sf for sf in s["source_files"])),
        })
    return dataset


FEATURES = [
    ("f2p_count", "Fail-to-Pass Tests"),
    ("p2p_count", "Pass-to-Pass Tests"),
    ("source_file_count", "Source Files"),
    ("module_count", "Module Count"),
    ("lines_added", "Lines Added"),
    ("lines_removed", "Lines Removed"),
    ("total_lines_changed", "Total Lines Changed"),
    ("lines_per_file", "Lines per File"),
    ("add_remove_ratio", "Add/Remove Ratio"),
    ("f2p_to_p2p_ratio", "F2P/P2P Ratio"),

    ("cross_module", "Cross-Module"),
    ("is_esql", "Is ESQL"),
]


def main():
    dataset = build_dataset()
    resolve = [d["resolve_rate"] for d in dataset]

    # --- Spearman correlations ---
    results = []
    for key, label in FEATURES:
        vals = [d[key] for d in dataset]
        r, p = sp_stats.spearmanr(vals, resolve)
        results.append((label, key, r, p))
    results.sort(key=lambda x: abs(x[2]), reverse=True)

    print(f"\nSpearman correlations with resolve rate (n={len(dataset)})\n")
    print(f"  {'Feature':<25} {'ρ':>8} {'p-value':>10} {'Sig':>5}")
    print(f"  {'-'*50}")
    for label, _, r, p in results:
        sig = "***" if p and p < 0.001 else "**" if p and p < 0.01 else "*" if p and p < 0.05 else "ns"
        pstr = f"{p:.4f}"
        print(f"  {label:<25} {r:>+8.3f} {pstr:>10} {sig:>5}")

    # --- Group comparisons ---
    print(f"\n  {'Group':<25} {'Mean %':>8} {'Median %':>10} {'n':>5}")
    print(f"  {'-'*50}")
    by_diff = defaultdict(list)
    for d in dataset:
        by_diff[d["difficulty"]].append(d["resolve_rate"])
    for diff in ["Easy", "Medium", "Hard", "Very Hard", "Unsolved"]:
        vals = sorted(by_diff.get(diff, []))
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        median = vals[len(vals) // 2]
        print(f"  {diff:<25} {mean:>7.1f}% {median:>9.1f}% {len(vals):>5}")

    for group_name, key, mapping in [
        ("Instance Type", "instance_type", None),
        ("Cross-Module", "cross_module", {0: "Single Module", 1: "Cross-Module"}),
        ("ESQL", "is_esql", {0: "Non-ESQL", 1: "ESQL"}),
    ]:
        print(f"\n  {group_name}:")
        by_group = defaultdict(list)
        for d in dataset:
            label = mapping[d[key]] if mapping else d[key]
            by_group[label].append(d["resolve_rate"])
        for label, vals in sorted(by_group.items()):
            vals = sorted(vals)
            mean = sum(vals) / len(vals)
            median = vals[len(vals) // 2]
            print(f"  {label:<25} {mean:>7.1f}% {median:>9.1f}% {len(vals):>5}")


if __name__ == "__main__":
    main()
