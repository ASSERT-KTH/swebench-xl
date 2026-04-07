import argparse
import json
import re
import os
import zipfile
import matplotlib.pyplot as plt

TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/codex-mswe-java/"
#TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/multi-java-codex-full-hints"

_EXCLUDE_RE = re.compile(
    r"/docs/|\.asciidoc$|\.md$|/locales/|\.github/|\.yml$|\.yaml$|"
    r"\.gradle$|Rakefile|\.rake$|\.gemspec$|\.options$|"
    r"\.sh$|\.bat$|\.json$|/config/|/docker/|"
    r"/test/|/tests/|/spec/|Test\.java$|_test\.go$|_spec\.rb$|"
    r"CHANGELOG|CONTRIBUTING|LICENSE|README",
    re.IGNORECASE,
)

# Zip filename pattern: multiswebench.eval.x86_64.{org}__{repo}_{pr_num}-output.zip
ZIP_PREFIX = "multiswebench.eval.x86_64."
ZIP_SUFFIX = "-output.zip"


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


def _strip_home_prefix(path):
    """Strip /home/{reponame}/ prefix to get a relative path."""
    m = re.match(r'^/home/[^/]+/(.+)$', path)
    if m:
        return m.group(1)
    return path


def get_reads_and_writes(trajectory):
    """Extract read and written file paths from Multi-SWE-bench Codex trajectory.

    Trajectory is a list of dicts with keys: tool, action, observation, ...
    Tools: bash, file_edit, Finish
    - bash: action is the command string; extract paths from it
    - file_edit: action is 'file_change: [{"path":"...","kind":"update|add"}]'
    """
    reads = {}   # relative_path -> [descriptions]
    writes = set()

    for item in trajectory:
        tool = item.get("tool", "")
        action = item.get("action", "")

        if tool == "bash":
            # Extract the actual command from /bin/bash -lc '...' wrapper
            cmd = action
            m = re.match(r"/bin/bash\s+-lc\s+'(.+)'$", action, re.DOTALL)
            if m:
                cmd = m.group(1)
            elif action.startswith("/bin/bash -lc \""):
                m2 = re.match(r'/bin/bash\s+-lc\s+"(.+)"$', action, re.DOTALL)
                if m2:
                    cmd = m2.group(1)

            if cmd and not _is_non_read_command(cmd):
                # Match absolute /home/XXX/ paths
                paths = re.findall(r'(/home/[^/]+/[^\s\'\"\\|>;]+)', cmd)
                # Match relative paths (e.g. src/..., x-pack/...)
                rel_paths = re.findall(r'(?:^|\s)([a-zA-Z0-9_.][^\s\'\"\\|>;]*\.[a-zA-Z0-9]+)', cmd)
                for p in rel_paths:
                    clean = p.rstrip(".,;:)(")
                    if '/' in clean and not clean.startswith('/'):
                        paths.append(clean)  # already relative
                all_rel = []
                for p in paths:
                    clean = p.rstrip(".,;:)(")
                    rel = _strip_home_prefix(clean)
                    if _is_valid_source_path(rel):
                        all_rel.append(rel)
                for rel in all_rel:
                    reads.setdefault(rel, []).append(cmd)

        elif tool == "file_edit":
            # Parse: file_change: [{"path":"/home/xxx/...","kind":"update"}]
            m = re.search(r'file_change:\s*(\[.+\])', action)
            if m:
                try:
                    changes = json.loads(m.group(1))
                    for change in changes:
                        path = change.get("path", "")
                        rel = _strip_home_prefix(path)
                        if _is_valid_source_path(rel):
                            writes.add(rel)
                except (json.JSONDecodeError, TypeError):
                    pass

    return reads, list(writes)


def _instance_id_from_zip(filename):
    """Extract instance_id from zip filename.

    multiswebench.eval.x86_64.alibaba__fastjson2_1245-output.zip
    -> alibaba__fastjson2_1245
    """
    basename = os.path.basename(filename)
    if basename.startswith(ZIP_PREFIX) and basename.endswith(ZIP_SUFFIX):
        return basename[len(ZIP_PREFIX):-len(ZIP_SUFFIX)]
    return None


def _zip_instance_id_to_jsonl_id(zip_id):
    """Convert zip instance_id to JSONL instance_id format.

    alibaba__fastjson2_1245 -> alibaba__fastjson2-1245
    (last underscore before the PR number becomes a hyphen)
    """
    # Split on last underscore: alibaba__fastjson2 + 1245
    parts = zip_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return f"{parts[0]}-{parts[1]}"
    return zip_id


def get_all_trajectory_files(trajectory_dir):
    """Find all trajectory zips and return (zip_path, zip_instance_id, jsonl_instance_id) triples."""
    results = []
    for filename in sorted(os.listdir(trajectory_dir)):
        if not filename.endswith(ZIP_SUFFIX):
            continue
        zip_id = _instance_id_from_zip(filename)
        if zip_id is None:
            continue
        zip_path = os.path.join(trajectory_dir, filename)
        jsonl_id = _zip_instance_id_to_jsonl_id(zip_id)
        results.append((zip_path, zip_id, jsonl_id))
    return results


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


