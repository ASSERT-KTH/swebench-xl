"""Tests for traj/scripts/collect.py."""
from __future__ import annotations

import csv
import math
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from traj.scripts.collect import (
    CSV_COLUMNS,
    _load_size_metrics,
    _nan_safe,
    collect,
    write_csv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_size_csv(tmp_path: Path, rows: list[dict]) -> str:
    """Write a minimal size metrics CSV and return its path."""
    path = tmp_path / "size.csv"
    fieldnames = ["run_id", "benchmark", "instance", "source_code_files",
                  "source_code_tokens", "total_files", "total_tokens"]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def _fake_analyse_simple(trajectory_dir):
    """Minimal fake analyse_directory returning one instance."""
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "total_operations": 10, "first_write_at": 3,
             "actions_before_first_write": 3, "has_write": True,
             "breakdown_before_write": {}},
        ],
    }


def _fake_analyse_with_stats(trajectory_dir, instance_stats_path):
    """Minimal fake analyse_directory requiring instance_stats."""
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "write": {"recall": 1.0, "precision": 0.5, "f1": 0.67},
             "read": {"recall": 0.8, "precision": 0.4, "f1": 0.53}},
        ],
    }


def _fake_rtw(trajectory_dir, instance_stats_path):
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "gt_files_read": 2, "gt_files_written": 1,
             "read_then_written": 1, "conversion_rate": 0.5,
             "avg_steps_read_to_write": 3.0,
             "read_only_count": 1, "write_without_read_count": 0},
        ],
    }


def _fake_ttc(trajectory_dir, instance_stats_path):
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "first_correct_read": 2, "first_correct_write": 5,
             "ops_before_correct_read": 2, "ops_before_correct_write": 5,
             "found_correct_read": True, "found_correct_write": True},
        ],
    }


def _fake_ec(trajectory_dir):
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "total_writes": 4, "unique_files_written": 2,
             "rewrites": 2, "churn_rate": 0.5,
             "avg_writes_per_file": 2.0, "churned_file_count": 1},
        ],
    }


def _fake_eb(trajectory_dir):
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "unique_files": 8, "unique_dirs": 3,
             "max_depth": 4, "avg_depth": 2.5, "top_level_count": 2},
        ],
    }


def _fake_rr(trajectory_dir):
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "total_reads": 12, "unique_files_read": 6,
             "rereads": 6, "reread_rate": 0.5, "avg_reads_per_file": 2.0},
        ],
    }


def _fake_su(trajectory_dir):
    return {
        "summary": {},
        "per_instance": [
            {"instance_id": "owner__repo-123", "resolved": True,
             "subagent_count": 3},
        ],
    }


