import argparse
import json
import re
import os
import statistics
from collections import Counter, defaultdict
import matplotlib.pyplot as plt

TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/claude-code-full-msbench/outputs/"
INSTANCE_STATS = "/Users/pontusberglund/Documents/GitHub/swebench-xl/analysis/instance_stats_output.json"

# Directory name pattern: swebench-xl-v1.eval.x86_64.{instance_id}-output
DIR_PREFIX = "swebench-xl-v1.eval.x86_64."
DIR_SUFFIX = "-output"


def get_steps(trajectory):
    return trajectory["steps"]


def load_trajectory(file_path):
    with open(file_path, "r") as f:
        trajectory = json.load(f)
    return trajectory


def load_legacy_trajectory(file_path):
    """Load trajectory_legacy.json which is a flat list of all tool calls."""
    with open(file_path, "r") as f:
        return json.load(f)


def get_steps_with_tool_calls(steps):
    steps_with_tool_calls = []
    for step in steps:
        if "tool_calls" in step and step["tool_calls"]:
            steps_with_tool_calls.append(step)
    return steps_with_tool_calls


def _is_non_read_command(cmd):
    """Return True if the command is not investigative (doesn't read file content)."""
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
    write_prefixes = (
        "sed ", "sed -i",
        "echo ", "printf ",
        "tee ",
    )
    # Check for redirections that write to files
    if ">>" in cmd or re.search(r'[^>]>[^>]', cmd):
        return True
    return stripped.startswith(write_prefixes)


def _is_valid_source_path(path):
    """Return True if path looks like an actual source file, not a dir or build artifact."""
    if path.endswith('/'):
        return False
    basename = os.path.basename(path)
    if '.' not in basename:
        return False
    if '/build/' in path or '/target/' in path:
        return False
    if path.endswith('.class'):
        return False
    return True


def _extract_paths_from_command(cmd):
    """Extract file paths from a bash command."""
    paths = []
    # Match absolute /app/ paths
    abs_paths = re.findall(r'(/app/[^\s\'\"\\|>;]+)', cmd)
    for p in abs_paths:
        clean = p.rstrip(".,;:)(")
        paths.append(clean)
    # Match relative paths and normalise to /app/
    rel_paths = re.findall(r'(?:^|\s)([a-zA-Z0-9_.][^\s\'\"\\|>;]*\.[a-zA-Z0-9]+)', cmd)
    for p in rel_paths:
        clean = p.rstrip(".,;:)(")
        if '/' in clean and not clean.startswith('/'):
            paths.append(f"/app/{clean}")
    return [p for p in paths if _is_valid_source_path(p)]


def get_reads_and_writes(steps):
    """Extract read and written file paths from Claude Code trajectory steps.

    Tool mapping:
      Read   -> read (file_path)
      Grep   -> read (path, if present; otherwise repo-wide, skip)
      Glob   -> skip (just lists file names)
      Bash   -> read or write depending on command content
      Edit   -> write (file_path)
      Write  -> write (file_path) — only /app/ paths, not plan files
      Agent  -> skip (sub-agent delegation)
    """
    reads = {}   # path -> [source descriptions]
    writes = set()

    for step in steps:
        for tool_call in step.get("tool_calls", []):
            fn = tool_call.get("function_name", "")
            args = tool_call.get("arguments", {})
            if not isinstance(args, dict):
                continue

            if fn == "Read":
                file_path = args.get("file_path", "")
                if file_path and _is_valid_source_path(file_path):
                    reads.setdefault(file_path, []).append(f"Read {file_path}")

            elif fn == "Grep":
                path = args.get("path", "")
                if path and _is_valid_source_path(path):
                    reads.setdefault(path, []).append(
                        f"Grep pattern={args.get('pattern', '')} path={path}"
                    )

            elif fn == "Bash":
                cmd = args.get("command", "")
                if not cmd:
                    continue
                extracted = _extract_paths_from_command(cmd)
                if _is_write_command(cmd):
                    for p in extracted:
                        writes.add(p)
                elif not _is_non_read_command(cmd):
                    for p in extracted:
                        reads.setdefault(p, []).append(f"Bash: {cmd}")

            elif fn == "Edit":
                file_path = args.get("file_path", "")
                if file_path and _is_valid_source_path(file_path):
                    writes.add(file_path)

            elif fn == "Write":
                file_path = args.get("file_path", "")
                # Only count writes to /app/ (ignore plan files etc.)
                if file_path and file_path.startswith("/app/") and _is_valid_source_path(file_path):
                    writes.add(file_path)

    return reads, list(writes)


