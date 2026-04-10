#!/usr/bin/env python3
"""
Unified file recall/precision stats for multiple agent trajectory runs.

Auto-detects the agent type (Claude Code, Codex, Copilot) from zip contents
and computes recall/precision of file reads and writes against gold-patch
source files.

Usage:
    python file-recall-precision-general.py                        # uses RUNS list
    python file-recall-precision-general.py /path/to/run1/ ...     # override
    python file-recall-precision-general.py /path/to/run1/ --per-instance
"""

import argparse
import json
import os
import re
import sys
import zipfile

INSTANCE_STATS = os.path.join(os.path.dirname(__file__), "instance_stats_output.json")
ZIP_SUFFIX = "-output.zip"

# Gold patch files to exclude from source set (matched by basename)
EXCLUDED_GOLD_FILES = [
    "EsqlCapabilities.java",
]

# ---------------------------------------------------------------------------
# Hardcoded run list: (path, optional_label)
# Set label to None to auto-detect from path + agent.
# ---------------------------------------------------------------------------
RUNS = [
    ("/Users/pontusberglund/Documents/full-run-trajectories/copilot-gpt5.4-xl", None),
    ("/Users/pontusberglund/Documents/full-run-trajectories/copilot-opus-xl", None),
    ("/Users/pontusberglund/Documents/full-run-trajectories/codex-xl-msbench-full-run", None),
    ("/Users/pontusberglund/Documents/full-run-trajectories/claude-opus-xl", None),
    ("/Users/pontusberglund/Documents/full-run-trajectories/codex-gpt-5.4-xhigh-xl", None),
    ("/Users/pontusberglund/Documents/full-run-trajectories/codex-gpt5.4-mini-xl", None),
]


# ---------------------------------------------------------------------------
# Path helpers (shared across agents)
# ---------------------------------------------------------------------------

def _is_valid_source_path(path):
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
    paths = []
    abs_paths = re.findall(r"(/app/[^\s'\"\\|>;]+)", cmd)
    for p in abs_paths:
        paths.append(p.rstrip(".,;:)("))
    rel_paths = re.findall(
        r"(?:^|\s)([a-zA-Z0-9_.][^\s'\"\\|>;]*\.[a-zA-Z0-9]+)", cmd
    )
    for p in rel_paths:
        clean = p.rstrip(".,;:)(")
        if "/" in clean and not clean.startswith("/"):
            paths.append(f"/app/{clean}")
    return [p for p in paths if _is_valid_source_path(p)]


def _is_non_read_command(cmd):
    stripped = cmd.lstrip()
    non_read_prefixes = (
        "git add ", "git checkout ", "git restore ", "git reset ",
        "git stash", "git commit", "git push", "git pull",
        "git merge", "git rebase", "git cherry-pick",
        "rm ", "mv ", "cp ", "mkdir ", "touch ", "chmod ", "chown ",
    )
    return stripped.startswith(non_read_prefixes)


def _is_write_command(cmd):
    stripped = cmd.lstrip()
    write_prefixes = ("sed ", "sed -i", "echo ", "printf ", "tee ")
    if ">>" in cmd or re.search(r"[^>]>[^>]", cmd):
        return True
    return stripped.startswith(write_prefixes)


# ---------------------------------------------------------------------------
# Precision / recall
# ---------------------------------------------------------------------------

def _precision_recall(predicted_set, gold_set):
    tp = len(predicted_set & gold_set)
    fp = len(predicted_set - gold_set)
    fn = len(gold_set - predicted_set)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    return {"recall": recall, "precision": precision,
            "true_positives": tp, "false_positives": fp, "false_negatives": fn}


# ---------------------------------------------------------------------------
# Instance stats
# ---------------------------------------------------------------------------

_INSTANCE_STATS_CACHE = None


def _load_instance_stats():
    global _INSTANCE_STATS_CACHE
    if _INSTANCE_STATS_CACHE is None:
        with open(INSTANCE_STATS, "r") as f:
            _INSTANCE_STATS_CACHE = json.load(f)
    return _INSTANCE_STATS_CACHE