def _extract_files_from_patch(patch_text):
    """Extract file paths from unified diff text (diff --git a/path b/path lines)."""
    files = []
    for match in re.finditer(r'^diff --git a/(.+?) b/(.+?)$', patch_text, re.MULTILINE):
        # Use the b/ side (the "after" path)
        files.append(match.group(2))
    return files


def _load_mswe_bench_index(mswe_bench_dir):
    """Load all Multi-SWE-bench JSONL files and return a dict: instance_id -> fix_patch."""
    index = {}
    for filename in os.listdir(mswe_bench_dir):
        if not filename.endswith("_dataset.jsonl") and not filename.endswith(".jsonl"):
            continue
        filepath = os.path.join(mswe_bench_dir, filename)
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                iid = entry.get("instance_id", "")
                patch = entry.get("fix_patch", "")
                if iid and patch:
                    index[iid] = patch
    return index


def _read_gold_patch(gold_patches_dir, instance_id, mswe_bench_index=None):
    """Read the gold patch for an instance.

    If mswe_bench_index is provided, look up the fix_patch from the
    Multi-SWE-bench JSONL index. Otherwise fall back to the directory-based
    lookup:
      1. {gold_patches_dir}/{instance_id}/solution/solve.sh  (embedded diff)
      2. {gold_patches_dir}/{instance_id}/gold.patch
      3. {gold_patches_dir}/{instance_id}/patch.diff
      4. {gold_patches_dir}/{instance_id}.patch
    """
    if mswe_bench_index is not None:
        return mswe_bench_index.get(instance_id)

    # Try solve.sh first (patch embedded between __SOLUTION__ markers)
    solve_sh = os.path.join(gold_patches_dir, instance_id, "solution", "solve.sh")
    if os.path.isfile(solve_sh):
        with open(solve_sh, "r") as f:
            content = f.read()
        # Extract the diff between __SOLUTION__ markers
        m = re.search(r"<< *'__SOLUTION__'\n(.*?)__SOLUTION__", content, re.DOTALL)
        if m:
            return m.group(1)
        # Fallback: the whole file might contain diff lines
        return content

    # Try standalone patch files
    for filename in ("gold.patch", "patch.diff", "solution.patch", "solution.diff"):
        patch_file = os.path.join(gold_patches_dir, instance_id, filename)
        if os.path.isfile(patch_file):
            with open(patch_file, "r") as f:
                return f.read()

    # Try {instance_id}.patch at the top level
    patch_file = os.path.join(gold_patches_dir, f"{instance_id}.patch")
    if os.path.isfile(patch_file):
        with open(patch_file, "r") as f:
            return f.read()

    return None


def source_files_from_gold_patch(gold_patches_dir, instance_id, mswe_bench_index=None):
    """Get source files for an instance by parsing its gold patch."""
    patch_text = _read_gold_patch(gold_patches_dir, instance_id, mswe_bench_index)
    if patch_text is None:
        return []
    files = _extract_files_from_patch(patch_text)
    return [f for f in files if not _EXCLUDE_RE.search(f)]


def _extract_semantic_dirs(path):
    """Extract module, package, and parent directory from a path.

    Given Elasticsearch's Maven layout: module/src/{main|test}/java/org/.../File.java
    - module:  everything before /src/
    - package: the Java package dir (between /java/ and the filename)
    - parent:  immediate parent directory
    """
    parent = os.path.dirname(path)

    # Module: prefix before /src/
    src_idx = path.find("/src/")
    if src_idx != -1:
        module = path[:src_idx]
    else:
        # Fallback: first 3 components (e.g. /app/server -> /app/server)
        parts = path.split("/")
        module = "/".join(parts[:min(4, len(parts))])

    # Package: dirname of the portion after /java/
    java_idx = path.find("/java/")
    if java_idx != -1:
        after_java = path[java_idx + len("/java/"):]
        package = os.path.dirname(after_java)
    else:
        # Fallback: use parent relative to module
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

