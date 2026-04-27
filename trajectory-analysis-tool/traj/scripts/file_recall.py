"""File recall/precision analysis for benchmark runs.

Compares the files an agent touched (Read/Write) against the ground-truth
source files from the instance stats, and calculates recall and precision
for both Read and Write operations separately.

Usage:
    traj file-recall <trajectory_dir> \
        --instance-stats <instance_stats.json>

The trajectory_dir should contain output zips from a benchmark run
(e.g. swebench-xl-v1.eval.x86_64.<instance_id>-output.zip).

Each zip is expected to contain:
    output/trajectories/trajectory.json   — the agent trajectory
    output/eval.json                      — {"instance_id": {"resolved": bool}}
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path
from collections import defaultdict

from traj.loader import _detect_adapter
from traj.models import TrajectoryResult


# Files to exclude from ground truth when calculating metrics.
EXCLUDED_FILES = [
    "EsqlCapabilities.java",
]


def run(trajectories: list[TrajectoryResult], **kwargs) -> dict:
    """Entry point called by `traj analyse`.

    Requires extra CLI args:
        --instance-stats <path>   Path to instance_stats_output.json
        --trajectory-dir <path>   Path to the benchmark run directory with zips

    Since the standard analyse interface only passes normalised trajectories,
    this script reads the raw data itself. Call it directly via:
        python -m traj.scripts.file_recall --help
    """
    return {"error": "Use the standalone CLI: python -m traj.scripts.file_recall --help"}


def _extract_instance_id_from_zip(zip_path: str) -> str | None:
    """Extract instance_id from zip filename like
    swebench-xl-v1.eval.x86_64.elastic__elasticsearch-135899-output.zip
    or SWE-bench Pro style:
    prefix.ansible__ansible-0fd88717c953b92ed8a50495d55e630eb5d59166-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5-output.zip"""
    basename = os.path.basename(zip_path)
    match = re.search(r'\.([a-zA-Z0-9_]+__[a-zA-Z0-9_]+-[a-zA-Z0-9_-]+)-output\.zip$', basename)
    if match:
        return match.group(1)
    return None


def _load_trajectory_from_zip(zip_path: str) -> tuple[list | dict | None, dict | None]:
    """Load trajectory.json and eval.json from an output zip.

    Returns (trajectory_data, eval_data) or (None, None) on failure.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            traj_data = None
            eval_data = None

            if "output/trajectories/trajectory.json" in zf.namelist():
                traj_data = json.loads(zf.read("output/trajectories/trajectory.json"))
            if "output/eval.json" in zf.namelist():
                eval_data = json.loads(zf.read("output/eval.json"))

            return traj_data, eval_data
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: failed to read {zip_path}: {e}")
        return None, None


def _normalise_path(path: str) -> str:
    """Normalise a path for comparison — strip container prefixes, leading slashes, etc."""
    p = path.strip()
    # Remove common container prefixes
    for prefix in ["/testbed/", "/app/", "/workspace/", "/repo/"]:
        if p.startswith(prefix):
            p = p[len(prefix):]
    p = p.lstrip("/")
    return p


def _extract_files_by_action(traj_data: list | dict, source_file: str = "") -> tuple[set[str], set[str]]:
    """Extract the sets of files the agent read and wrote from a trajectory.

    Returns (read_files, written_files).
    """
    adapter = _detect_adapter(traj_data)
    _, _, ops = adapter.extract(traj_data, source_file)

    read_files = set()
    written_files = set()
    for op in ops:
        if not op.path:
            continue
        normalised = _normalise_path(op.path)
        if not normalised or normalised.endswith("/") or "." not in normalised.split("/")[-1]:
            continue
        if op.action == "Write":
            written_files.add(normalised)
        elif op.action == "Read":
            read_files.add(normalised)

    return read_files, written_files


def _filter_excluded(files: set[str]) -> set[str]:
    """Remove excluded files from a set (matches by filename, not full path)."""
    return {f for f in files if os.path.basename(f) not in EXCLUDED_FILES}