def source_files_from_instance_id(instance_id):
    stats = _load_instance_stats()
    for inst in stats["instances"]:
        if inst["instance_id"] == instance_id:
            return inst.get("source_files", [])
    return []


# ---------------------------------------------------------------------------
# Zip helpers
# ---------------------------------------------------------------------------

def _instance_id_from_zip(filename):
    basename = os.path.basename(filename)
    if not basename.endswith(ZIP_SUFFIX):
        return None
    without_suffix = basename[: -len(ZIP_SUFFIX)]
    idx = without_suffix.find("x86_64.")
    if idx != -1:
        return without_suffix[idx + len("x86_64."):]
    return None


def get_all_trajectory_zips(trajectory_dir):
    results = []
    for filename in sorted(os.listdir(trajectory_dir)):
        if not filename.endswith(ZIP_SUFFIX):
            continue
        instance_id = _instance_id_from_zip(filename)
        if instance_id is None:
            continue
        results.append((os.path.join(trajectory_dir, filename), instance_id))
    return results


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


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------

def detect_agent(zip_path):
    """Detect agent type from zip contents.

    Returns: "claude-code", "codex", or "copilot"

    All three agents may ship both trajectory.json and trajectory_legacy.json,
    so we distinguish by inspecting tool names.
    """
    with zipfile.ZipFile(zip_path, "r") as z:
        data = json.loads(z.read("output/trajectories/trajectory.json"))

        # Codex: trajectory.json is a flat list of items
        if isinstance(data, list):
            return "codex"

        # Both Copilot and Claude Code have dict-with-steps trajectory.json.
        # Distinguish by tool/function names in the steps.
        if isinstance(data, dict) and "steps" in data:
            fn_names = set()
            for step in data.get("steps", [])[:20]:
                for tc in step.get("tool_calls", []):
                    fn_names.add(tc.get("function_name", ""))
            # Copilot uses view/edit/create/rg; Claude Code uses Read/Edit/Grep/Bash
            copilot_tools = {"view", "edit", "create", "rg", "grep", "apply_patch",
                             "report_intent", "read_bash", "stop_bash"}
            claude_tools = {"Read", "Edit", "Write", "Grep", "Bash", "Glob", "Agent"}
            copilot_hits = len(fn_names & copilot_tools)
            claude_hits = len(fn_names & claude_tools)
            if copilot_hits > claude_hits:
                return "copilot"
            return "claude-code"

        # Fallback: check legacy file
        return "claude-code"


def load_trajectory(zip_path, agent):
    """Load trajectory data from zip for the given agent type."""
    with zipfile.ZipFile(zip_path, "r") as z:
        if agent == "claude-code":
            return json.loads(z.read("output/trajectories/trajectory_legacy.json"))
        return json.loads(z.read("output/trajectories/trajectory.json"))


# ---------------------------------------------------------------------------
# Claude Code extraction (legacy flat list with sub-agent support)
# ---------------------------------------------------------------------------