def _parse_legacy_action(action_str):
    """Parse the 'action' field from legacy trajectory (JSON string -> dict)."""
    if not action_str:
        return {}
    try:
        return json.loads(action_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def get_reads_and_writes_legacy(legacy_items, include_subagents=True):
    """Extract read and written file paths from legacy trajectory items.

    Each item has 'tool', 'action' (JSON string), and optionally 'parent_tool_use_id'.
    If include_subagents is False, items with parent_tool_use_id are skipped.

    Returns (reads, writes, subagent_stats) where subagent_stats is a dict with
    sub-agent usage information.
    """
    reads = {}   # path -> [source descriptions]
    writes = set()
    # Sub-agent tracking
    subagent_calls = []  # list of Agent call items
    subagent_steps = defaultdict(list)  # parent_id -> [items]
    main_tool_count = 0
    total_items = len(legacy_items)

    for item in legacy_items:
        fn = item.get("tool", "")
        parent_id = item.get("parent_tool_use_id")
        args = _parse_legacy_action(item.get("action", ""))

        # Track sub-agent structure
        if fn == "Agent" and not parent_id:
            subagent_calls.append(item)
            main_tool_count += 1
            continue
        if parent_id:
            subagent_steps[parent_id].append(item)
            if not include_subagents:
                continue
        else:
            main_tool_count += 1

        # Extract reads/writes (same logic as get_reads_and_writes)
        if fn == "Read":
            file_path = args.get("file_path", "")
            if file_path and _is_valid_source_path(file_path):
                src = f"[sub-agent] Read {file_path}" if parent_id else f"Read {file_path}"
                reads.setdefault(file_path, []).append(src)

        elif fn == "Grep":
            path = args.get("path", "")
            if path and _is_valid_source_path(path):
                src = f"[sub-agent] Grep" if parent_id else "Grep"
                reads.setdefault(path, []).append(
                    f"{src} pattern={args.get('pattern', '')} path={path}"
                )

        elif fn == "Bash":
            cmd = args.get("command", "")
            if not cmd:
                continue
            extracted = _extract_paths_from_command(cmd)
            if _is_write_command(cmd):
                for p in extracted:
                    writes.add(p)
            elif not _is_non_read_command(cmd):
                for p in extracted:
                    src = f"[sub-agent] Bash: {cmd}" if parent_id else f"Bash: {cmd}"
                    reads.setdefault(p, []).append(src)

        elif fn == "Edit":
            file_path = args.get("file_path", "")
            if file_path and _is_valid_source_path(file_path):
                writes.add(file_path)

        elif fn == "Write":
            file_path = args.get("file_path", "")
            if file_path and file_path.startswith("/app/") and _is_valid_source_path(file_path):
                writes.add(file_path)

    # Build sub-agent stats
    subagent_details = []
    for ac in subagent_calls:
        ac_args = _parse_legacy_action(ac.get("action", ""))
        # Match by looking for items whose parent_tool_use_id could match;
        # in legacy format we match by order: Agent calls don't have an ID field,
        # but sub-agent items have parent_tool_use_id. Collect all parent IDs.
        pass

    # Collect unique parent IDs
    all_parent_ids = set()
    for item in legacy_items:
        pid = item.get("parent_tool_use_id")
        if pid:
            all_parent_ids.add(pid)

    total_subagent_steps = sum(len(v) for v in subagent_steps.values())
    per_invocation_steps = [len(subagent_steps[pid]) for pid in all_parent_ids] if all_parent_ids else []

    # Tool breakdown across all sub-agent steps
    subagent_tool_counts = Counter()
    for steps_list in subagent_steps.values():
        for s in steps_list:
            subagent_tool_counts[s.get("tool", "unknown")] += 1

    # Per sub-agent type breakdown
    type_counts = Counter()
    for ac in subagent_calls:
        ac_args = _parse_legacy_action(ac.get("action", ""))
        type_counts[ac_args.get("subagent_type", "unknown")] += 1

    subagent_stats = {
        "num_subagent_calls": len(subagent_calls),
        "num_unique_parent_ids": len(all_parent_ids),
        "total_subagent_steps": total_subagent_steps,
        "main_tool_count": main_tool_count,
        "total_items": total_items,
        "per_invocation_steps": per_invocation_steps,
        "subagent_tool_counts": dict(subagent_tool_counts),
        "subagent_type_counts": dict(type_counts),
    }

    return reads, list(writes), subagent_stats


def _safe_stats(values):
    """Compute mean/median/min/max/stdev for a list of numbers."""
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


def _instance_id_from_dirname(dirname):
    """Extract instance_id (e.g. 'elastic__elasticsearch-135899') from directory name."""
    # Pattern: swebench-xl-v1.eval.x86_64.{instance_id}-output
    if dirname.startswith(DIR_PREFIX) and dirname.endswith(DIR_SUFFIX):
        return dirname[len(DIR_PREFIX):-len(DIR_SUFFIX)]
    return None


def get_all_trajectory_files(trajectory_dir):
    """Walk the outputs directory and return (legacy_path, instance_id) pairs.

    Uses trajectory_legacy.json which includes both main-agent and sub-agent tool calls.
    """
    trajectory_file_and_instance_id = []
    for dirname in os.listdir(trajectory_dir):
        instance_id = _instance_id_from_dirname(dirname)
        if instance_id is None:
            continue
        legacy_path = os.path.join(
            trajectory_dir, dirname, "output", "trajectories", "trajectory_legacy.json"
        )
        if os.path.isfile(legacy_path):
            trajectory_file_and_instance_id.append((legacy_path, instance_id))
    return sorted(trajectory_file_and_instance_id, key=lambda x: x[1])


def source_files_from_instance_id(instance_id):
    with open(INSTANCE_STATS, "r") as f:
        instance_stats = json.load(f)
    for instance in instance_stats["instances"]:
        if instance["instance_id"] == instance_id:
            return instance.get("source_files", [])
    return []


def _extract_semantic_dirs(path):
    """Extract module, package, and parent directory from a path."""
    parent = os.path.dirname(path)

    src_idx = path.find("/src/")
    if src_idx != -1:
        module = path[:src_idx]
    else:
        parts = path.split("/")
        module = "/".join(parts[:min(4, len(parts))])

    java_idx = path.find("/java/")
    if java_idx != -1:
        after_java = path[java_idx + len("/java/"):]
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
    tp = len(predicted_set.intersection(gold_set))
    fp = len(predicted_set.difference(gold_set))
    fn = len(gold_set.difference(predicted_set))
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    return {
        "recall": recall,
        "precision": precision,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }


def _is_test_file(path):
    return os.path.basename(path).endswith("Tests.java")


DEFAULT_RECALL_THRESHOLD = 0.67
DEFAULT_PRECISION_THRESHOLD = 0.67

# Gold patch files to exclude from source set (matched by basename)
EXCLUDED_GOLD_FILES = [
    "EsqlCapabilities.java",
]

WRITE_CATEGORIES = {
    "high_prec_high_recall": {
        "label": "High Precision, High Recall",
        "explanation": "Agent edited the right files and covered most/all of them. "
                       "Failure likely due to incorrect content in the edits, not file targeting.",
    },
    "high_prec_low_recall": {
        "label": "High Precision, Low Recall",
        "explanation": "Agent was accurate but incomplete — every file it edited was correct, "
                       "but it missed files that needed changing. Patch is partial.",
    },
    "low_prec_high_recall": {
        "label": "Low Precision, High Recall",
        "explanation": "Agent touched all required files but also modified many unnecessary ones. "
                       "Scattershot approach — finds the target but makes noisy, risky edits.",
    },
    "low_prec_low_recall": {
        "label": "Low Precision, Low Recall",
        "explanation": "Agent both missed required files and edited wrong ones. "
                       "Poor file localization overall.",
    },
    "no_writes": {
        "label": "No Writes",
        "explanation": "Agent did not write to any files. It may have failed to produce a patch entirely.",
    },
}


def categorize_write_stats(write_stats, precision_threshold=DEFAULT_PRECISION_THRESHOLD, recall_threshold=DEFAULT_RECALL_THRESHOLD):
    if write_stats["true_positives"] == 0 and write_stats["false_positives"] == 0:
        return "no_writes"
    high_p = write_stats["precision"] >= precision_threshold
    high_r = write_stats["recall"] >= recall_threshold
    if high_p and high_r:
        return "high_prec_high_recall"
    elif high_p and not high_r:
        return "high_prec_low_recall"
    elif not high_p and high_r:
        return "low_prec_high_recall"
    else:
        return "low_prec_low_recall"


READ_CATEGORIES = {
    "high_prec_high_recall": {
        "label": "High Precision, High Recall",
        "explanation": "Efficient and thorough — reads the relevant files without "
                       "wasting time on irrelevant ones.",
    },
    "high_prec_low_recall": {
        "label": "High Precision, Low Recall",
        "explanation": "Focused but narrow — reads few files and they're relevant, "
                       "but misses important context.",
    },
    "low_prec_high_recall": {
        "label": "Low Precision, High Recall",
        "explanation": "Thorough but noisy — reads everything including the right files, "
                       "but wastes time exploring many irrelevant ones.",
    },
    "low_prec_low_recall": {
        "label": "Low Precision, Low Recall",
        "explanation": "Poor navigation — doesn't find the relevant files and reads "
                       "the wrong ones.",
    },
    "no_reads": {
        "label": "No Reads",
        "explanation": "Agent did not read any files.",
    },
}


def categorize_read_stats(read_stats, precision_threshold=DEFAULT_PRECISION_THRESHOLD, recall_threshold=DEFAULT_RECALL_THRESHOLD):
    if read_stats["true_positives"] == 0 and read_stats["false_positives"] == 0:
        return "no_reads"
    high_p = read_stats["precision"] >= precision_threshold
    high_r = read_stats["recall"] >= recall_threshold
    if high_p and high_r:
        return "high_prec_high_recall"
    elif high_p and not high_r:
        return "high_prec_low_recall"
    elif not high_p and high_r:
        return "low_prec_high_recall"
    else:
        return "low_prec_low_recall"


def get_recall_precision_stats_legacy(legacy_items, source_files, exclude_tests=False, include_subagents=True):
    """Compute recall/precision from legacy trajectory items."""
    reads, writes, subagent_stats = get_reads_and_writes_legacy(legacy_items, include_subagents=include_subagents)

    read_set = set(reads)
    write_set = set(writes)

    if exclude_tests:
        read_set = {p for p in read_set if not _is_test_file(p)}
        write_set = {p for p in write_set if not _is_test_file(p)}

    source_set = set(f"/app/{s.lstrip('/')}" for s in source_files)
    source_set = {s for s in source_set if os.path.basename(s) not in EXCLUDED_GOLD_FILES}

    result = {
        "read": _precision_recall(read_set, source_set),
        "write": _precision_recall(write_set, source_set),
        "subagent_stats": subagent_stats,
    }

    for level in ("module", "package", "parent"):
        read_dirs = _map_to_dir_sets(read_set, level)
        write_dirs = _map_to_dir_sets(write_set, level)
        source_dirs = _map_to_dir_sets(source_set, level)
        result[f"read_{level}"] = _precision_recall(read_dirs, source_dirs)
        result[f"write_{level}"] = _precision_recall(write_dirs, source_dirs)

    return result, reads, writes


def is_resolved(instance_id):
    """Check resolution from the per-instance eval.json file."""
    eval_dir = os.path.join(
        TRAJECTORY_DIR,
        f"{DIR_PREFIX}{instance_id}{DIR_SUFFIX}",
        "output",
        "eval.json",
    )
    if not os.path.isfile(eval_dir):
        return False
    with open(eval_dir, "r") as f:
        eval_data = json.load(f)
    for iid, info in eval_data.items():
        if info.get("resolved", False):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="File recall/precision stats for Claude Code trajectories")
    parser.add_argument("--instance", type=str, default=None,
                        help="Instance ID to inspect (prints source files and all reads/writes)")
    parser.add_argument("--exclude-tests", action="store_true",
                        help="Exclude *Tests.java files from reads/writes")
    parser.add_argument("--resolved", action="store_true",
                        help="Only show resolved instances")
    parser.add_argument("--unresolved", action="store_true",
                        help="Only show unresolved instances")
    parser.add_argument("--categorize", action="store_true",
                        help="Group instances by write/read precision/recall category")
    parser.add_argument("--recall-threshold", type=float, default=DEFAULT_RECALL_THRESHOLD,
                        help=f"Recall threshold for high/low categorization (default: {DEFAULT_RECALL_THRESHOLD})")
    parser.add_argument("--precision-threshold", type=float, default=DEFAULT_PRECISION_THRESHOLD,
                        help=f"Precision threshold for high/low categorization (default: {DEFAULT_PRECISION_THRESHOLD})")
    parser.add_argument("--show-cmds", action="store_true",
                        help="Show the commands used to read each file (only with --instance)")
    parser.add_argument("--dir-stats", action="store_true",
                        help="Show directory-level (module/package/parent) precision/recall")
    parser.add_argument("--plot", action="store_true",
                        help="Generate a scatter plot of write recall vs precision")
    parser.add_argument("--no-subagents", action="store_true",
                        help="Exclude sub-agent reads/writes (main agent only)")
    args = parser.parse_args()

    include_sa = not args.no_subagents

    trajectory_files = get_all_trajectory_files(TRAJECTORY_DIR)

    if args.instance:
        matched = [(f, iid) for f, iid in trajectory_files if iid == args.instance]
        if not matched:
            print(f"No trajectory found for instance: {args.instance}")
            return
        resolved = is_resolved(args.instance)
        source_files = source_files_from_instance_id(args.instance)
        print(f"Instance: {args.instance}")
        print(f"Resolved: {resolved}")
        print(f"\nSource files ({len(source_files)}):")
        for sf in sorted(source_files):
            print(f"  {sf}")
        for file, _ in matched:
            legacy_items = load_legacy_trajectory(file)
            stats, reads, writes = get_recall_precision_stats_legacy(
                legacy_items, source_files, exclude_tests=args.exclude_tests,
                include_subagents=include_sa,
            )
            sa = stats["subagent_stats"]
            print(f"\nTrajectory: {file}")
            print(f"Total tool calls: {sa['total_items']}  (main: {sa['main_tool_count']}, sub-agent: {sa['total_subagent_steps']})")
            print(f"Sub-agent invocations: {sa['num_subagent_calls']}")
            if sa["subagent_type_counts"]:
                for stype, cnt in sorted(sa["subagent_type_counts"].items()):
                    print(f"  {stype}: {cnt}")
            if sa["per_invocation_steps"]:
                inv_stats = _safe_stats(sa["per_invocation_steps"])
                print(f"  Steps per invocation: mean={inv_stats['mean']}, median={inv_stats['median']}, min={inv_stats['min']}, max={inv_stats['max']}")
            if sa["subagent_tool_counts"]:
                print(f"  Sub-agent tool breakdown:")
                for tool, cnt in sorted(sa["subagent_tool_counts"].items(), key=lambda x: -x[1]):
                    print(f"    {tool}: {cnt}")
            print(f"\nReads ({len(reads)}):")
            for r in sorted(reads):
                print(f"  R: {r}")
                if args.show_cmds:
                    for cmd in reads[r]:
                        print(f"     cmd: {cmd}")
            print(f"Writes ({len(writes)}):")
            for w in sorted(writes):
                print(f"  W: {w}")
            for kind in ("read", "write"):
                s = stats[kind]
                print(f"\n{kind.upper()} stats (file-level):")
                print(f"  Recall:  {s['recall']:.2f}")
                print(f"  Precision: {s['precision']:.2f}")
                print(f"  True Positives:  {s['true_positives']}")
                print(f"  False Positives: {s['false_positives']}")
                print(f"  False Negatives: {s['false_negatives']}")
                for level in ("module", "package", "parent"):
                    d = stats[f"{kind}_{level}"]
                    print(f"  {level:>7}: recall={d['recall']:.2f}  precision={d['precision']:.2f}  (TP={d['true_positives']} FP={d['false_positives']} FN={d['false_negatives']})")
    else:
        all_read_recalls = []
        all_read_precisions = []
        all_write_recalls = []
        all_write_precisions = []
        all_subagent_counts = []
        all_subagent_steps = []
        all_main_steps = []
        all_total_steps = []
        instances_with_subagents = 0
        for file, instance_id in trajectory_files:
            resolved = is_resolved(instance_id)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            source_files = source_files_from_instance_id(instance_id)
            legacy_items = load_legacy_trajectory(file)
            stats, _, _ = get_recall_precision_stats_legacy(
                legacy_items, source_files, exclude_tests=args.exclude_tests,
                include_subagents=include_sa,
            )
            r, w = stats["read"], stats["write"]
            sa = stats["subagent_stats"]
            all_read_recalls.append(r["recall"])
            all_read_precisions.append(r["precision"])
            all_write_recalls.append(w["recall"])
            all_write_precisions.append(w["precision"])
            all_subagent_counts.append(sa["num_subagent_calls"])
            all_subagent_steps.append(sa["total_subagent_steps"])
            all_main_steps.append(sa["main_tool_count"])
            all_total_steps.append(sa["total_items"])
            if sa["num_subagent_calls"] > 0:
                instances_with_subagents += 1
            status = "RESOLVED" if resolved else "UNRESOLVED"
            line = f"{instance_id}  {status}  read_recall={r['recall']:.2f}  read_precision={r['precision']:.2f}  write_recall={w['recall']:.2f}  write_precision={w['precision']:.2f}  subagents={sa['num_subagent_calls']}  sa_steps={sa['total_subagent_steps']}"
            if args.dir_stats:
                for level in ("module", "package", "parent"):
                    rd = stats[f"read_{level}"]
                    wd = stats[f"write_{level}"]
                    line += f"  r_{level[:3]}={rd['recall']:.2f}  w_{level[:3]}={wd['recall']:.2f}"
            print(line)

        n = len(all_read_recalls)
        if n > 0:
            print(f"\n{'=' * 60}")
            print(f"AVERAGES ({n} instances)")
            print(f"  Avg Read Recall:     {sum(all_read_recalls) / n:.2f}")
            print(f"  Avg Read Precision:  {sum(all_read_precisions) / n:.2f}")
            print(f"  Avg Write Recall:    {sum(all_write_recalls) / n:.2f}")
            print(f"  Avg Write Precision: {sum(all_write_precisions) / n:.2f}")
            print(f"{'=' * 60}")
            print(f"\nSUB-AGENT STATISTICS ({n} instances)")
            print(f"  Instances with sub-agents: {instances_with_subagents}/{n}")
            sa_count_stats = _safe_stats(all_subagent_counts)
            print(f"  Sub-agent calls per instance: mean={sa_count_stats['mean']}, median={sa_count_stats['median']}, min={sa_count_stats['min']}, max={sa_count_stats['max']}")
            sa_step_stats = _safe_stats(all_subagent_steps)
            print(f"  Sub-agent steps per instance: mean={sa_step_stats['mean']}, median={sa_step_stats['median']}, min={sa_step_stats['min']}, max={sa_step_stats['max']}")
            main_stats = _safe_stats(all_main_steps)
            print(f"  Main-agent steps per instance: mean={main_stats['mean']}, median={main_stats['median']}, min={main_stats['min']}, max={main_stats['max']}")
            total_stats = _safe_stats(all_total_steps)
            print(f"  Total steps per instance: mean={total_stats['mean']}, median={total_stats['median']}, min={total_stats['min']}, max={total_stats['max']}")
            print(f"{'=' * 60}")

    if args.categorize:
        write_buckets = {k: [] for k in WRITE_CATEGORIES}
        read_buckets = {k: [] for k in READ_CATEGORIES}
        for file, instance_id in trajectory_files:
            resolved = is_resolved(instance_id)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            if not args.resolved and not args.unresolved and resolved:
                continue
            source_files = source_files_from_instance_id(instance_id)
            legacy_items = load_legacy_trajectory(file)
            stats, _, _ = get_recall_precision_stats_legacy(
                legacy_items, source_files, exclude_tests=args.exclude_tests,
                include_subagents=include_sa,
            )
            w_cat = categorize_write_stats(stats["write"], args.precision_threshold, args.recall_threshold)
            r_cat = categorize_read_stats(stats["read"], args.precision_threshold, args.recall_threshold)
            write_buckets[w_cat].append((instance_id, stats))
            read_buckets[r_cat].append((instance_id, stats))

        filter_label = "RESOLVED" if args.resolved else "UNRESOLVED" if args.unresolved else "UNRESOLVED"
        print("\n" + "=" * 70)
        print(f"{filter_label} INSTANCES — WRITE CATEGORIES")
        print(f"  Thresholds: precision >= {args.precision_threshold}, recall >= {args.recall_threshold}")
        print("=" * 70)
        for cat_key, cat_info in WRITE_CATEGORIES.items():
            instances = write_buckets[cat_key]
            print(f"\n--- {cat_info['label']} ({len(instances)}) ---")
            print(f"    {cat_info['explanation']}")
            for iid, st in instances:
                w = st["write"]
                line = f"    {iid}  write_recall={w['recall']:.2f}  write_precision={w['precision']:.2f}"
                if args.dir_stats:
                    for level in ("module", "package", "parent"):
                        wd = st[f"write_{level}"]
                        line += f"  w_{level[:3]}={wd['recall']:.2f}/{wd['precision']:.2f}"
                print(line)

        print("\n" + "=" * 70)
        print(f"{filter_label} INSTANCES — READ CATEGORIES")
        print(f"  Thresholds: precision >= {args.precision_threshold}, recall >= {args.recall_threshold}")
        print("=" * 70)
        for cat_key, cat_info in READ_CATEGORIES.items():
            instances = read_buckets[cat_key]
            print(f"\n--- {cat_info['label']} ({len(instances)}) ---")
            print(f"    {cat_info['explanation']}")
            for iid, st in instances:
                r = st["read"]
                line = f"    {iid}  read_recall={r['recall']:.2f}  read_precision={r['precision']:.2f}"
                if args.dir_stats:
                    for level in ("module", "package", "parent"):
                        rd = st[f"read_{level}"]
                        line += f"  r_{level[:3]}={rd['recall']:.2f}/{rd['precision']:.2f}"
                print(line)


    if args.plot:
        resolved_points = []   # (recall, precision)
        unresolved_points = [] # (recall, precision)
        for file, instance_id in trajectory_files:
            resolved = is_resolved(instance_id)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            source_files = source_files_from_instance_id(instance_id)
            legacy_items = load_legacy_trajectory(file)
            stats, _, _ = get_recall_precision_stats_legacy(
                legacy_items, source_files, exclude_tests=args.exclude_tests,
                include_subagents=include_sa,
            )
            w = stats["write"]
            if resolved:
                resolved_points.append((w["recall"], w["precision"]))
            else:
                unresolved_points.append((w["recall"], w["precision"]))

        fig, ax = plt.subplots(figsize=(8, 8))
        if resolved_points:
            ax.scatter([p[0] for p in resolved_points], [p[1] for p in resolved_points],
                       c="green", label="Resolved", alpha=0.7, edgecolors="black", s=60)
        if unresolved_points:
            ax.scatter([p[0] for p in unresolved_points], [p[1] for p in unresolved_points],
                       c="red", label="Unresolved", alpha=0.7, edgecolors="black", s=60)
        ax.axhline(y=args.precision_threshold, color="gray", linestyle="--", linewidth=1,
                   label=f"Precision threshold ({args.precision_threshold})")
        ax.axvline(x=args.recall_threshold, color="gray", linestyle="--", linewidth=1,
                   label=f"Recall threshold ({args.recall_threshold})")
        ax.set_xlabel("Write Recall", fontsize=13)
        ax.set_ylabel("Write Precision", fontsize=13)
        ax.set_title("Claude Code — Write Recall vs Precision", fontsize=15)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
