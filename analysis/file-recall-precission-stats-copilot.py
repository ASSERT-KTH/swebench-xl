import argparse
import json
import re
import os
import zipfile

#DEFAULT_TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/copilot-opus-xl/"
DEFAULT_TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/copilot-gpt5.4-xl"
INSTANCE_STATS = "/Users/pontusberglund/Documents/GitHub/swebench-xl/analysis/instance_stats_output.json"

# Zip filename patterns
ZIP_SUFFIX = "-output.zip"

_EXCLUDE_RE = re.compile(
    r"/docs/|\.asciidoc$|\.md$|/locales/|\.github/|\.yml$|\.yaml$|"
    r"\.gradle$|Rakefile|\.rake$|\.gemspec$|\.options$|"
    r"\.sh$|\.bat$|\.json$|/config/|/docker/|"
    r"/test/|/tests/|/spec/|Test\.java$|_test\.go$|_spec\.rb$|"
    r"CHANGELOG|CONTRIBUTING|LICENSE|README",
    re.IGNORECASE,
)


def get_steps(trajectory):
    return trajectory["steps"]

def load_trajectory(file_path):
    with open(file_path, "r") as f:
        trajectory = json.load(f)
    return trajectory

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
    abs_paths = re.findall(r'(/app/[^\s\'\"\\|>;]+)', cmd)
    for p in abs_paths:
        clean = p.rstrip(".,;:)(")
        paths.append(clean)
    rel_paths = re.findall(r'(?:^|\s)([a-zA-Z0-9_.][^\s\'\"\\|>;]*\.[a-zA-Z0-9]+)', cmd)
    for p in rel_paths:
        clean = p.rstrip(".,;:)(")
        if '/' in clean and not clean.startswith('/'):
            paths.append(f"/app/{clean}")
    return [p for p in paths if _is_valid_source_path(p)]

def get_reads_and_writes(steps):
    """Extract read and written file paths from Copilot CLI trajectory steps.

    Tool mapping:
      view        -> read (path)
      bash        -> read or write depending on command content
      grep / rg   -> read (path, if it points to a file)
      glob        -> skip (just lists file names)
      edit        -> write (path)
      create      -> write (path)
      apply_patch -> write (paths extracted from patch text)
      report_intent / read_bash / stop_bash -> skip
    """
    reads = {}   # path -> [source descriptions]
    writes = set()

    for step in steps:
        for tool_call in step.get("tool_calls", []):
            fn = tool_call.get("function_name", "")
            args = tool_call.get("arguments", {})
            if not isinstance(args, dict):
                continue

            if fn == "view":
                file_path = args.get("path", "")
                if file_path and _is_valid_source_path(file_path):
                    reads.setdefault(file_path, []).append(f"view {file_path}")

            elif fn in ("grep", "rg"):
                path = args.get("path", "")
                if path and _is_valid_source_path(path):
                    reads.setdefault(path, []).append(
                        f"{fn} pattern={args.get('pattern', '')} path={path}"
                    )

            elif fn == "bash":
                cmd = args.get("command", "")
                if not cmd:
                    continue
                extracted = _extract_paths_from_command(cmd)
                if not _is_non_read_command(cmd):
                    for p in extracted:
                        reads.setdefault(p, []).append(f"bash: {cmd}")

            elif fn == "edit":
                file_path = args.get("path", "")
                if file_path and _is_valid_source_path(file_path):
                    writes.add(file_path)

            elif fn == "create":
                file_path = args.get("path", "")
                if file_path and file_path.startswith("/app/") and _is_valid_source_path(file_path):
                    writes.add(file_path)

            elif fn == "apply_patch":
                patch = args.get("raw", "") or args.get("patch", "") or args.get("diff", "")
                for match in re.findall(r'\*\*\*\s+(?:Update|Create)\s+File:\s*(\S+)', patch):
                    if _is_valid_source_path(match):
                        writes.add(match)

    return reads, list(writes)

