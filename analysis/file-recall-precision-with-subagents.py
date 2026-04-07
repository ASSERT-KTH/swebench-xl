#!/usr/bin/env python3
"""
File recall/precision stats for Claude Code trajectories, with sub-agent breakdown.

Reads zipped trajectory outputs and computes recall/precision of file reads and
writes against the gold-patch source files, splitting contributions by main agent
vs sub-agents.

Usage:
    python file-recall-precision-with-subagents.py /path/to/outputs/
    python file-recall-precision-with-subagents.py /path/to/outputs/ --instance elastic__elasticsearch-135899
    python file-recall-precision-with-subagents.py /path/to/outputs/ --unresolved --categorize
    python file-recall-precision-with-subagents.py /path/to/outputs/ --plot

    python file-recall-precision-with-subagents.py /Users/pontusberglund/Documents/full-run-trajectories/claude-code-full-msbench   
"""

import argparse
import json
import os
import re
import statistics
import sys
import zipfile
from collections import Counter, defaultdict

import matplotlib.pyplot as plt

INSTANCE_STATS = os.path.join(os.path.dirname(__file__), "instance_stats_output.json")

ZIP_SUFFIX = "-output.zip"

# Gold patch files to exclude from source set (matched by basename)
EXCLUDED_GOLD_FILES = [
    "EsqlCapabilities.java",
]

DEFAULT_RECALL_THRESHOLD = 0.67
DEFAULT_PRECISION_THRESHOLD = 0.67


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _is_valid_source_path(path):
    """Return True if path looks like an actual source file."""
    if path.endswith("/"):
        return False
    basename = os.path.basename(path)
    if "." not in basename:
        return False
    if "/build/" in path or "/target/" in path:
        return False
    if path.endswith(".class"):
        return False
    return True


def _is_test_file(path):
    return os.path.basename(path).endswith("Tests.java")


def _extract_paths_from_command(cmd):
    """Extract file paths from a bash command."""
    paths = []
    abs_paths = re.findall(r"(/app/[^\s'\"\\|>;]+)", cmd)
    for p in abs_paths:
        clean = p.rstrip(".,;:)(")
        paths.append(clean)
    rel_paths = re.findall(
        r"(?:^|\s)([a-zA-Z0-9_.][^\s'\"\\|>;]*\.[a-zA-Z0-9]+)", cmd
    )
    for p in rel_paths:
        clean = p.rstrip(".,;:)(")
        if "/" in clean and not clean.startswith("/"):
            paths.append(f"/app/{clean}")
    return [p for p in paths if _is_valid_source_path(p)]


def _is_non_read_command(cmd):
    """Return True if the command is not investigative."""
    stripped = cmd.lstrip()
    non_read_prefixes = (
        "git add ", "git checkout ", "git restore ", "git reset ",
        "git stash", "git commit", "git push", "git pull",
        "git merge", "git rebase", "git cherry-pick",
        "rm ", "mv ", "cp ", "mkdir ", "touch ", "chmod ", "chown ",
    )
    return stripped.startswith(non_read_prefixes)


def _is_write_command(cmd):
    """Return True if the command modifies files."""
    stripped = cmd.lstrip()
    write_prefixes = ("sed ", "sed -i", "echo ", "printf ", "tee ")
    if ">>" in cmd or re.search(r"[^>]>[^>]", cmd):
        return True
    return stripped.startswith(write_prefixes)


def _extract_semantic_dirs(path):
    """Extract module, package, and parent directory from a path."""
    parent = os.path.dirname(path)
    src_idx = path.find("/src/")
    if src_idx != -1:
        module = path[:src_idx]
    else:
        parts = path.split("/")
        module = "/".join(parts[: min(4, len(parts))])
    java_idx = path.find("/java/")
    if java_idx != -1:
        after_java = path[java_idx + len("/java/") :]
        package = os.path.dirname(after_java)
    else:
        package = parent
    return {"module": module, "package": package, "parent": parent}


def _map_to_dir_sets(file_set, level):
    dirs = set()
    for path in file_set:
        sem = _extract_semantic_dirs(path)
        dirs.add(sem[level])
    return dirs