def get_recall_precision_stats(trajectory, source_files, exclude_tests=False):
    reads, writes = get_reads_and_writes(trajectory)

    read_set = set(reads)
    write_set = set(writes)

    if exclude_tests:
        read_set = {p for p in read_set if not _is_test_file(p)}
        write_set = {p for p in write_set if not _is_test_file(p)}

    # source_files from gold patch are already relative paths
    source_set = set(s.lstrip('/') for s in source_files)
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
    parser = argparse.ArgumentParser(description="File recall/precision stats for Codex trajectories (Multi-SWE-bench) using gold patches")
    parser.add_argument("--gold-patches-dir", type=str, default=None,
                        help="Directory containing gold patches. Expected structure: "
                             "{dir}/{instance_id}/solution/solve.sh or {dir}/{instance_id}.patch")
    parser.add_argument("--jsonl-dir", type=str, default=None,
                        help="Directory containing JSONL files with instance_id and "
                             "fix_patch fields (e.g. Multi-SWE-bench java/ from HuggingFace).")
    parser.add_argument("--trajectory-dir", type=str, default=TRAJECTORY_DIR,
                        help=f"Directory containing trajectory zip files (default: {TRAJECTORY_DIR})")
    parser.add_argument("--instance", type=str, default=None,
                        help="Instance ID to inspect (zip-style, e.g. alibaba__fastjson2_1245)")
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
    args = parser.parse_args()

    if not args.gold_patches_dir and not args.jsonl_dir:
        parser.error("Either --gold-patches-dir or --jsonl-dir is required")

    trajectory_dir = args.trajectory_dir
    gold_patches_dir = args.gold_patches_dir
    trajectory_files = get_all_trajectory_files(trajectory_dir)

    mswe_bench_index = None
    if args.jsonl_dir:
        print(f"Loading JSONL index from {args.jsonl_dir} ...")
        mswe_bench_index = _load_mswe_bench_index(args.jsonl_dir)
        print(f"Loaded {len(mswe_bench_index)} instances from JSONL files.")

    if args.instance:
        matched = [(zp, zid, jid) for zp, zid, jid in trajectory_files if zid == args.instance]
        if not matched:
            print(f"No trajectory found for instance: {args.instance}")
            return
        zip_path, zip_id, jsonl_id = matched[0]
        resolved = is_resolved_from_zip(zip_path)
        source_files = source_files_from_gold_patch(gold_patches_dir, jsonl_id, mswe_bench_index)
        if not source_files:
            print(f"No gold patch found for instance: {args.instance} (jsonl_id: {jsonl_id})")
            return
        print(f"Instance: {zip_id} (jsonl_id: {jsonl_id})")
        print(f"Resolved: {resolved}")
        print(f"\nSource files from gold patch ({len(source_files)}):")
        for sf in sorted(source_files):
            print(f"  {sf}")
        trajectory = load_trajectory_from_zip(zip_path)
        reads, writes = get_reads_and_writes(trajectory)
        print(f"\nTrajectory: {zip_path}")
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
        skipped = 0
        for zip_path, zip_id, jsonl_id in trajectory_files:
            resolved = is_resolved_from_zip(zip_path)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            source_files = source_files_from_gold_patch(gold_patches_dir, jsonl_id, mswe_bench_index)
            if not source_files:
                skipped += 1
                continue
            trajectory = load_trajectory_from_zip(zip_path)
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
            r, w = stats["read"], stats["write"]
            all_read_recalls.append(r["recall"])
            all_read_precisions.append(r["precision"])
            all_write_recalls.append(w["recall"])
            all_write_precisions.append(w["precision"])
            status = "RESOLVED" if resolved else "UNRESOLVED"
            line = f"{zip_id}  {status}  read_recall={r['recall']:.2f}  read_precision={r['precision']:.2f}  write_recall={w['recall']:.2f}  write_precision={w['precision']:.2f}"
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
            if skipped:
                print(f"  Skipped (no gold patch): {skipped}")
            print(f"{'=' * 50}")

    if args.categorize:
        write_buckets = {k: [] for k in WRITE_CATEGORIES}
        read_buckets = {k: [] for k in READ_CATEGORIES}
        for zip_path, zip_id, jsonl_id in trajectory_files:
            resolved = is_resolved_from_zip(zip_path)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            if not args.resolved and not args.unresolved and resolved:
                continue
            source_files = source_files_from_gold_patch(gold_patches_dir, jsonl_id, mswe_bench_index)
            if not source_files:
                continue
            trajectory = load_trajectory_from_zip(zip_path)
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
            w_cat = categorize_write_stats(stats["write"], args.precision_threshold, args.recall_threshold)
            r_cat = categorize_read_stats(stats["read"], args.precision_threshold, args.recall_threshold)
            write_buckets[w_cat].append((zip_id, stats))
            read_buckets[r_cat].append((zip_id, stats))

        filter_label = "RESOLVED" if args.resolved else "UNRESOLVED" if args.unresolved else "UNRESOLVED"
        print("\n" + "=" * 70)
        print(f"{filter_label} INSTANCES \u2014 WRITE CATEGORIES")
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
        print(f"{filter_label} INSTANCES \u2014 READ CATEGORIES")
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
        for zip_path, zip_id, jsonl_id in trajectory_files:
            resolved = is_resolved_from_zip(zip_path)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            source_files = source_files_from_gold_patch(gold_patches_dir, jsonl_id, mswe_bench_index)
            if not source_files:
                continue
            trajectory = load_trajectory_from_zip(zip_path)
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
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
        ax.set_title("Codex (Multi-SWE-bench) \u2014 Write Recall vs Precision (Gold Patches)", fontsize=15)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