def get_reads_and_writes_legacy(trajectory):
    """Extract read/written file paths from legacy trajectory (list of tool call items)."""
    reads = {}   # path -> [cmds]
    writes = set()

    for item in trajectory:
        tool = item.get("tool", "")
        action_str = item.get("action", "")

        # Parse action JSON
        try:
            args = json.loads(action_str) if isinstance(action_str, str) else action_str
        except (json.JSONDecodeError, TypeError):
            args = {}
        if not isinstance(args, dict):
            args = {}

        if tool == "view":
            file_path = args.get("path", "")
            if file_path and _is_valid_source_path(file_path):
                reads.setdefault(file_path, []).append(f"view {file_path}")

        elif tool in ("grep", "rg"):
            path = args.get("path", "")
            if path and _is_valid_source_path(path):
                reads.setdefault(path, []).append(
                    f"{tool} pattern={args.get('pattern', '')} path={path}"
                )

        elif tool == "bash":
            cmd = args.get("command", "")
            if not cmd:
                # Legacy format sometimes has the raw command as action string
                cmd = action_str if isinstance(action_str, str) else ""
            if cmd and not _is_non_read_command(cmd):
                extracted = _extract_paths_from_command(cmd)
                for p in extracted:
                    reads.setdefault(p, []).append(f"bash: {cmd}")

        elif tool == "edit":
            file_path = args.get("path", "")
            if file_path and _is_valid_source_path(file_path):
                writes.add(file_path)

        elif tool == "create":
            file_path = args.get("path", "")
            if file_path and file_path.startswith("/app/") and _is_valid_source_path(file_path):
                writes.add(file_path)

        elif tool == "apply_patch":
            patch = args.get("raw", "") or args.get("patch", "") or args.get("diff", "")
            if not patch:
                patch = action_str if isinstance(action_str, str) else ""
            for match in re.findall(r'\*\*\*\s+(?:Update|Create)\s+File:\s*(\S+)', patch):
                if _is_valid_source_path(match):
                    writes.add(match)

    return reads, list(writes)


def _instance_id_from_zip(filename):
    """Extract instance_id from zip filename.

    swebench-xl-v1.eval.x86_64.elastic__elasticsearch-135899-output.zip
    -> elastic__elasticsearch-135899
    """
    basename = os.path.basename(filename)
    if not basename.endswith(ZIP_SUFFIX):
        return None
    without_suffix = basename[:-len(ZIP_SUFFIX)]
    idx = without_suffix.find("x86_64.")
    if idx != -1:
        return without_suffix[idx + len("x86_64."):]
    return None


def load_trajectory_from_zip(zip_path):
    """Load trajectory.json from inside a zip file."""
    with zipfile.ZipFile(zip_path, "r") as z:
        return json.loads(z.read("output/trajectories/trajectory.json"))