def _precision_recall(predicted_set, gold_set):
    tp = len(predicted_set & gold_set)
    fp = len(predicted_set - gold_set)
    fn = len(gold_set - predicted_set)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    return {
        "recall": recall,
        "precision": precision,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }


def _safe_stats(values):
    if not values:
        return {"mean": 0, "median": 0, "min": 0, "max": 0}
    result = {
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 1),
        "min": min(values),
        "max": max(values),
    }
    if len(values) >= 2:
        result["stdev"] = round(statistics.stdev(values), 2)
    return result


# ---------------------------------------------------------------------------
# Trajectory loading
# ---------------------------------------------------------------------------

def _instance_id_from_zip(filename):
    basename = os.path.basename(filename)
    if not basename.endswith(ZIP_SUFFIX):
        return None
    without_suffix = basename[: -len(ZIP_SUFFIX)]
    idx = without_suffix.find("x86_64.")
    if idx != -1:
        return without_suffix[idx + len("x86_64.") :]
    return None


def load_legacy_trajectory_from_zip(zip_path):
    """Load trajectory_legacy.json from inside a zip file."""
    with zipfile.ZipFile(zip_path, "r") as z:
        return json.loads(z.read("output/trajectories/trajectory_legacy.json"))


def is_resolved_from_zip(zip_path):
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            eval_data = json.loads(z.read("output/eval.json"))
        for _, info in eval_data.items():
            if info.get("resolved", False):
                return True
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        pass
    return False


def get_all_trajectory_zips(trajectory_dir):
    """Return sorted list of (zip_path, instance_id) tuples."""
    results = []
    for filename in sorted(os.listdir(trajectory_dir)):
        if not filename.endswith(ZIP_SUFFIX):
            continue
        instance_id = _instance_id_from_zip(filename)
        if instance_id is None:
            continue
        results.append((os.path.join(trajectory_dir, filename), instance_id))
    return results


def _load_instance_stats():
    with open(INSTANCE_STATS, "r") as f:
        return json.load(f)


_INSTANCE_STATS_CACHE = None


def source_files_from_instance_id(instance_id):
    global _INSTANCE_STATS_CACHE
    if _INSTANCE_STATS_CACHE is None:
        _INSTANCE_STATS_CACHE = _load_instance_stats()
    for instance in _INSTANCE_STATS_CACHE["instances"]:
        if instance["instance_id"] == instance_id:
            return instance.get("source_files", [])
    return []


# ---------------------------------------------------------------------------
# Read/write extraction from legacy trajectory (with sub-agent attribution)
# ---------------------------------------------------------------------------