def _is_resolved(eval_data: dict | None, instance_id: str) -> bool | None:
    """Check if an instance was resolved from eval.json."""
    if eval_data is None:
        return None
    for key, val in eval_data.items():
        if isinstance(val, dict):
            return val.get("resolved", None)
    return None


def _extract_instance_id_from_dir(dir_name: str) -> str | None:
    """Extract instance_id from directory name like
    elastic__elasticsearch-135899__2UFCwGH
    or SWE-bench Pro style:
    ansible__ansible-0fd88717c953b92ed8a50495d55e630eb5d59166-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5__SUFFIX"""
    match = re.match(r'^([a-zA-Z0-9_]+__[a-zA-Z0-9_]+-[a-zA-Z0-9_-]+)__\w+$', dir_name)
    if match:
        return match.group(1)
    return None


def _load_trajectory_from_dir(instance_dir: str) -> tuple[list | dict | None, bool | None]:
    """Load trajectory and resolved status from an instance directory.

    Expects:
        agent/trajectory.json
        verifier/reward.txt (0 or 1)

    Returns (trajectory_data, resolved) or (None, None) on failure.
    """
    traj_path = os.path.join(instance_dir, "agent", "trajectory.json")
    reward_path = os.path.join(instance_dir, "verifier", "reward.txt")

    traj_data = None
    resolved = None

    try:
        if os.path.exists(traj_path):
            with open(traj_path) as f:
                traj_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: failed to read {traj_path}: {e}")

    try:
        if os.path.exists(reward_path):
            with open(reward_path) as f:
                reward = f.read().strip()
            resolved = reward == "1"
    except OSError:
        pass

    return traj_data, resolved


def _detect_run_format(traj_dir: Path) -> str:
    """Detect whether the run directory uses zip or directory format.

    Returns 'zip' or 'dir'.
    """
    if list(traj_dir.glob("*-output.zip")):
        return "zip"
    # Check for instance subdirectories with agent/trajectory.json
    for entry in traj_dir.iterdir():
        if entry.is_dir() and (entry / "agent" / "trajectory.json").exists():
            return "dir"
    return "zip"  # default fallback


def _collect_instances_zip(traj_dir: Path) -> list[tuple[str, list | dict, bool | None]]:
    """Collect (instance_id, traj_data, resolved) from zip-based runs."""
    results = []
    for zip_path in sorted(traj_dir.glob("*-output.zip")):
        instance_id = _extract_instance_id_from_zip(str(zip_path))
        if not instance_id:
            continue
        traj_data, eval_data = _load_trajectory_from_zip(str(zip_path))
        if traj_data is None:
            continue
        resolved = _is_resolved(eval_data, instance_id)
        results.append((instance_id, traj_data, resolved))
    return results


def _collect_instances_dir(traj_dir: Path) -> list[tuple[str, list | dict, bool | None]]:
    """Collect (instance_id, traj_data, resolved) from directory-based runs."""
    results = []
    for entry in sorted(traj_dir.iterdir()):
        if not entry.is_dir():
            continue
        instance_id = _extract_instance_id_from_dir(entry.name)
        if not instance_id:
            continue
        traj_data, resolved = _load_trajectory_from_dir(str(entry))
        if traj_data is None:
            continue
        results.append((instance_id, traj_data, resolved))
    return results


def _calc_metrics(ground_truth: set[str], predicted: set[str]) -> dict:
    """Calculate recall, precision, F1 between ground truth and predicted sets."""
    tp = ground_truth & predicted
    recall = len(tp) / len(ground_truth) if ground_truth else 0.0
    precision = len(tp) / len(predicted) if predicted else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "true_positives": sorted(tp),
        "false_negatives": sorted(ground_truth - predicted),
        "false_positives": sorted(predicted - ground_truth),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
    }