def is_resolved_from_zip(zip_path):
    """Check resolution status from eval.json inside the zip."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            eval_data = json.loads(z.read("output/eval.json"))
        for iid, info in eval_data.items():
            if info.get("resolved", False):
                return True
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        pass
    return False


def get_all_trajectory_files(trajectory_dir):
    """Return list of (path, instance_id) tuples for all zip files."""
    trajectory_file_and_instance_id = []
    for filename in sorted(os.listdir(trajectory_dir)):
        if not filename.endswith(ZIP_SUFFIX):
            continue
        instance_id = _instance_id_from_zip(filename)
        if instance_id is None:
            continue
        zip_path = os.path.join(trajectory_dir, filename)
        trajectory_file_and_instance_id.append((zip_path, instance_id))
    return trajectory_file_and_instance_id

def source_files_from_instance_id(instance_id):
    with open(INSTANCE_STATS, "r") as f:
        instance_stats = json.load(f)
    for instance in instance_stats["instances"]:
        if instance["instance_id"] == instance_id:
            files = instance.get("source_files", [])
            return [f for f in files if not _EXCLUDE_RE.search(f)]
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
    """Map a set of file paths to a set of directories at the given semantic level."""
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

def get_recall_precision_stats(trajectory, source_files, exclude_tests=False, use_legacy=False):
    if use_legacy:
        reads, writes = get_reads_and_writes_legacy(trajectory)
    else:
        steps = get_steps(trajectory)
        steps_with_tool_calls = get_steps_with_tool_calls(steps)
        reads, writes = get_reads_and_writes(steps_with_tool_calls)

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
    }

    for level in ("module", "package", "parent"):
        read_dirs = _map_to_dir_sets(read_set, level)
        write_dirs = _map_to_dir_sets(write_set, level)
        source_dirs = _map_to_dir_sets(source_set, level)
        result[f"read_{level}"] = _precision_recall(read_dirs, source_dirs)
        result[f"write_{level}"] = _precision_recall(write_dirs, source_dirs)

    return result

def main():
    parser = argparse.ArgumentParser(description="File recall/precision stats for Copilot CLI trajectories")
    parser.add_argument("--instance", type=str, default=None,
                        help="Instance ID to inspect (prints source files and all reads/writes)")
    parser.add_argument("--exclude-tests", action="store_true",
                        help="Exclude *Tests.java files from reads/writes")
    parser.add_argument("--resolved", action="store_true",
                        help="Only show resolved instances")
    parser.add_argument("--unresolved", action="store_true",
                        help="Only show unresolved instances")
    parser.add_argument("--categorize", action="store_true",
                        help="Group unresolved instances by write precision/recall category")
    parser.add_argument("--recall-threshold", type=float, default=DEFAULT_RECALL_THRESHOLD,
                        help=f"Recall threshold for high/low categorization (default: {DEFAULT_RECALL_THRESHOLD})")
    parser.add_argument("--precision-threshold", type=float, default=DEFAULT_PRECISION_THRESHOLD,
                        help=f"Precision threshold for high/low categorization (default: {DEFAULT_PRECISION_THRESHOLD})")
    parser.add_argument("--show-cmds", action="store_true",
                        help="Show the commands used to read each file (only with --instance)")
    parser.add_argument("--dir-stats", action="store_true",
                        help="Show directory-level (module/package/parent) precision/recall")
    parser.add_argument("--trajectory-dir", type=str, default=DEFAULT_TRAJECTORY_DIR,
                        help=f"Directory containing trajectory zips (default: {DEFAULT_TRAJECTORY_DIR})")
    args = parser.parse_args()

    trajectory_dir = args.trajectory_dir
    trajectory_files = get_all_trajectory_files(trajectory_dir)

    if args.instance:
        matched = [(f, iid) for f, iid in trajectory_files if iid == args.instance]
        if not matched:
            print(f"No trajectory found for instance: {args.instance}")
            return
        file_path, _ = matched[0]
        resolved = is_resolved_from_zip(file_path)
        source_files = source_files_from_instance_id(args.instance)
        print(f"Instance: {args.instance}")
        print(f"Resolved: {resolved}")
        print(f"\nSource files ({len(source_files)}):")
        for sf in sorted(source_files):
            print(f"  {sf}")
        for file, _ in matched:
            trajectory = load_trajectory_from_zip(file)
            steps = get_steps(trajectory)
            steps_with_tool_calls = get_steps_with_tool_calls(steps)
            reads, writes = get_reads_and_writes(steps_with_tool_calls)
            print(f"\nTrajectory: {file}")
            print(f"Reads ({len(reads)}):")
            for r in sorted(reads):
                print(f"  R: {r}")
                if args.show_cmds:
                    for cmd in reads[r]:
                        print(f"     cmd: {cmd}")
            print(f"Writes ({len(writes)}):")
            for w in sorted(writes):
                print(f"  W: {w}")
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
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
        for file, instance_id in trajectory_files:
            resolved = is_resolved_from_zip(file)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            source_files = source_files_from_instance_id(instance_id)
            trajectory = load_trajectory_from_zip(file)
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
            r, w = stats["read"], stats["write"]
            all_read_recalls.append(r["recall"])
            all_read_precisions.append(r["precision"])
            all_write_recalls.append(w["recall"])
            all_write_precisions.append(w["precision"])
            status = "RESOLVED" if resolved else "UNRESOLVED"
            line = f"{instance_id}  {status}  read_recall={r['recall']:.2f}  read_precision={r['precision']:.2f}  write_recall={w['recall']:.2f}  write_precision={w['precision']:.2f}"
            if args.dir_stats:
                for level in ("module", "package", "parent"):
                    rd = stats[f"read_{level}"]
                    wd = stats[f"write_{level}"]
                    line += f"  r_{level[:3]}={rd['recall']:.2f}  w_{level[:3]}={wd['recall']:.2f}"
            print(line)

        n = len(all_read_recalls)
        if n > 0:
            print(f"\n{'=' * 50}")
            print(f"AVERAGES ({n} instances)")
            print(f"  Avg Read Recall:     {sum(all_read_recalls) / n:.2f}")
            print(f"  Avg Read Precision:  {sum(all_read_precisions) / n:.2f}")
            print(f"  Avg Write Recall:    {sum(all_write_recalls) / n:.2f}")
            print(f"  Avg Write Precision: {sum(all_write_precisions) / n:.2f}")
            print(f"{'=' * 50}")

    if args.categorize:
        write_buckets = {k: [] for k in WRITE_CATEGORIES}
        read_buckets = {k: [] for k in READ_CATEGORIES}
        for file, instance_id in trajectory_files:
            resolved = is_resolved_from_zip(file)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            if not args.resolved and not args.unresolved and resolved:
                continue
            source_files = source_files_from_instance_id(instance_id)
            trajectory = load_trajectory_from_zip(file)
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
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


if __name__ == "__main__":
    main()