def _parse_action(action_str):
    if not action_str:
        return {}
    try:
        return json.loads(action_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_reads_writes(legacy_items):
    """Extract reads and writes from legacy trajectory items.

    Returns:
        main_reads:  dict[path -> [descriptions]]  (main agent only)
        main_writes: set of paths                   (main agent only)
        sa_reads:    dict[path -> [descriptions]]   (sub-agent only)
        sa_writes:   set of paths                   (sub-agent only)
        subagent_stats: dict with sub-agent usage info
    """
    main_reads = {}
    main_writes = set()
    sa_reads = {}
    sa_writes = set()

    subagent_calls = []
    subagent_steps = defaultdict(list)
    main_tool_count = 0

    for item in legacy_items:
        fn = item.get("tool", "")
        parent_id = item.get("parent_tool_use_id")
        args = _parse_action(item.get("action", ""))

        if fn == "Agent" and not parent_id:
            subagent_calls.append(item)
            main_tool_count += 1
            continue
        if parent_id:
            subagent_steps[parent_id].append(item)
        else:
            main_tool_count += 1

        # Decide which bucket to use
        is_sub = parent_id is not None
        reads_bucket = sa_reads if is_sub else main_reads
        writes_bucket = sa_writes if is_sub else main_writes
        tag = "[sub-agent] " if is_sub else ""

        if fn == "Read":
            file_path = args.get("file_path", "")
            if file_path and _is_valid_source_path(file_path):
                reads_bucket.setdefault(file_path, []).append(f"{tag}Read {file_path}")

        elif fn == "Grep":
            path = args.get("path", "")
            if path and _is_valid_source_path(path):
                reads_bucket.setdefault(path, []).append(
                    f"{tag}Grep pattern={args.get('pattern', '')} path={path}"
                )

        elif fn == "Bash":
            cmd = args.get("command", "")
            if not cmd:
                continue
            extracted = _extract_paths_from_command(cmd)
            if _is_write_command(cmd):
                for p in extracted:
                    writes_bucket.add(p)
            elif not _is_non_read_command(cmd):
                for p in extracted:
                    reads_bucket.setdefault(p, []).append(f"{tag}Bash: {cmd}")

        elif fn == "Edit":
            file_path = args.get("file_path", "")
            if file_path and _is_valid_source_path(file_path):
                writes_bucket.add(file_path)

        elif fn == "Write":
            file_path = args.get("file_path", "")
            if file_path and file_path.startswith("/app/") and _is_valid_source_path(file_path):
                writes_bucket.add(file_path)

    # Sub-agent stats
    all_parent_ids = {item.get("parent_tool_use_id") for item in legacy_items
                      if item.get("parent_tool_use_id")}
    total_subagent_steps = sum(len(v) for v in subagent_steps.values())
    per_invocation_steps = [len(subagent_steps[pid]) for pid in all_parent_ids] if all_parent_ids else []

    sa_tool_counts = Counter()
    for steps_list in subagent_steps.values():
        for s in steps_list:
            sa_tool_counts[s.get("tool", "unknown")] += 1

    type_counts = Counter()
    for ac in subagent_calls:
        ac_args = _parse_action(ac.get("action", ""))
        type_counts[ac_args.get("subagent_type", "unknown")] += 1

    subagent_stats = {
        "num_subagent_calls": len(subagent_calls),
        "total_subagent_steps": total_subagent_steps,
        "main_tool_count": main_tool_count,
        "total_items": len(legacy_items),
        "per_invocation_steps": per_invocation_steps,
        "subagent_tool_counts": dict(sa_tool_counts),
        "subagent_type_counts": dict(type_counts),
    }

    return main_reads, main_writes, sa_reads, sa_writes, subagent_stats


# ---------------------------------------------------------------------------
# Precision / recall computation
# ---------------------------------------------------------------------------

def compute_stats(main_reads, main_writes, sa_reads, sa_writes, source_files,
                  exclude_tests=False):
    """Compute precision/recall for main-only, sub-agent-only, and combined."""
    source_set = {f"/app/{s.lstrip('/')}" for s in source_files}
    source_set = {s for s in source_set if os.path.basename(s) not in EXCLUDED_GOLD_FILES}

    def apply_filter(path_set):
        if exclude_tests:
            return {p for p in path_set if not _is_test_file(p)}
        return path_set

    main_read_set = apply_filter(set(main_reads))
    main_write_set = apply_filter(main_writes)
    sa_read_set = apply_filter(set(sa_reads))
    sa_write_set = apply_filter(sa_writes)
    combined_read_set = main_read_set | sa_read_set
    combined_write_set = main_write_set | sa_write_set

    result = {}
    for scope, r_set, w_set in [
        ("main", main_read_set, main_write_set),
        ("subagent", sa_read_set, sa_write_set),
        ("combined", combined_read_set, combined_write_set),
    ]:
        result[f"{scope}_read"] = _precision_recall(r_set, source_set)
        result[f"{scope}_write"] = _precision_recall(w_set, source_set)
        for level in ("module", "package", "parent"):
            r_dirs = _map_to_dir_sets(r_set, level)
            w_dirs = _map_to_dir_sets(w_set, level)
            s_dirs = _map_to_dir_sets(source_set, level)
            result[f"{scope}_read_{level}"] = _precision_recall(r_dirs, s_dirs)
            result[f"{scope}_write_{level}"] = _precision_recall(w_dirs, s_dirs)

    # Extra: files read by sub-agent but not main (unique sub-agent contribution)
    sa_unique_reads = sa_read_set - main_read_set
    sa_unique_writes = sa_write_set - main_write_set
    result["subagent_unique_reads"] = len(sa_unique_reads)
    result["subagent_unique_reads_tp"] = len(sa_unique_reads & source_set)
    result["subagent_unique_writes"] = len(sa_unique_writes)
    result["subagent_unique_writes_tp"] = len(sa_unique_writes & source_set)

    return result


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

WRITE_CATEGORIES = {
    "high_prec_high_recall": {
        "label": "High Precision, High Recall",
        "explanation": "Agent edited the right files and covered most/all of them.",
    },
    "high_prec_low_recall": {
        "label": "High Precision, Low Recall",
        "explanation": "Agent was accurate but incomplete — missed files that needed changing.",
    },
    "low_prec_high_recall": {
        "label": "Low Precision, High Recall",
        "explanation": "Agent touched all required files but also modified many unnecessary ones.",
    },
    "low_prec_low_recall": {
        "label": "Low Precision, Low Recall",
        "explanation": "Agent both missed required files and edited wrong ones.",
    },
    "no_writes": {
        "label": "No Writes",
        "explanation": "Agent did not write to any files.",
    },
}

READ_CATEGORIES = {
    "high_prec_high_recall": {
        "label": "High Precision, High Recall",
        "explanation": "Efficient and thorough — reads the relevant files without wasting time.",
    },
    "high_prec_low_recall": {
        "label": "High Precision, Low Recall",
        "explanation": "Focused but narrow — reads few files and they're relevant, but misses context.",
    },
    "low_prec_high_recall": {
        "label": "Low Precision, High Recall",
        "explanation": "Thorough but noisy — reads everything including the right files.",
    },
    "low_prec_low_recall": {
        "label": "Low Precision, Low Recall",
        "explanation": "Poor navigation — doesn't find the relevant files and reads the wrong ones.",
    },
    "no_reads": {
        "label": "No Reads",
        "explanation": "Agent did not read any files.",
    },
}


def _categorize(stats_dict, prec_t, rec_t, no_label):
    if stats_dict["true_positives"] == 0 and stats_dict["false_positives"] == 0:
        return no_label
    high_p = stats_dict["precision"] >= prec_t
    high_r = stats_dict["recall"] >= rec_t
    if high_p and high_r:
        return "high_prec_high_recall"
    elif high_p:
        return "high_prec_low_recall"
    elif high_r:
        return "low_prec_high_recall"
    else:
        return "low_prec_low_recall"


def categorize_write(stats_dict, prec_t=DEFAULT_PRECISION_THRESHOLD, rec_t=DEFAULT_RECALL_THRESHOLD):
    return _categorize(stats_dict, prec_t, rec_t, "no_writes")


def categorize_read(stats_dict, prec_t=DEFAULT_PRECISION_THRESHOLD, rec_t=DEFAULT_RECALL_THRESHOLD):
    return _categorize(stats_dict, prec_t, rec_t, "no_reads")


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def _print_pr(label, stats_dict, dir_stats=False, all_stats=None, prefix=""):
    """Print precision/recall block."""
    s = stats_dict
    print(f"{prefix}{label}:")
    print(f"{prefix}  Recall:  {s['recall']:.2f}  Precision: {s['precision']:.2f}")
    print(f"{prefix}  TP={s['true_positives']}  FP={s['false_positives']}  FN={s['false_negatives']}")
    if dir_stats and all_stats:
        base = label.split(" ")[0].lower()  # "read" or "write"
        scope = label.split(" ")[-1].strip("()").lower() if "(" in label else ""
        for level in ("module", "package", "parent"):
            key = f"{scope}_{base}_{level}" if scope else f"{base}_{level}"
            if key in all_stats:
                d = all_stats[key]
                print(f"{prefix}  {level:>7}: recall={d['recall']:.2f}  precision={d['precision']:.2f}"
                      f"  (TP={d['true_positives']} FP={d['false_positives']} FN={d['false_negatives']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="File recall/precision stats for Claude Code trajectories with sub-agent breakdown"
    )
    parser.add_argument("input_dir", help="Directory containing *-output.zip trajectory files")
    parser.add_argument("--instance", type=str, default=None,
                        help="Inspect a single instance (detailed output)")
    parser.add_argument("--exclude-tests", action="store_true",
                        help="Exclude *Tests.java files from reads/writes")
    parser.add_argument("--resolved", action="store_true",
                        help="Only show resolved instances")
    parser.add_argument("--unresolved", action="store_true",
                        help="Only show unresolved instances")
    parser.add_argument("--categorize", action="store_true",
                        help="Group instances by write/read precision/recall category")
    parser.add_argument("--recall-threshold", type=float, default=DEFAULT_RECALL_THRESHOLD,
                        help=f"Recall threshold (default: {DEFAULT_RECALL_THRESHOLD})")
    parser.add_argument("--precision-threshold", type=float, default=DEFAULT_PRECISION_THRESHOLD,
                        help=f"Precision threshold (default: {DEFAULT_PRECISION_THRESHOLD})")
    parser.add_argument("--show-cmds", action="store_true",
                        help="Show the commands used to read each file (only with --instance)")
    parser.add_argument("--dir-stats", action="store_true",
                        help="Show directory-level (module/package/parent) precision/recall")
    parser.add_argument("--plot", action="store_true",
                        help="Scatter plot of combined write recall vs precision")
    parser.add_argument("--output-json", "-o", type=str, default=None,
                        help="Write detailed per-instance JSON results to file")
    args = parser.parse_args()

    zips = get_all_trajectory_zips(args.input_dir)
    if not zips:
        print(f"No *-output.zip files found in {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Single instance mode
    # -----------------------------------------------------------------------
    if args.instance:
        matched = [(z, iid) for z, iid in zips if iid == args.instance]
        if not matched:
            print(f"No trajectory found for instance: {args.instance}")
            return
        zip_path, instance_id = matched[0]
        resolved = is_resolved_from_zip(zip_path)
        source_files = source_files_from_instance_id(instance_id)
        print(f"Instance: {instance_id}")
        print(f"Resolved: {resolved}")
        print(f"\nGold source files ({len(source_files)}):")
        for sf in sorted(source_files):
            print(f"  {sf}")

        legacy_items = load_legacy_trajectory_from_zip(zip_path)
        main_reads, main_writes, sa_reads, sa_writes, sa_stats = extract_reads_writes(legacy_items)
        stats = compute_stats(main_reads, main_writes, sa_reads, sa_writes,
                              source_files, exclude_tests=args.exclude_tests)

        # Sub-agent overview
        print(f"\nTotal tool calls: {sa_stats['total_items']}  "
              f"(main: {sa_stats['main_tool_count']}, sub-agent: {sa_stats['total_subagent_steps']})")
        print(f"Sub-agent invocations: {sa_stats['num_subagent_calls']}")
        if sa_stats["subagent_type_counts"]:
            for stype, cnt in sorted(sa_stats["subagent_type_counts"].items()):
                print(f"  {stype}: {cnt}")
        if sa_stats["per_invocation_steps"]:
            inv = _safe_stats(sa_stats["per_invocation_steps"])
            print(f"  Steps per invocation: mean={inv['mean']}, median={inv['median']}, "
                  f"min={inv['min']}, max={inv['max']}")

        # Print reads / writes per scope
        all_reads = {**main_reads}
        for p, descs in sa_reads.items():
            all_reads.setdefault(p, []).extend(descs)

        print(f"\n--- Main agent reads ({len(main_reads)}) ---")
        for r in sorted(main_reads):
            print(f"  R: {r}")
            if args.show_cmds:
                for cmd in main_reads[r]:
                    print(f"     {cmd}")

        print(f"\n--- Sub-agent reads ({len(sa_reads)}) ---")
        for r in sorted(sa_reads):
            marker = " *" if r not in main_reads else ""
            print(f"  R: {r}{marker}")
            if args.show_cmds:
                for cmd in sa_reads[r]:
                    print(f"     {cmd}")

        print(f"\n--- Main agent writes ({len(main_writes)}) ---")
        for w in sorted(main_writes):
            print(f"  W: {w}")

        print(f"\n--- Sub-agent writes ({len(sa_writes)}) ---")
        for w in sorted(sa_writes):
            marker = " *" if w not in main_writes else ""
            print(f"  W: {w}{marker}")

        # Stats per scope
        for scope in ("main", "subagent", "combined"):
            print(f"\n{'=' * 50}")
            print(f"  {scope.upper()} SCOPE")
            print(f"{'=' * 50}")
            for kind in ("read", "write"):
                key = f"{scope}_{kind}"
                s = stats[key]
                print(f"\n  {kind.upper()} (file-level):")
                print(f"    Recall:  {s['recall']:.2f}  Precision: {s['precision']:.2f}")
                print(f"    TP={s['true_positives']}  FP={s['false_positives']}  FN={s['false_negatives']}")
                if args.dir_stats:
                    for level in ("module", "package", "parent"):
                        d = stats[f"{scope}_{kind}_{level}"]
                        print(f"    {level:>7}: recall={d['recall']:.2f}  precision={d['precision']:.2f}"
                              f"  (TP={d['true_positives']} FP={d['false_positives']} FN={d['false_negatives']})")

        # Unique sub-agent contribution
        print(f"\n--- Sub-agent unique contributions ---")
        print(f"  Unique reads:  {stats['subagent_unique_reads']} (TP={stats['subagent_unique_reads_tp']})")
        print(f"  Unique writes: {stats['subagent_unique_writes']} (TP={stats['subagent_unique_writes_tp']})")
        return

    # -----------------------------------------------------------------------
    # Summary mode
    # -----------------------------------------------------------------------
    collectors = {
        scope: {
            "read_recall": [], "read_precision": [],
            "write_recall": [], "write_precision": [],
        }
        for scope in ("main", "subagent", "combined")
    }
    all_sa_counts = []
    all_sa_steps = []
    all_main_steps = []
    all_total_steps = []
    all_sa_unique_reads = []
    all_sa_unique_reads_tp = []
    all_sa_unique_writes = []
    all_sa_unique_writes_tp = []
    instances_with_sa = 0
    per_instance_json = []

    for zip_path, instance_id in zips:
        resolved = is_resolved_from_zip(zip_path)
        if args.resolved and not resolved:
            continue
        if args.unresolved and resolved:
            continue

        source_files = source_files_from_instance_id(instance_id)
        try:
            legacy_items = load_legacy_trajectory_from_zip(zip_path)
        except (KeyError, zipfile.BadZipFile) as e:
            print(f"WARN: skipping {instance_id}: {e}", file=sys.stderr)
            continue

        main_reads, main_writes, sa_reads, sa_writes, sa_stats = extract_reads_writes(legacy_items)
        stats = compute_stats(main_reads, main_writes, sa_reads, sa_writes,
                              source_files, exclude_tests=args.exclude_tests)

        for scope in ("main", "subagent", "combined"):
            collectors[scope]["read_recall"].append(stats[f"{scope}_read"]["recall"])
            collectors[scope]["read_precision"].append(stats[f"{scope}_read"]["precision"])
            collectors[scope]["write_recall"].append(stats[f"{scope}_write"]["recall"])
            collectors[scope]["write_precision"].append(stats[f"{scope}_write"]["precision"])

        all_sa_counts.append(sa_stats["num_subagent_calls"])
        all_sa_steps.append(sa_stats["total_subagent_steps"])
        all_main_steps.append(sa_stats["main_tool_count"])
        all_total_steps.append(sa_stats["total_items"])
        all_sa_unique_reads.append(stats["subagent_unique_reads"])
        all_sa_unique_reads_tp.append(stats["subagent_unique_reads_tp"])
        all_sa_unique_writes.append(stats["subagent_unique_writes"])
        all_sa_unique_writes_tp.append(stats["subagent_unique_writes_tp"])
        if sa_stats["num_subagent_calls"] > 0:
            instances_with_sa += 1

        status = "RESOLVED" if resolved else "UNRESOLVED"
        cr = stats["combined_read"]
        cw = stats["combined_write"]
        mr = stats["main_read"]
        mw = stats["main_write"]
        line = (f"{instance_id}  {status}  "
                f"comb_r_rec={cr['recall']:.2f}  comb_r_prec={cr['precision']:.2f}  "
                f"comb_w_rec={cw['recall']:.2f}  comb_w_prec={cw['precision']:.2f}  "
                f"main_w_rec={mw['recall']:.2f}  main_w_prec={mw['precision']:.2f}  "
                f"sa_calls={sa_stats['num_subagent_calls']}  "
                f"sa_uniq_r={stats['subagent_unique_reads']}({stats['subagent_unique_reads_tp']}tp)")
        if args.dir_stats:
            for level in ("module", "package", "parent"):
                cd = stats[f"combined_write_{level}"]
                line += f"  cw_{level[:3]}={cd['recall']:.2f}"
        print(line)

        per_instance_json.append({
            "instance_id": instance_id,
            "resolved": resolved,
            "stats": stats,
            "subagent_stats": sa_stats,
        })

    n = len(collectors["combined"]["read_recall"])
    if n > 0:
        print(f"\n{'=' * 70}")
        print(f"AVERAGES ({n} instances)")
        for scope in ("main", "subagent", "combined"):
            c = collectors[scope]
            print(f"\n  {scope.upper()}:")
            print(f"    Avg Read Recall:     {sum(c['read_recall']) / n:.2f}")
            print(f"    Avg Read Precision:  {sum(c['read_precision']) / n:.2f}")
            print(f"    Avg Write Recall:    {sum(c['write_recall']) / n:.2f}")
            print(f"    Avg Write Precision: {sum(c['write_precision']) / n:.2f}")

        print(f"\n  COMBINED vs MAIN-ONLY delta:")
        mc = collectors["main"]
        cc = collectors["combined"]
        print(f"    Read Recall:  main={sum(mc['read_recall'])/n:.2f}  "
              f"combined={sum(cc['read_recall'])/n:.2f}  "
              f"delta=+{(sum(cc['read_recall'])-sum(mc['read_recall']))/n:.3f}")
        print(f"    Write Recall: main={sum(mc['write_recall'])/n:.2f}  "
              f"combined={sum(cc['write_recall'])/n:.2f}  "
              f"delta=+{(sum(cc['write_recall'])-sum(mc['write_recall']))/n:.3f}")
        print(f"    Read Prec:    main={sum(mc['read_precision'])/n:.2f}  "
              f"combined={sum(cc['read_precision'])/n:.2f}  "
              f"delta={(sum(cc['read_precision'])-sum(mc['read_precision']))/n:+.3f}")
        print(f"    Write Prec:   main={sum(mc['write_precision'])/n:.2f}  "
              f"combined={sum(cc['write_precision'])/n:.2f}  "
              f"delta={(sum(cc['write_precision'])-sum(mc['write_precision']))/n:+.3f}")

        print(f"\n{'=' * 70}")
        print(f"SUB-AGENT STATISTICS")
        print(f"  Instances with sub-agents: {instances_with_sa}/{n}")
        print(f"  Sub-agent calls/instance:  {_safe_stats(all_sa_counts)}")
        print(f"  Sub-agent steps/instance:  {_safe_stats(all_sa_steps)}")
        print(f"  Main steps/instance:       {_safe_stats(all_main_steps)}")
        print(f"  Total steps/instance:      {_safe_stats(all_total_steps)}")
        print(f"\n  Sub-agent unique file contributions:")
        print(f"    Unique reads/instance:  {_safe_stats(all_sa_unique_reads)}")
        print(f"    Unique reads TP/instance: {_safe_stats(all_sa_unique_reads_tp)}")
        print(f"    Unique writes/instance: {_safe_stats(all_sa_unique_writes)}")
        print(f"    Unique writes TP/instance: {_safe_stats(all_sa_unique_writes_tp)}")
        print(f"{'=' * 70}")

    # -----------------------------------------------------------------------
    # Categorize
    # -----------------------------------------------------------------------
    if args.categorize:
        write_buckets = {k: [] for k in WRITE_CATEGORIES}
        read_buckets = {k: [] for k in READ_CATEGORIES}
        for entry in per_instance_json:
            if args.resolved and not entry["resolved"]:
                continue
            if args.unresolved and entry["resolved"]:
                continue
            if not args.resolved and not args.unresolved and entry["resolved"]:
                continue
            st = entry["stats"]
            w_cat = categorize_write(st["combined_write"], args.precision_threshold, args.recall_threshold)
            r_cat = categorize_read(st["combined_read"], args.precision_threshold, args.recall_threshold)
            write_buckets[w_cat].append(entry)
            read_buckets[r_cat].append(entry)

        filter_label = "RESOLVED" if args.resolved else "UNRESOLVED" if args.unresolved else "UNRESOLVED"
        print(f"\n{'=' * 70}")
        print(f"{filter_label} — COMBINED WRITE CATEGORIES")
        print(f"  Thresholds: precision >= {args.precision_threshold}, recall >= {args.recall_threshold}")
        print(f"{'=' * 70}")
        for cat_key, cat_info in WRITE_CATEGORIES.items():
            entries = write_buckets[cat_key]
            print(f"\n--- {cat_info['label']} ({len(entries)}) ---")
            print(f"    {cat_info['explanation']}")
            for e in entries:
                cw = e["stats"]["combined_write"]
                mw = e["stats"]["main_write"]
                print(f"    {e['instance_id']}  combined_w={cw['recall']:.2f}/{cw['precision']:.2f}"
                      f"  main_w={mw['recall']:.2f}/{mw['precision']:.2f}")

        print(f"\n{'=' * 70}")
        print(f"{filter_label} — COMBINED READ CATEGORIES")
        print(f"  Thresholds: precision >= {args.precision_threshold}, recall >= {args.recall_threshold}")
        print(f"{'=' * 70}")
        for cat_key, cat_info in READ_CATEGORIES.items():
            entries = read_buckets[cat_key]
            print(f"\n--- {cat_info['label']} ({len(entries)}) ---")
            print(f"    {cat_info['explanation']}")
            for e in entries:
                cr = e["stats"]["combined_read"]
                mr = e["stats"]["main_read"]
                print(f"    {e['instance_id']}  combined_r={cr['recall']:.2f}/{cr['precision']:.2f}"
                      f"  main_r={mr['recall']:.2f}/{mr['precision']:.2f}")

    # -----------------------------------------------------------------------
    # Plot
    # -----------------------------------------------------------------------
    if args.plot:
        resolved_main = []
        resolved_comb = []
        unresolved_main = []
        unresolved_comb = []
        for e in per_instance_json:
            mw = e["stats"]["main_write"]
            cw = e["stats"]["combined_write"]
            if e["resolved"]:
                resolved_main.append((mw["recall"], mw["precision"]))
                resolved_comb.append((cw["recall"], cw["precision"]))
            else:
                unresolved_main.append((mw["recall"], mw["precision"]))
                unresolved_comb.append((cw["recall"], cw["precision"]))

        fig, axes = plt.subplots(1, 2, figsize=(16, 7))
        for ax, title, res_pts, unres_pts in [
            (axes[0], "Main Agent Only — Write Recall vs Precision", resolved_main, unresolved_main),
            (axes[1], "Combined (Main + Sub-agents) — Write Recall vs Precision", resolved_comb, unresolved_comb),
        ]:
            if res_pts:
                ax.scatter([p[0] for p in res_pts], [p[1] for p in res_pts],
                           c="green", label="Resolved", alpha=0.7, edgecolors="black", s=60)
            if unres_pts:
                ax.scatter([p[0] for p in unres_pts], [p[1] for p in unres_pts],
                           c="red", label="Unresolved", alpha=0.7, edgecolors="black", s=60)
            ax.axhline(y=args.precision_threshold, color="gray", linestyle="--", linewidth=1)
            ax.axvline(x=args.recall_threshold, color="gray", linestyle="--", linewidth=1)
            ax.set_xlabel("Write Recall", fontsize=12)
            ax.set_ylabel("Write Precision", fontsize=12)
            ax.set_title(title, fontsize=13)
            ax.set_xlim(-0.05, 1.05)
            ax.set_ylim(-0.05, 1.05)
            ax.legend()
            ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    # -----------------------------------------------------------------------
    # JSON output
    # -----------------------------------------------------------------------
    if args.output_json and per_instance_json:
        output = {
            "num_instances": n,
            "averages": {
                scope: {
                    "read_recall": round(sum(collectors[scope]["read_recall"]) / n, 3),
                    "read_precision": round(sum(collectors[scope]["read_precision"]) / n, 3),
                    "write_recall": round(sum(collectors[scope]["write_recall"]) / n, 3),
                    "write_precision": round(sum(collectors[scope]["write_precision"]) / n, 3),
                }
                for scope in ("main", "subagent", "combined")
            },
            "per_instance": per_instance_json,
        }
        with open(args.output_json, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nDetailed results written to {args.output_json}")


if __name__ == "__main__":
    main()
