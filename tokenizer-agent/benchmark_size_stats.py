#!/usr/bin/env python3
"""Aggregate RepoTokenizerAgent output across a Harbor job into benchmark-wide stats.

``RepoTokenizerAgent`` (see ``tokenizer_agent.py``) writes one
``token_counts.json`` per trial, at ``<job_dir>/<trial_name>/agent/token_counts.json``
(Harbor's standard per-trial agent-log location). This script walks a
completed job directory, collects every instance's token counts, and writes a
single ``benchmark_size_stats.json`` at the job root — sitting next to
Harbor's own ``<job_dir>/result.json`` — with the mean/median/population
standard deviation across the whole benchmark, plus a sorted per-instance
breakdown.

Usage:
    python benchmark_size_stats.py <job_dir> [-o OUTPUT] [--metric FIELD]
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

# Fields from token_counts.json that get aggregated across the benchmark.
STATS_FIELDS = (
    "total_tokens",
    "source_code_tokens",
    "total_files",
    "source_code_files",
)


def _find_token_counts_files(job_dir: Path) -> list[Path]:
    """Locate every trial's token_counts.json under a job directory.

    Handles both single-step trials (``<trial_dir>/agent/token_counts.json``)
    and multi-step trials (``<trial_dir>/steps/<step>/agent/token_counts.json``).
    """
    found: list[Path] = []
    for trial_dir in sorted(p for p in job_dir.iterdir() if p.is_dir()):
        single_step = trial_dir / "agent" / "token_counts.json"
        if single_step.is_file():
            found.append(single_step)
            continue
        steps_dir = trial_dir / "steps"
        if steps_dir.is_dir():
            found.extend(sorted(steps_dir.glob("*/agent/token_counts.json")))
    return found


def _load_instances(job_dir: Path) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for path in _find_token_counts_files(job_dir):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        instances.append(
            {
                "instance_id": data.get("instance_id", path.parent.parent.name),
                **{field: data.get(field, 0) for field in STATS_FIELDS},
            }
        )
    return instances


def _compute_stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
        "sum": sum(values),
    }


def build_summary(job_dir: Path, metric: str) -> dict[str, Any]:
    instances = _load_instances(job_dir)
    if not instances:
        raise SystemExit(
            f"No token_counts.json files found under {job_dir}. Did the job run "
            "RepoTokenizerAgent (tokenizer_agent.py)?"
        )

    instances.sort(key=lambda inst: inst[metric], reverse=True)

    return {
        "job_dir": str(job_dir),
        "n_instances": len(instances),
        "metrics": {
            field: _compute_stats([inst[field] for inst in instances])
            for field in STATS_FIELDS
        },
        "instances": instances,
    }


def _print_table(summary: dict[str, Any], metric: str) -> None:
    instances = summary["instances"]
    width = max((len(str(inst["instance_id"])) for inst in instances), default=8)

    header = f"{'instance_id':<{width}}  {'total_tokens':>13}  {'source_code_tokens':>19}  {'total_files':>11}"
    print(header)
    print("-" * len(header))
    for inst in instances:
        print(
            f"{str(inst['instance_id']):<{width}}  "
            f"{inst['total_tokens']:>13,}  "
            f"{inst['source_code_tokens']:>19,}  "
            f"{inst['total_files']:>11,}"
        )

    print()
    print(f"n_instances = {summary['n_instances']}")
    for field in STATS_FIELDS:
        s = summary["metrics"][field]
        print(
            f"{field:<20} mean={s['mean']:,.1f}  median={s['median']:,.1f}  "
            f"stdev={s['stdev']:,.1f}  min={s['min']:,.0f}  max={s['max']:,.0f}"
        )
    print()
    print(f"Sorted by {metric} (descending).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate RepoTokenizerAgent results across a Harbor job."
    )
    parser.add_argument(
        "job_dir",
        type=Path,
        help="Path to a Harbor job directory (e.g. jobs/2026-08-31-map)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Where to write benchmark_size_stats.json (default: <job_dir>/benchmark_size_stats.json)",
    )
    parser.add_argument(
        "--metric",
        choices=STATS_FIELDS,
        default="total_tokens",
        help="Field to sort the per-instance table by (default: total_tokens)",
    )
    args = parser.parse_args()

    job_dir = args.job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        raise SystemExit(f"Job directory not found: {job_dir}")

    summary = build_summary(job_dir, args.metric)

    output_path = args.output or (job_dir / "benchmark_size_stats.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    _print_table(summary, args.metric)
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
