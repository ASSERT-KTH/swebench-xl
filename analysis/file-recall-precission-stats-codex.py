


import argparse
import json
import re
import os

TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/codex-gpt-5.4-analysis-final/"
INSTANCE_STATS = "/Users/pontusberglund/Documents/GitHub/swebench-xl/analysis/instance_stats_output.json"
RUN_RESULTS_JSON = "/Users/pontusberglund/Documents/full-run-trajectories/codex-gpt-5.4-analysis-final/result.json"


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

def get_reads_and_writes(steps):
    reads = set()
    writes = set()
    for step in steps:
        for tool_call in step.get("tool_calls", []):
            fn = tool_call.get("function_name", "")
            args = tool_call.get("arguments", {})
            raw_args = step.get("extra", {}).get("raw_arguments", "")

            if fn == "exec_command":
                cmd = ""
                if isinstance(args, dict):
                    cmd = args.get("cmd", "")
                if not cmd and raw_args:
                    try:
                        parsed = json.loads(raw_args)
                        cmd = parsed.get("cmd", "")
                    except (json.JSONDecodeError, TypeError):
                        pass
                if cmd:
                    paths = re.findall(r'(/app/[^\s\'\"\\|>;]+)', cmd)
                    for p in paths:
                        clean = p.rstrip(".,;:)(")
                        reads.add(clean)

            elif fn == "apply_patch":
                patch = raw_args if raw_args else str(args)
                for match in re.findall(r'\*\*\*\s+(?:Update|Create)\s+File:\s*(\S+)', patch):
                    writes.add(match)

    return list(reads), list(writes)

def get_all_trajectory_files(trajectory_dir):
    trajectory_file_and_instance_id = []
    for root, _, files in os.walk(trajectory_dir):
        for file in files:
            if file.endswith("trajectory.json"):
                instance_id = os.path.basename(os.path.dirname(root)).rsplit("__", 1)[0]
                trajectory_file_and_instance_id.append((os.path.join(root, file), instance_id))
    return trajectory_file_and_instance_id

def source_files_from_instance_id(instance_id):
    with open(INSTANCE_STATS, "r") as f:
        instance_stats = json.load(f)
    for instance in instance_stats["instances"]:
        if instance["instance_id"] == instance_id:
            return instance.get("source_files", [])
    return []

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

def get_recall_precision_stats(trajectory, source_files, exclude_tests=False):
    steps = get_steps(trajectory)
    steps_with_tool_calls = get_steps_with_tool_calls(steps)
    reads, writes = get_reads_and_writes(steps_with_tool_calls)

    read_set = set(reads)
    write_set = set(writes)

    if exclude_tests:
        read_set = {p for p in read_set if not _is_test_file(p)}
        write_set = {p for p in write_set if not _is_test_file(p)}

    source_set = set(f"/app/{s.lstrip('/')}" for s in source_files)

    return {
        "read": _precision_recall(read_set, source_set),
        "write": _precision_recall(write_set, source_set),
    }

def is_resolved(instance_id):
    with open(RUN_RESULTS_JSON, "r") as f:
        run_results = json.load(f)
    
    resolved = run_results["stats"]["evals"]["azure-codex__gpt-5.4__swebench-xl-v0.1"]["reward_stats"]["reward"]["1.0"]
    for iid in resolved:
        resolved_iid = iid.rsplit("__", 1)[0]
        if resolved_iid == instance_id:
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="File recall/precision stats for codex trajectories")
    parser.add_argument("--instance", type=str, default=None,
                        help="Instance ID to inspect (prints source files and all reads/writes)")
    parser.add_argument("--exclude-tests", action="store_true",
                        help="Exclude *Tests.java files from reads/writes")
    parser.add_argument("--resolved", action="store_true",
                        help="Only show resolved instances")
    parser.add_argument("--unresolved", action="store_true",
                        help="Only show unresolved instances")
    args = parser.parse_args()

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
            trajectory = load_trajectory(file)
            steps = get_steps(trajectory)
            steps_with_tool_calls = get_steps_with_tool_calls(steps)
            reads, writes = get_reads_and_writes(steps_with_tool_calls)
            print(f"\nTrajectory: {file}")
            print(f"Reads ({len(reads)}):")
            for r in sorted(reads):
                print(f"  R: {r}")
            print(f"Writes ({len(writes)}):")
            for w in sorted(writes):
                print(f"  W: {w}")
            stats = get_recall_precision_stats(trajectory, source_files, exclude_tests=args.exclude_tests)
            for kind in ("read", "write"):
                s = stats[kind]
                print(f"\n{kind.upper()} stats:")
                print(f"  Recall:  {s['recall']:.2f}")
                print(f"  Precision: {s['precision']:.2f}")
                print(f"  True Positives:  {s['true_positives']}")
                print(f"  False Positives: {s['false_positives']}")
                print(f"  False Negatives: {s['false_negatives']}")
    else:
        for file, instance_id in trajectory_files:
            resolved = is_resolved(instance_id)
            if args.resolved and not resolved:
                continue
            if args.unresolved and resolved:
                continue
            source_files = source_files_from_instance_id(instance_id)
            stats = get_recall_precision_stats(load_trajectory(file), source_files, exclude_tests=args.exclude_tests)
            r, w = stats["read"], stats["write"]
            status = "RESOLVED" if resolved else "UNRESOLVED"
            print(f"{instance_id}  {status}  read_recall={r['recall']:.2f}  read_precision={r['precision']:.2f}  write_recall={w['recall']:.2f}  write_precision={w['precision']:.2f}")


if __name__ == "__main__":
    main()
    