def analyse_directory(trajectory_dir: str, instance_stats_path: str) -> dict:
    """Run file recall/precision analysis on a benchmark run directory.

    Supports two directory formats:
    - Zip-based: contains *-output.zip files with trajectories inside
    - Directory-based: contains instance subdirectories with agent/trajectory.json
    """
    # Load instance stats
    with open(instance_stats_path) as f:
        stats_data = json.load(f)

    # Build lookup: instance_id -> source_files
    instances = stats_data if isinstance(stats_data, list) else stats_data.get("instances", [])
    source_files_map: dict[str, list[str]] = {}
    for inst in instances:
        iid = inst["instance_id"]
        source_files_map[iid] = inst.get("source_files", [])

    # Detect format and collect instances
    traj_dir = Path(trajectory_dir)
    run_format = _detect_run_format(traj_dir)

    if run_format == "dir":
        instance_data = _collect_instances_dir(traj_dir)
    else:
        instance_data = _collect_instances_zip(traj_dir)

    per_instance = []
    resolved_results = []
    unresolved_results = []

    for instance_id, traj_data, resolved in instance_data:
        ground_truth = set(source_files_map.get(instance_id, []))
        if not ground_truth:
            continue

        read_files, written_files = _extract_files_by_action(traj_data, instance_id)

        gt_filtered = _filter_excluded(ground_truth)

        write_metrics = _calc_metrics(ground_truth, written_files)
        read_metrics = _calc_metrics(ground_truth, read_files)
        write_excl_metrics = _calc_metrics(gt_filtered, written_files)
        read_excl_metrics = _calc_metrics(gt_filtered, read_files)

        result = {
            "instance_id": instance_id,
            "resolved": resolved,
            "ground_truth_files": sorted(ground_truth),
            "excluded_files": sorted(ground_truth - gt_filtered),
            "write": {
                "predicted_files": sorted(written_files),
                **write_metrics,
            },
            "read": {
                "predicted_files": sorted(read_files),
                **read_metrics,
            },
            "write_excluding": {
                **write_excl_metrics,
            },
            "read_excluding": {
                **read_excl_metrics,
            },
        }
        per_instance.append(result)

        if resolved is True:
            resolved_results.append(result)
        elif resolved is False:
            unresolved_results.append(result)

    # Compute averages
    def _avg(results: list[dict], section: str, key: str) -> float:
        if not results:
            return 0.0
        return round(sum(r[section][key] for r in results) / len(results), 4)

    def _section_avgs(results: list[dict], section: str) -> dict:
        return {
            "avg_recall": _avg(results, section, "recall"),
            "avg_precision": _avg(results, section, "precision"),
            "avg_f1": _avg(results, section, "f1"),
        }

    summary = {
        "total_instances": len(per_instance),
        "resolved_count": len(resolved_results),
        "unresolved_count": len(unresolved_results),
        "excluded_files": EXCLUDED_FILES,
        "overall": {
            "write": _section_avgs(per_instance, "write"),
            "read": _section_avgs(per_instance, "read"),
            "write_excluding": _section_avgs(per_instance, "write_excluding"),
            "read_excluding": _section_avgs(per_instance, "read_excluding"),
        },
        "resolved": {
            "count": len(resolved_results),
            "write": _section_avgs(resolved_results, "write"),
            "read": _section_avgs(resolved_results, "read"),
            "write_excluding": _section_avgs(resolved_results, "write_excluding"),
            "read_excluding": _section_avgs(resolved_results, "read_excluding"),
        },
        "unresolved": {
            "count": len(unresolved_results),
            "write": _section_avgs(unresolved_results, "write"),
            "read": _section_avgs(unresolved_results, "read"),
            "write_excluding": _section_avgs(unresolved_results, "write_excluding"),
            "read_excluding": _section_avgs(unresolved_results, "read_excluding"),
        },
    }

    return {
        "summary": summary,
        "per_instance": per_instance,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="File recall/precision analysis for benchmark runs",
    )
    parser.add_argument(
        "trajectory_dir",
        help="Directory containing output zips from a benchmark run",
    )
    parser.add_argument(
        "--instance-stats",
        required=True,
        help="Path to instance_stats_output.json with ground-truth source files",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write output to file instead of stdout",
    )
    args = parser.parse_args()

    result = analyse_directory(args.trajectory_dir, args.instance_stats)
    json_str = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(json_str)
        print(f"Written to {args.output}")
    else:
        print(json_str)