MOCK_PATCHES = {
    "traj.scripts.collect.abw_analyse": _fake_analyse_simple,
    "traj.scripts.collect.ec_analyse": _fake_ec,
    "traj.scripts.collect.eb_analyse": _fake_eb,
    "traj.scripts.collect.rr_analyse": _fake_rr,
    "traj.scripts.collect.su_analyse": _fake_su,
    "traj.scripts.collect.fr_analyse": _fake_analyse_with_stats,
    "traj.scripts.collect.rtw_analyse": _fake_rtw,
    "traj.scripts.collect.ttc_analyse": _fake_ttc,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadSizeMetrics:
    def test_loads_metrics(self, tmp_path):
        csv_path = _make_size_csv(tmp_path, [
            {"run_id": "1", "benchmark": "sb", "instance": "owner__repo-123",
             "source_code_files": "10", "source_code_tokens": "5000",
             "total_files": "20", "total_tokens": "10000"},
        ])
        result = _load_size_metrics(csv_path)
        assert "owner__repo-123" in result
        assert result["owner__repo-123"]["source_code_files"] == 10
        assert result["owner__repo-123"]["total_tokens"] == 10000

    def test_missing_instance(self, tmp_path):
        csv_path = _make_size_csv(tmp_path, [
            {"run_id": "1", "benchmark": "sb", "instance": "",
             "source_code_files": "10", "source_code_tokens": "5000",
             "total_files": "20", "total_tokens": "10000"},
        ])
        result = _load_size_metrics(csv_path)
        assert len(result) == 0


class TestNanSafe:
    def test_nan(self):
        assert _nan_safe(float("nan")) == ""

    def test_none(self):
        assert _nan_safe(None) == ""

    def test_normal(self):
        assert _nan_safe(42) == 42
        assert _nan_safe("hello") == "hello"


class TestCollect:
    def test_all_metrics_populated(self, tmp_path):
        csv_path = _make_size_csv(tmp_path, [
            {"run_id": "1", "benchmark": "sb", "instance": "owner__repo-123",
             "source_code_files": "10", "source_code_tokens": "5000",
             "total_files": "20", "total_tokens": "10000"},
        ])

        with patch.dict("sys.modules", {}):
            # We need to patch the imports inside collect()
            import traj.scripts.collect as mod

            orig_collect = mod.collect

            def patched_collect(run_dir, agent, benchmark, size_metrics_csv, instance_stats=None):
                with patch.object(mod, "_run_script_safe", side_effect=_mock_run_script_safe(instance_stats)):
                    # Call with real _load_size_metrics but mocked scripts
                    return _run_collect_with_mocks(
                        run_dir, agent, benchmark, size_metrics_csv, instance_stats
                    )

            rows = _run_collect_with_mocks(
                "/fake/dir", "test-agent", "test-bench", csv_path, "/fake/stats.json"
            )

        assert len(rows) == 1
        row = rows[0]
        assert row["agent"] == "test-agent"
        assert row["benchmark"] == "test-bench"
        assert row["instance_id"] == "owner__repo-123"
        assert row["resolved"] is True
        assert row["source_code_files"] == 10
        assert row["write_recall"] == 1.0
        assert row["total_operations"] == 10
        assert row["subagent_count"] == 3
        assert row["total_reads"] == 12
        assert row["unique_files_read"] == 6
        assert row["total_writes"] == 4
        assert row["first_correct_read"] == 2
        assert row["conversion_rate"] == 0.5

    def test_no_instance_stats_gives_nan(self, tmp_path):
        csv_path = _make_size_csv(tmp_path, [
            {"run_id": "1", "benchmark": "sb", "instance": "owner__repo-123",
             "source_code_files": "10", "source_code_tokens": "5000",
             "total_files": "20", "total_tokens": "10000"},
        ])

        rows = _run_collect_with_mocks(
            "/fake/dir", "test-agent", "test-bench", csv_path, None
        )

        assert len(rows) == 1
        row = rows[0]
        # Metrics from scripts not requiring instance_stats should be present
        assert row["total_operations"] == 10
        assert row["subagent_count"] == 3
        # Metrics requiring instance_stats should be NaN
        assert math.isnan(row["write_recall"])
        assert math.isnan(row["first_correct_read"])
        assert math.isnan(row["conversion_rate"])


class TestWriteCsv:
    def test_write_new(self, tmp_path):
        out = str(tmp_path / "out.csv")
        rows = [{"agent": "a", "benchmark": "b", "instance_id": "x", "resolved": True}]
        # Fill missing columns with NaN
        for col in CSV_COLUMNS:
            for row in rows:
                row.setdefault(col, float("nan"))

        write_csv(rows, out)

        with open(out, newline="") as fh:
            reader = csv.DictReader(fh)
            read_rows = list(reader)
        assert len(read_rows) == 1
        assert read_rows[0]["agent"] == "a"
        assert read_rows[0]["benchmark"] == "b"

    def test_append(self, tmp_path):
        out = str(tmp_path / "out.csv")
        row_template = {col: "" for col in CSV_COLUMNS}

        row1 = {**row_template, "agent": "a1", "benchmark": "b1", "instance_id": "x1"}
        row2 = {**row_template, "agent": "a2", "benchmark": "b2", "instance_id": "x2"}

        write_csv([row1], out, append=False)
        write_csv([row2], out, append=True)

        with open(out, newline="") as fh:
            reader = csv.DictReader(fh)
            read_rows = list(reader)
        assert len(read_rows) == 2
        assert read_rows[0]["agent"] == "a1"
        assert read_rows[1]["agent"] == "a2"

    def test_append_header_mismatch(self, tmp_path):
        out = str(tmp_path / "out.csv")
        # Write a CSV with wrong headers
        with open(out, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["wrong", "headers"])
            writer.writerow(["v1", "v2"])

        row = {col: "" for col in CSV_COLUMNS}
        with pytest.raises(SystemExit):
            write_csv([row], out, append=True)


# ---------------------------------------------------------------------------
# Helper to run collect with mocked analysis functions
# ---------------------------------------------------------------------------

def _mock_run_script_safe(instance_stats):
    """Return a side_effect function for _run_script_safe."""
    def _side_effect(name, fn, *args):
        return fn(*args)
    return _side_effect


def _run_collect_with_mocks(run_dir, agent, benchmark, size_csv, instance_stats):
    """Run collect() with all analyse_directory functions mocked."""
    import traj.scripts.collect as mod

    patches = [
        patch("traj.scripts.actions_before_write.analyse_directory", _fake_analyse_simple),
        patch("traj.scripts.edit_churn.analyse_directory", _fake_ec),
        patch("traj.scripts.exploration_breadth.analyse_directory", _fake_eb),
        patch("traj.scripts.reread_rate.analyse_directory", _fake_rr),
        patch("traj.scripts.subagent_usage.analyse_directory", _fake_su),
        patch("traj.scripts.file_recall.analyse_directory", _fake_analyse_with_stats),
        patch("traj.scripts.read_to_write.analyse_directory", _fake_rtw),
        patch("traj.scripts.time_to_correct.analyse_directory", _fake_ttc),
    ]

    for p in patches:
        p.start()
    try:
        return collect(run_dir, agent, benchmark, size_csv, instance_stats)
    finally:
        for p in patches:
            p.stop()
