"""Unified per-instance CSV export.

Runs all analysis scripts on a benchmark run directory and outputs a flat CSV
with one row per instance, combining metadata, size metrics, and all
per-instance analysis results.

Usage:
    traj collect <run_dir> \
        --agent copilot-cli-opus-4.6 \
        --benchmark swebench-verified \
        --size-metrics /path/to/data.csv \
        [--instance-stats /path/to/instance_stats.json] \
        -o results.csv \
        [--append]
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path


# Ordered list of CSV column names.
CSV_COLUMNS = [
    # Metadata
    "agent",
    "benchmark",
    "instance_id",
    "resolved",
    # Codebase size
    "source_code_files",
    "source_code_tokens",
    # Quality
    "write_recall",
    "write_precision",
    "read_recall",
    "read_precision",
    # Scale of work
    "total_operations",
    "total_reads",
    "total_writes",
    # Exploration breadth
    "unique_files_read",
    "unique_files_written",
    "unique_dirs",
    "max_depth",
    # Efficiency / behaviour
    "first_write_at",
    "reread_rate",
    "churn_rate",
    "conversion_rate",
    # Navigation
    "first_correct_read",
    "first_correct_write",
    # Sub-agents
    "subagent_count",
]

NAN = float("nan")


def _load_size_metrics(csv_path: str) -> dict[str, dict]:
    """Load the size metrics CSV and return a dict keyed by instance id.

    The CSV uses column ``instance`` for the instance id.  We extract only the
    four size-related columns.
    """
    size_keys = ["source_code_files", "source_code_tokens", "total_files", "total_tokens"]
    lookup: dict[str, dict] = {}

    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            iid = row.get("instance", "").strip()
            if not iid:
                continue
            entry: dict = {}
            for key in size_keys:
                raw = row.get(key, "").strip()
                try:
                    entry[key] = int(raw) if raw else NAN
                except ValueError:
                    try:
                        entry[key] = float(raw)
                    except ValueError:
                        entry[key] = NAN
            lookup[iid] = entry

    return lookup


def _index_per_instance(per_instance_list: list[dict]) -> dict[str, dict]:
    """Index a list of per-instance dicts by instance_id."""
    return {item["instance_id"]: item for item in per_instance_list}


def _run_script_safe(name: str, fn, *args):
    """Run an analysis function and return its result, or None on error."""
    try:
        return fn(*args)
    except Exception as exc:
        print(f"Warning: {name} failed: {exc}", file=sys.stderr)
        return None


def collect(
    run_dir: str,
    agent: str,
    benchmark: str,
    size_metrics_csv: str,
    instance_stats: str | None = None,
) -> list[dict]:
    """Run all analysis scripts and return a list of flat per-instance dicts."""
    from traj.scripts.actions_before_write import (
        analyse_directory as abw_analyse,
    )
    from traj.scripts.edit_churn import analyse_directory as ec_analyse
    from traj.scripts.exploration_breadth import analyse_directory as eb_analyse
    from traj.scripts.reread_rate import analyse_directory as rr_analyse
    from traj.scripts.subagent_usage import analyse_directory as su_analyse

    # Scripts that require instance_stats
    from traj.scripts.file_recall import analyse_directory as fr_analyse
    from traj.scripts.read_to_write import analyse_directory as rtw_analyse
    from traj.scripts.time_to_correct import analyse_directory as ttc_analyse

    # Load size metrics
    size_lookup = _load_size_metrics(size_metrics_csv)

    # Run scripts that don't need instance_stats
    abw_result = _run_script_safe("actions_before_write", abw_analyse, run_dir)
    ec_result = _run_script_safe("edit_churn", ec_analyse, run_dir)
    eb_result = _run_script_safe("exploration_breadth", eb_analyse, run_dir)
    rr_result = _run_script_safe("reread_rate", rr_analyse, run_dir)
    su_result = _run_script_safe("subagent_usage", su_analyse, run_dir)

    # Run scripts that need instance_stats (optional)
    fr_result = None
    rtw_result = None
    ttc_result = None
    if instance_stats:
        fr_result = _run_script_safe("file_recall", fr_analyse, run_dir, instance_stats)
        rtw_result = _run_script_safe("read_to_write", rtw_analyse, run_dir, instance_stats)
        ttc_result = _run_script_safe("time_to_correct", ttc_analyse, run_dir, instance_stats)

    # Index all per-instance results by instance_id
    def _idx(result):
        if result is None:
            return {}
        return _index_per_instance(result.get("per_instance", []))

    abw_idx = _idx(abw_result)
    ec_idx = _idx(ec_result)
    eb_idx = _idx(eb_result)
    rr_idx = _idx(rr_result)
    su_idx = _idx(su_result)
    fr_idx = _idx(fr_result)
    rtw_idx = _idx(rtw_result)
    ttc_idx = _idx(ttc_result)

    # Collect instance_ids from the first successful script as canonical set.
    # All scripts process the same run dir, so they should agree on IDs.
    # Using a single source avoids mismatches from different ID-extraction logic.
    canonical_idx = next(
        (idx for idx in [abw_idx, ec_idx, eb_idx, rr_idx, su_idx, fr_idx, rtw_idx, ttc_idx] if idx),
        {},
    )
    all_ids = set(canonical_idx.keys())

    rows: list[dict] = []
    for iid in sorted(all_ids):
        abw = abw_idx.get(iid, {})
        ec = ec_idx.get(iid, {})
        eb = eb_idx.get(iid, {})
        rr = rr_idx.get(iid, {})
        su = su_idx.get(iid, {})
        fr = fr_idx.get(iid, {})
        rtw = rtw_idx.get(iid, {})
        ttc = ttc_idx.get(iid, {})
        size = size_lookup.get(iid, {})

        # Determine resolved from whichever script has it
        resolved = None
        for d in [abw, ec, eb, rr, su, fr, rtw, ttc]:
            if d.get("resolved") is not None:
                resolved = d["resolved"]
                break

        # Flatten file_recall nested dicts
        fr_write = fr.get("write", {})
        fr_read = fr.get("read", {})

        row: dict = {
            # Metadata
            "agent": agent,
            "benchmark": benchmark,
            "instance_id": iid,
            "resolved": resolved,
            # Codebase size
            "source_code_files": size.get("source_code_files", NAN),
            "source_code_tokens": size.get("source_code_tokens", NAN),
            # Quality
            "write_recall": fr_write.get("recall", NAN),
            "write_precision": fr_write.get("precision", NAN),
            "read_recall": fr_read.get("recall", NAN),
            "read_precision": fr_read.get("precision", NAN),
            # Scale of work
            "total_operations": abw.get("total_operations", NAN),
            "total_reads": rr.get("total_reads", NAN),
            "total_writes": ec.get("total_writes", NAN),
            # Exploration breadth
            "unique_files_read": rr.get("unique_files_read", NAN),
            "unique_files_written": ec.get("unique_files_written", NAN),
            "unique_dirs": eb.get("unique_dirs", NAN),
            "max_depth": eb.get("max_depth", NAN),
            # Efficiency / behaviour
            "first_write_at": abw.get("first_write_at", NAN),
            "reread_rate": rr.get("reread_rate", NAN),
            "churn_rate": ec.get("churn_rate", NAN),
            "conversion_rate": rtw.get("conversion_rate", NAN),
            # Navigation
            "first_correct_read": ttc.get("first_correct_read", NAN),
            "first_correct_write": ttc.get("first_correct_write", NAN),
            # Sub-agents
            "subagent_count": su.get("subagent_count", NAN),
        }
        rows.append(row)

    return rows


def _nan_safe(value):
    """Convert NaN floats to empty string for CSV output, leave others as-is."""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if value is None:
        return ""
    return value


def write_csv(rows: list[dict], output_path: str, *, append: bool = False):
    """Write rows to a CSV file, optionally appending to an existing file."""
    out = Path(output_path)

    if append and out.exists():
        # Verify header matches
        with open(out, newline="") as fh:
            reader = csv.reader(fh)
            existing_header = next(reader, None)
        if existing_header and existing_header != CSV_COLUMNS:
            print(
                f"Error: existing CSV header doesn't match expected columns.\n"
                f"  Expected: {CSV_COLUMNS[:5]}...\n"
                f"  Got:      {existing_header[:5]}...",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(out, "a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            for row in rows:
                writer.writerow({k: _nan_safe(row.get(k)) for k in CSV_COLUMNS})
        print(f"Appended {len(rows)} rows to {output_path}")
    else:
        with open(out, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _nan_safe(row.get(k)) for k in CSV_COLUMNS})
        print(f"Written {len(rows)} rows to {output_path}")