def _parse_action(action_str):
    if not action_str:
        return {}
    try:
        return json.loads(action_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_claude_code(legacy_items):
    reads = set()
    writes = set()

    for item in legacy_items:
        fn = item.get("tool", "")
        args = _parse_action(item.get("action", ""))

        if fn == "Read":
            file_path = args.get("file_path", "")
            if file_path and _is_valid_source_path(file_path):
                reads.add(file_path)

        elif fn == "Grep":
            path = args.get("path", "")
            if path and _is_valid_source_path(path):
                reads.add(path)

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
                    reads.add(p)

        elif fn == "Edit":
            file_path = args.get("file_path", "")
            if file_path and _is_valid_source_path(file_path):
                writes.add(file_path)

        elif fn == "Write":
            file_path = args.get("file_path", "")
            if file_path and file_path.startswith("/app/") and _is_valid_source_path(file_path):
                writes.add(file_path)

    return reads, writes


# ---------------------------------------------------------------------------
# Codex extraction (flat list: bash + file_edit)
# ---------------------------------------------------------------------------

def _extract_codex(trajectory):
    reads = set()
    writes = set()

    for item in trajectory:
        tool = item.get("tool", "")
        action = item.get("action", "")

        if tool == "bash":
            cmd = action
            m = re.match(r"/bin/bash\s+-lc\s+'(.+)'$", action, re.DOTALL)
            if m:
                cmd = m.group(1)
            elif action.startswith('/bin/bash -lc "'):
                m2 = re.match(r'/bin/bash\s+-lc\s+"(.+)"$', action, re.DOTALL)
                if m2:
                    cmd = m2.group(1)

            if cmd and not _is_non_read_command(cmd):
                for p in _extract_paths_from_command(cmd):
                    reads.add(p)

        elif tool == "file_edit":
            m = re.search(r'file_change:\s*(\[.+\])', action)
            if m:
                try:
                    changes = json.loads(m.group(1))
                    for change in changes:
                        path = change.get("path", "")
                        if not path.startswith("/app/"):
                            path = f"/app/{path.lstrip('/')}"
                        if _is_valid_source_path(path):
                            writes.add(path)
                except (json.JSONDecodeError, TypeError):
                    pass

    return reads, writes


# ---------------------------------------------------------------------------
# Copilot extraction (dict with steps -> tool_calls)
# ---------------------------------------------------------------------------

def _extract_copilot(trajectory):
    reads = set()
    writes = set()

    for step in trajectory.get("steps", []):
        for tool_call in step.get("tool_calls", []):
            fn = tool_call.get("function_name", "")
            args = tool_call.get("arguments", {})
            if not isinstance(args, dict):
                continue

            if fn == "view":
                file_path = args.get("path", "")
                if file_path and _is_valid_source_path(file_path):
                    reads.add(file_path)

            elif fn in ("grep", "rg"):
                path = args.get("path", "")
                if path and _is_valid_source_path(path):
                    reads.add(path)

            elif fn == "bash":
                cmd = args.get("command", "")
                if cmd and not _is_non_read_command(cmd):
                    for p in _extract_paths_from_command(cmd):
                        reads.add(p)

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

    return reads, writes


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

EXTRACTORS = {
    "claude-code": _extract_claude_code,
    "codex": _extract_codex,
    "copilot": _extract_copilot,
}


def extract_reads_writes(trajectory, agent):
    return EXTRACTORS[agent](trajectory)


# ---------------------------------------------------------------------------
# Per-instance stats
# ---------------------------------------------------------------------------

def compute_instance_stats(reads, writes, source_files):
    source_set = {f"/app/{s.lstrip('/')}" for s in source_files}
    source_set = {s for s in source_set if os.path.basename(s) not in EXCLUDED_GOLD_FILES}
    return {
        "read": _precision_recall(reads, source_set),
        "write": _precision_recall(writes, source_set),
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _avg(values):
    return sum(values) / len(values) if values else 0.0


def _summary_row(label, entries):
    """Return (label, n, read_rec, read_prec, write_rec, write_prec) tuple."""
    n = len(entries)
    if n == 0:
        return (label, 0, 0.0, 0.0, 0.0, 0.0)
    rr = _avg([e["read"]["recall"] for e in entries])
    rp = _avg([e["read"]["precision"] for e in entries])
    wr = _avg([e["write"]["recall"] for e in entries])
    wp = _avg([e["write"]["precision"] for e in entries])
    return (label, n, rr, rp, wr, wp)


def print_summary(label, entries):
    """Print summary stats for a list of per-instance stat entries."""
    _, n, rr, rp, wr, wp = _summary_row(label, entries)
    if n == 0:
        print(f"  {label}: 0 instances")
        return
    print(f"  {label} ({n} instances):")
    print(f"    Read  — recall: {rr:.2f}  precision: {rp:.2f}")
    print(f"    Write — recall: {wr:.2f}  precision: {wp:.2f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Unified file recall/precision stats across agent trajectory runs"
    )
    parser.add_argument("input_dirs", nargs="*",
                        help="Directories containing *-output.zip trajectory files (default: RUNS list)")
    parser.add_argument("--per-instance", action="store_true",
                        help="Print per-instance detail lines")
    parser.add_argument("--exclude-tests", action="store_true",
                        help="Exclude *Tests.java files from reads/writes")
    parser.add_argument("--output-md", type=str,
                        default=os.path.join(os.path.dirname(__file__), "file-recall-precision-results.md"),
                        help="Path for Markdown output (default: analysis/file-recall-precision-results.md)")
    args = parser.parse_args()

    # Build (path, label) pairs from CLI args or hardcoded RUNS list
    if args.input_dirs:
        runs = [(d, None) for d in args.input_dirs]
    else:
        runs = list(RUNS)

    # Collect results for MD output: list of (label, agent, all, resolved, unresolved)
    md_runs = []

    for input_dir, custom_label in runs:
        zips = get_all_trajectory_zips(input_dir)
        if not zips:
            print(f"No *-output.zip files found in {input_dir}", file=sys.stderr)
            continue

        # Detect agent from first zip
        agent = detect_agent(zips[0][0])
        label = custom_label or os.path.basename(input_dir.rstrip("/"))
        print(f"{'=' * 70}")
        print(f"Run: {label}")
        print(f"Agent: {agent}  |  Instances: {len(zips)}")
        print(f"{'=' * 70}")

        all_stats = []
        resolved_stats = []
        unresolved_stats = []

        for zip_path, instance_id in zips:
            resolved = is_resolved_from_zip(zip_path)
            source_files = source_files_from_instance_id(instance_id)

            try:
                trajectory = load_trajectory(zip_path, agent)
            except (KeyError, zipfile.BadZipFile) as e:
                print(f"  WARN: skipping {instance_id}: {e}", file=sys.stderr)
                continue

            reads, writes = extract_reads_writes(trajectory, agent)

            if args.exclude_tests:
                reads = {p for p in reads if not _is_test_file(p)}
                writes = {p for p in writes if not _is_test_file(p)}

            stats = compute_instance_stats(reads, writes, source_files)

            all_stats.append(stats)
            if resolved:
                resolved_stats.append(stats)
            else:
                unresolved_stats.append(stats)

            if args.per_instance:
                status = "RESOLVED" if resolved else "UNRESOLVED"
                r, w = stats["read"], stats["write"]
                print(f"  {instance_id}  {status}  "
                      f"r_rec={r['recall']:.2f}  r_prec={r['precision']:.2f}  "
                      f"w_rec={w['recall']:.2f}  w_prec={w['precision']:.2f}")

        print()
        print_summary("Overall", all_stats)
        print_summary("Resolved", resolved_stats)
        print_summary("Unresolved", unresolved_stats)
        print()

        md_runs.append((label, agent, all_stats, resolved_stats, unresolved_stats))

    # -----------------------------------------------------------------------
    # Markdown output
    # -----------------------------------------------------------------------
    if args.output_md and md_runs:
        lines = ["# File Recall / Precision Results\n"]
        for run_label, run_agent, all_s, res_s, unres_s in md_runs:
            lines.append(f"## {run_label}\n")
            lines.append(f"**Agent:** {run_agent}  |  **Instances:** {len(all_s)}\n")
            lines.append("| Split | N | Read Recall | Read Precision | Write Recall | Write Precision |")
            lines.append("|-------|--:|:-----------:|:--------------:|:------------:|:---------------:|")
            for split_label, split_entries in [("Overall", all_s), ("Resolved", res_s), ("Unresolved", unres_s)]:
                _, n, rr, rp, wr, wp = _summary_row(split_label, split_entries)
                lines.append(f"| {split_label} | {n} | {rr:.2f} | {rp:.2f} | {wr:.2f} | {wp:.2f} |")
            lines.append("")
        md_content = "\n".join(lines)
        with open(args.output_md, "w") as f:
            f.write(md_content)
        print(f"Markdown results written to {args.output_md}")


if __name__ == "__main__":
    main()
