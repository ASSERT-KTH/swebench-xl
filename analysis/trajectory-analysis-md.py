#!/usr/bin/env python3
"""
Trajectory analysis script for SWEBench-XL trajectories — Markdown output.

Reads all trajectories in ./full-trajectories and the reduced gold patches,
then outputs a comprehensive Markdown report with:
- Overview (resolve rate, exit/build statuses)
- Steps & API calls
- Token usage and costs
- Action/command patterns
- File access stats
- Error rates
- Elasticsearch / test-run stats
- Gold patch stats (using reduced gold patches)
- Agent edits vs gold patch comparison
- Per-trajectory summary table
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

TRAJECTORIES_DIR = Path(__file__).parent.parent / "re-run-with-wrapper"
REDUCED_GOLD_PATCHES_PATH = Path(__file__).parent.parent / "reduced_gold_patches.json"
OUTPUT_PATH = Path(__file__).parent.parent / "trajectory_analysis_with_wrapper.md"


# ---------------------------------------------------------------------------
# Gold patch parsing (reduced)
# ---------------------------------------------------------------------------

def parse_gold_patches() -> dict[str, dict]:
    """Return {instance_id: {files, n_files, added, removed, hunks}} from reduced gold patches."""
    if not REDUCED_GOLD_PATCHES_PATH.exists():
        return {}
    with REDUCED_GOLD_PATCHES_PATH.open() as f:
        entries = json.load(f)
    result = {}
    for entry in entries:
        iid = entry["instance_id"]
        patch = entry.get("reduced_patch", "")
        files = set(entry.get("required_files", []))
        added = len(re.findall(r"^\+(?!\+\+)", patch, re.MULTILINE))
        removed = len(re.findall(r"^-(?!--)", patch, re.MULTILINE))
        hunks = len(re.findall(r"^@@ ", patch, re.MULTILINE))
        result[iid] = {
            "files": files,
            "n_files": len(files),
            "added": added,
            "removed": removed,
            "hunks": hunks,
            "changed_lines": added + removed,
        }
    return result


# ---------------------------------------------------------------------------
# Command categorization
# ---------------------------------------------------------------------------

CATEGORY_PATTERNS = [
    ("find_ls",   re.compile(r"^\s*(find|ls)\b")),
    # edit must come before read so "cat <<EOF" is classified as edit, not read
    ("edit",      re.compile(
        r"^\s*(sed|awk|tee|patch|nano|vim|vi|emacs)\b"
        r"|^\s*(echo|printf).*>>?\s*\S"
        r"|^\s*cat\s+<<"
        r"|^\s*python3?\s+-c\b.*(?:>|open.*['\"]w['\"])"
        r"|^\s*mv\b"
    )),
    # Negative lookahead: cat that is NOT a heredoc
    ("read",      re.compile(r"^\s*(?:cat(?!\s+<<)|head|tail|less|more)\b")),
    ("grep",      re.compile(r"^\s*(grep|rg|ag|awk.*match)\b")),
    # compile must come before test so gradlew :compileJava isn't counted as a test run
    ("compile",   re.compile(
        r"^\s*(\./gradlew(?:\.real)?|gradle)\b(?!.*(?::test\b|(?<!\w)test\b)|.*--tests\b)"
        r"|^\s*mvn\b.*\bcompile\b"
    )),
    ("test",      re.compile(
        r"^\s*(\./gradlew(?:\.real)?|gradle)\b(?=.*(?::test\b|(?<!\w)test\b)|.*--tests\b)"
        r"|^\s*(mvn\s+test|pytest|python3?\s+-m\s+pytest|"
        r"npm\s+test|yarn\s+test|go\s+test|cargo\s+test|make\s+test|"
        r"java\s+.*[Tt]est)\b"
    )),
    ("git",       re.compile(r"^\s*git\b")),
    ("submit",    re.compile(r"COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT")),
]


def categorize_command(cmd: str) -> str:
    for name, pattern in CATEGORY_PATTERNS:
        if pattern.search(cmd):
            return name
    return "other"


def strip_heredocs(cmd: str) -> str:
    """Remove heredoc body lines so they aren't misclassified as commands."""
    lines = cmd.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.search(r"<<-?['\"]?(\w+)['\"]?", line)
        if m:
            delimiter = m.group(1)
            result.append(line)
            i += 1
            while i < len(lines) and lines[i].strip() != delimiter:
                i += 1
            if i < len(lines):
                i += 1
        else:
            result.append(line)
            i += 1
    return "\n".join(result)


def split_compound_command(cmd: str) -> list[str]:
    """Split a bash compound command into individual sub-command segments.

    Strips heredoc bodies first, then splits on &&, ||, ; and newlines —
    but only outside of single- or double-quoted strings.
    """
    cleaned = strip_heredocs(cmd)
    segs: list[str] = []
    current: list[str] = []
    in_single = in_double = False
    i = 0
    while i < len(cleaned):
        c = cleaned[i]
        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
        elif c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
        elif not in_single and not in_double:
            if c in ("&", "|") and i + 1 < len(cleaned) and cleaned[i + 1] == c:
                segs.append("".join(current).strip())
                current = []
                i += 2
                continue
            elif c in (";", "\n"):
                segs.append("".join(current).strip())
                current = []
            else:
                current.append(c)
        else:
            current.append(c)
        i += 1
    if current:
        segs.append("".join(current).strip())
    return [s for s in segs if s]


# ---------------------------------------------------------------------------
# File path extraction
# ---------------------------------------------------------------------------

def _looks_like_path(tok: str) -> bool:
    tok = tok.strip("'\"")
    if not tok or tok.startswith("-") or tok in (".", "..", "/"):
        return False
    if "*" in tok and "/" not in tok:
        return False
    return "/" in tok or ("." in tok and not tok.startswith("."))


def extract_read_files(seg: str) -> set[str]:
    files: set[str] = set()
    if re.search(r"cat\s+<<", seg):
        return files
    m = re.match(r"\s*(?:cat|head|tail|less|more)\s+(.*)", seg)
    if not m:
        return files
    args = m.group(1).split("|")[0]
    args = re.sub(r"-\w+\s*\d*", "", args)
    for tok in args.split():
        tok = tok.strip("'\"")
        if _looks_like_path(tok):
            files.add(tok)
    return files


def extract_grep_files(seg: str) -> set[str]:
    files: set[str] = set()
    for subseg in seg.split("|"):
        subseg = subseg.strip()
        if not re.match(r"\s*(grep|rg|ag)\b", subseg):
            continue
        tokens = subseg.split()
        i, pattern_seen = 1, False
        value_flags = {"-A", "-B", "-C", "-m", "-e", "--include", "--exclude",
                       "--include-glob", "--exclude-glob"}
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith("-"):
                i += 2 if tok in value_flags else 1
            elif not pattern_seen:
                pattern_seen = True
                i += 1
            else:
                tok = tok.strip("'\"")
                if _looks_like_path(tok):
                    files.add(tok)
                i += 1
    return files


def extract_edit_files(seg: str) -> set[str]:
    files: set[str] = set()

    def add(tok: str) -> None:
        tok = tok.strip("'\"")
        if _looks_like_path(tok):
            files.add(tok)

    m = re.search(r"cat\s+<<['\"]?\w+['\"]?\s+>\s*(\S+)", seg)
    if m:
        add(m.group(1))
        return files

    if re.match(r"\s*sed\b", seg):
        rest = re.sub(r"-[iE]\S*", "", seg[seg.index("sed") + 3:])
        rest = re.sub(r"'[^']*'", "", rest)
        rest = re.sub(r'"[^"]*"', "", rest)
        tokens = rest.split()
        if tokens:
            add(tokens[-1])
        return files

    if re.match(r"\s*python3?\s+-c\b", seg):
        for rm in re.finditer(r">{1,2}\s*(\S+)", seg):
            add(rm.group(1))
        return files

    mm = re.match(r"\s*mv\s+\S+\s+(\S+)", seg)
    if mm:
        add(mm.group(1))
        return files

    if re.match(r"\s*(?:echo|printf)\b", seg):
        for rm in re.finditer(r">{1,2}\s*(\S+)", seg):
            add(rm.group(1))
        return files

    tm = re.match(r"\s*tee\s+(\S+)", seg)
    if tm:
        add(tm.group(1))
        return files

    m = re.search(r">\s*([^\s|;]+)", seg)
    if m:
        add(m.group(1))
    return files


# ---------------------------------------------------------------------------
# Elasticsearch / test-run patterns
# ---------------------------------------------------------------------------

ES_ROOT_ERROR = re.compile(r"can not run elasticsearch as root", re.IGNORECASE)
ES_ROOT_BYPASS = re.compile(r"\buseradd\b", re.IGNORECASE)
GRADLE_TEST_RUN = re.compile(
    r"^\s*(\./gradlew(?:\.real)?|gradle)\b"
    r"(?=.*(?::test\b|(?<!\w)test\b)|.*--tests\b)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Observation parsing
# ---------------------------------------------------------------------------

def parse_observation(content: str) -> dict | None:
    prefix = "Observation: "
    if not content.startswith(prefix):
        return None
    raw = content[len(prefix):]
    try:
        obs = ast.literal_eval(raw)
        if isinstance(obs, dict):
            return obs
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Verifier build status
# ---------------------------------------------------------------------------

def _verifier_build_status(traj_dir: Path, reward: float | None) -> str:
    if reward is not None and reward >= 1.0:
        return "tests_passed"

    out_path = traj_dir / "verifier" / "output.json"
    stdout_path = traj_dir / "verifier" / "run-script-stdout.txt"

    tests: list[dict] = []
    if out_path.exists():
        with out_path.open() as f:
            tests = json.load(f).get("tests", [])

    build_failed = False
    if stdout_path.exists():
        with stdout_path.open() as f:
            build_failed = bool(re.search(r"> Task .+ FAILED", f.read()))

    if not tests:
        return "build_failed" if build_failed else "unknown"

    failed = [t for t in tests if t["status"] == "FAILED"]
    if failed and all(t["name"].endswith("::classMethod") for t in failed):
        return "compile_error"

    return "tests_failed"


# ---------------------------------------------------------------------------
# Per-trajectory analysis
# ---------------------------------------------------------------------------

def analyze_trajectory(traj_dir: Path) -> dict:
    result_path = traj_dir / "result.json"
    traj_path = traj_dir / "agent" / "trajectory.json"
    mini_traj_path = traj_dir / "agent" / "mini-swe-agent.trajectory.json"

    result: dict = {}
    if result_path.exists():
        with result_path.open() as f:
            result = json.load(f)

    traj: dict = {}
    if traj_path.exists():
        with traj_path.open() as f:
            traj = json.load(f)

    trial_name = traj_dir.name
    task_name = result.get("task_name", trial_name.rsplit("__", 1)[0])

    # Rewards / success
    verifier = result.get("verifier_result", {})
    reward = verifier.get("rewards", {}).get("reward", None)
    resolved = bool(reward and reward >= 1.0)

    # Cost & tokens
    agent_result = result.get("agent_result", {})
    cost_usd = agent_result.get("cost_usd")
    n_input_tokens = agent_result.get("n_input_tokens")
    n_output_tokens = agent_result.get("n_output_tokens")
    n_cache_tokens = agent_result.get("n_cache_tokens")

    # Timing
    started_at = result.get("started_at")
    finished_at = result.get("finished_at")
    duration_sec = None
    if started_at and finished_at:
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        try:
            t0 = datetime.strptime(started_at, fmt).replace(tzinfo=timezone.utc)
            t1 = datetime.strptime(finished_at, fmt).replace(tzinfo=timezone.utc)
            duration_sec = (t1 - t0).total_seconds()
        except ValueError:
            pass

    # Trajectory steps (ATIF format)
    steps = traj.get("steps", [])
    agent_steps = [s for s in steps if s.get("source") == "agent"]
    valid_steps = [s for s in agent_steps if s.get("tool_calls")]
    n_format_errors = len(agent_steps) - len(valid_steps)
    n_steps = len(valid_steps)
    api_calls = n_steps

    # Exit status
    exit_status = "unknown"
    if mini_traj_path.exists():
        with mini_traj_path.open() as f:
            mini_info = json.load(f).get("info", {})
        exit_status = mini_info.get("exit_status", "unknown")
    elif valid_steps:
        last_cmd = valid_steps[-1]["tool_calls"][0]["arguments"].get("command", "")
        if "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in last_cmd:
            exit_status = "Submitted"

    # Command categorization & file tracking
    action_counts: Counter = Counter()
    files_read: set[str] = set()
    files_searched: set[str] = set()
    files_edited: set[str] = set()
    n_errors = 0
    n_empty_outputs = 0

    hit_root_error = False
    bypassed_root = False
    ran_tests_ok = False

    for step in valid_steps:
        cmd = step["tool_calls"][0]["arguments"].get("command", "").strip()

        segs = split_compound_command(cmd)
        for seg in segs:
            cat = categorize_command(seg)
            action_counts[cat] += 1
            if cat == "read":
                files_read |= extract_read_files(seg)
            elif cat == "grep":
                files_searched |= extract_grep_files(seg)
            elif cat == "edit":
                files_edited |= extract_edit_files(seg)

        if ES_ROOT_BYPASS.search(cmd) and re.search(r"\bsu\b", cmd):
            bypassed_root = True

        obs_content = ""
        try:
            obs_content = step["observation"]["results"][0]["content"]
        except (KeyError, IndexError, TypeError):
            pass
        obs = parse_observation(obs_content)
        if obs is not None:
            rc = obs.get("returncode", 0)
            output = obs.get("output", "")

            if rc != 0:
                n_errors += 1
            if not output.strip():
                n_empty_outputs += 1

            if ES_ROOT_ERROR.search(output):
                hit_root_error = True

            if any(GRADLE_TEST_RUN.match(seg) for seg in segs) and rc == 0:
                ran_tests_ok = True

    total_actions = sum(action_counts.values())
    build_status = _verifier_build_status(traj_dir, reward)

    test_stdout_path = traj_dir / "verifier" / "test-stdout.txt"
    patch_fuzz_fallback = False
    if test_stdout_path.exists():
        with test_stdout_path.open() as f:
            patch_fuzz_fallback = "git apply for test_patch failed, trying patch --fuzz=5" in f.read()

    return {
        "trial_name": trial_name,
        "task_name": task_name,
        "exit_status": exit_status,
        "build_status": build_status,
        "reward": reward,
        "resolved": resolved,
        "cost_usd": cost_usd,
        "n_input_tokens": n_input_tokens,
        "n_output_tokens": n_output_tokens,
        "n_cache_tokens": n_cache_tokens,
        "duration_sec": duration_sec,
        "api_calls": api_calls,
        "n_steps": n_steps,
        "n_format_errors": n_format_errors,
        "n_errors": n_errors,
        "n_empty_outputs": n_empty_outputs,
        "total_actions": total_actions,
        "actions": dict(action_counts),
        "n_files_read": len(files_read),
        "n_files_searched": len(files_searched),
        "n_files_edited": len(files_edited),
        "n_files_touched": len(files_read | files_searched | files_edited),
        "files_edited": files_edited,
        "hit_root_error": hit_root_error,
        "bypassed_root": bypassed_root,
        "ran_tests_ok": ran_tests_ok,
        "patch_fuzz_fallback": patch_fuzz_fallback,
    }


# ---------------------------------------------------------------------------
# Aggregate stats helpers
# ---------------------------------------------------------------------------

def safe_mean(vals):
    vals = [v for v in vals if v is not None]
    return mean(vals) if vals else None

def safe_median(vals):
    vals = [v for v in vals if v is not None]
    return median(vals) if vals else None

def safe_stdev(vals):
    vals = [v for v in vals if v is not None]
    return stdev(vals) if len(vals) >= 2 else None

def fmt(val, decimals=2):
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"

def pct(num, denom):
    return f"{100 * num / denom:.1f}%" if denom else "N/A"


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

class MarkdownWriter:
    def __init__(self):
        self.lines: list[str] = []

    def h1(self, text: str):
        self.lines.append(f"# {text}\n")

    def h2(self, text: str):
        self.lines.append(f"## {text}\n")

    def h3(self, text: str):
        self.lines.append(f"### {text}\n")

    def p(self, text: str):
        self.lines.append(f"{text}\n")

    def blank(self):
        self.lines.append("")

    def table(self, headers: list[str], rows: list[list[str]], alignments: list[str] | None = None):
        """Write a markdown table. alignments: list of 'l', 'c', 'r' per column."""
        if not alignments:
            alignments = ["l"] * len(headers)
        sep_map = {"l": ":---", "c": ":---:", "r": "---:"}

        self.lines.append("| " + " | ".join(headers) + " |")
        self.lines.append("| " + " | ".join(sep_map.get(a, "---") for a in alignments) + " |")
        for row in rows:
            self.lines.append("| " + " | ".join(str(c) for c in row) + " |")
        self.blank()

    def stat_table(self, label: str, vals: list, decimals: int = 1):
        """Convenience: one-row min/median/mean/max/stdev table."""
        clean = [v for v in vals if v is not None]
        if not clean:
            self.p(f"*No data for {label}.*")
            return
        row = [
            f"{min(clean):.{decimals}f}",
            fmt(safe_median(clean), decimals),
            fmt(safe_mean(clean), decimals),
            f"{max(clean):.{decimals}f}",
            fmt(safe_stdev(clean), decimals),
        ]
        self.table(
            [label, "Min", "Median", "Mean", "Max", "Stdev"],
            [[""] + row],
            ["l", "r", "r", "r", "r", "r"],
        )

    def write(self, path: Path):
        with path.open("w") as f:
            f.write("\n".join(self.lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    traj_dirs = sorted(TRAJECTORIES_DIR.iterdir())
    if not traj_dirs:
        print(f"No trajectories found in {TRAJECTORIES_DIR}", file=sys.stderr)
        sys.exit(1)

    gold_patches = parse_gold_patches()
    print(f"Loaded {len(gold_patches)} reduced gold patches.")
    print(f"Analyzing {len(traj_dirs)} trajectories...")

    records: list[dict] = []
    for d in traj_dirs:
        if d.is_dir():
            try:
                rec = analyze_trajectory(d)
                records.append(rec)
            except Exception as e:
                print(f"  [WARN] Failed to parse {d.name}: {e}", file=sys.stderr)

    n = len(records)
    print(f"Parsed {n} trajectories successfully.")

    md = MarkdownWriter()

    # ------------------------------------------------------------------ #
    # Title
    # ------------------------------------------------------------------ #
    md.h1("Trajectory Analysis Report")
    md.p(f"*Generated from {n} trajectories in `full-trajectories/` using reduced gold patches.*")
    md.blank()

    # ------------------------------------------------------------------ #
    # 1. Overview
    # ------------------------------------------------------------------ #
    md.h2("1. Overview")

    n_resolved = sum(1 for r in records if r["resolved"])
    exit_statuses = Counter(r["exit_status"] for r in records)
    build_statuses = Counter(r["build_status"] for r in records)
    rewards = [r["reward"] for r in records if r["reward"] is not None]

    md.table(
        ["Metric", "Value"],
        [
            ["Total trajectories", str(n)],
            ["Resolved (reward ≥ 1)", f"{n_resolved} ({pct(n_resolved, n)})"],
            ["Mean reward", fmt(safe_mean(rewards), 3)],
        ],
        ["l", "r"],
    )

    md.h3("Exit Statuses")
    md.table(
        ["Status", "Count", "%"],
        [[s, str(c), pct(c, n)] for s, c in exit_statuses.most_common()],
        ["l", "r", "r"],
    )

    md.h3("Build / Verifier Statuses")
    md.p("- **tests_passed** — all required tests passed")
    md.p("- **tests_failed** — tests ran but required ones failed")
    md.p("- **compile_error** — class loading failure (::classMethod)")
    md.p("- **build_failed** — build error, no tests ran")
    md.blank()
    md.table(
        ["Status", "Count", "%"],
        [[s, str(c), pct(c, n)] for s, c in build_statuses.most_common()],
        ["l", "r", "r"],
    )

    # ------------------------------------------------------------------ #
    # 2. Steps & API calls
    # ------------------------------------------------------------------ #
    md.h2("2. Steps & API Calls")

    steps_vals = [r["n_steps"] for r in records]
    api_vals = [r["api_calls"] for r in records]

    md.stat_table("Steps per trajectory", steps_vals)
    md.stat_table("API calls per trajectory", api_vals)

    # ------------------------------------------------------------------ #
    # 3. Cost & tokens
    # ------------------------------------------------------------------ #
    md.h2("3. Cost & Tokens")

    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    in_toks = [r["n_input_tokens"] for r in records if r["n_input_tokens"] is not None]
    out_toks = [r["n_output_tokens"] for r in records if r["n_output_tokens"] is not None]
    cache_toks = [r["n_cache_tokens"] for r in records if r["n_cache_tokens"] is not None]

    if costs:
        md.table(
            ["Metric", "Value"],
            [
                ["Total cost (USD)", f"${sum(costs):.4f}"],
                ["Min cost", f"${min(costs):.4f}"],
                ["Median cost", f"${safe_median(costs):.4f}"],
                ["Mean cost", f"${safe_mean(costs):.4f}"],
                ["Max cost", f"${max(costs):.4f}"],
            ],
            ["l", "r"],
        )

    md.table(
        ["Token type", "Mean", "Median"],
        [
            ["Input tokens", fmt(safe_mean(in_toks), 0), fmt(safe_median(in_toks), 0)],
            ["Output tokens", fmt(safe_mean(out_toks), 0), fmt(safe_median(out_toks), 0)],
            ["Cache tokens", fmt(safe_mean(cache_toks), 0), fmt(safe_median(cache_toks), 0)],
        ],
        ["l", "r", "r"],
    )

    # ------------------------------------------------------------------ #
    # 4. Duration
    # ------------------------------------------------------------------ #
    md.h2("4. Timing")

    durations = [r["duration_sec"] for r in records if r["duration_sec"] is not None]
    if durations:
        md.stat_table("Duration (seconds)", durations, 0)
        md.p(f"**Total wall-clock time:** {sum(durations)/3600:.2f} hours")
        md.blank()

    # ------------------------------------------------------------------ #
    # 5. Action patterns
    # ------------------------------------------------------------------ #
    md.h2("5. Action / Command Patterns")

    total_actions: Counter = Counter()
    for r in records:
        for cat, cnt in r["actions"].items():
            total_actions[cat] += cnt

    grand_total = sum(total_actions.values())
    md.p(f"**Total commands across all trajectories:** {grand_total}")
    md.blank()

    action_rows = []
    for cat, count in sorted(total_actions.items(), key=lambda x: -x[1]):
        p = f"{100 * count / grand_total:.1f}%" if grand_total else "N/A"
        mean_per = f"{count / n:.1f}"
        action_rows.append([f"`{cat}`", str(count), p, mean_per])

    md.table(
        ["Category", "Count", "% of total", "Mean/traj"],
        action_rows,
        ["l", "r", "r", "r"],
    )

    md.h3("Per-Trajectory Action Counts (mean / median / max)")
    act_detail_rows = []
    total_acts_per = [r["total_actions"] for r in records]
    act_detail_rows.append([
        "**Total**",
        fmt(safe_mean(total_acts_per), 1),
        fmt(safe_median(total_acts_per), 1),
        str(max(total_acts_per)),
    ])
    for cat in sorted(total_actions.keys(), key=lambda c: -total_actions[c]):
        vals = [r["actions"].get(cat, 0) for r in records]
        act_detail_rows.append([
            f"`{cat}`",
            fmt(safe_mean(vals), 1),
            fmt(safe_median(vals), 1),
            str(max(vals)),
        ])
    md.table(["Category", "Mean", "Median", "Max"], act_detail_rows, ["l", "r", "r", "r"])

    # ------------------------------------------------------------------ #
    # 6. File access stats
    # ------------------------------------------------------------------ #
    md.h2("6. File Access (unique paths per trajectory)")

    file_rows = []
    for label, key in [
        ("Files read (cat/head/tail)", "n_files_read"),
        ("Files searched (grep/rg)", "n_files_searched"),
        ("Files edited/written", "n_files_edited"),
        ("Total unique files touched", "n_files_touched"),
    ]:
        vals = [r[key] for r in records]
        file_rows.append([label, fmt(safe_mean(vals), 1), fmt(safe_median(vals), 1), str(max(vals))])
    md.table(["Metric", "Mean", "Median", "Max"], file_rows, ["l", "r", "r", "r"])

    md.h3("Per-Trajectory File Counts")
    ft_rows = []
    for r in records:
        ft_rows.append([
            f"`{r['trial_name']}`",
            str(r["n_files_read"]),
            str(r["n_files_searched"]),
            str(r["n_files_edited"]),
            str(r["n_files_touched"]),
        ])
    md.table(["Trial", "Read", "Grep", "Edit", "Total"], ft_rows, ["l", "r", "r", "r", "r"])

    # ------------------------------------------------------------------ #
    # 7. Error rates
    # ------------------------------------------------------------------ #
    md.h2("7. Error & Output Stats")

    for label, key in [
        ("Failed commands (non-zero rc)", "n_errors"),
        ("Empty outputs", "n_empty_outputs"),
        ("Format errors (multi-block)", "n_format_errors"),
    ]:
        vals = [r[key] for r in records]
        md.stat_table(label, vals)

    # ------------------------------------------------------------------ #
    # 8. Elasticsearch / test-run stats
    # ------------------------------------------------------------------ #
    md.h2("8. Elasticsearch / Test-Run Stats")

    n_hit_root = sum(1 for r in records if r["hit_root_error"])
    n_bypassed = sum(1 for r in records if r["bypassed_root"])
    n_tests_ok = sum(1 for r in records if r["ran_tests_ok"])
    n_fuzz = sum(1 for r in records if r["patch_fuzz_fallback"])
    n_stuck_root = sum(1 for r in records if r["hit_root_error"] and not r["bypassed_root"])

    bypass_pct = pct(n_bypassed, n_hit_root) if n_hit_root else "N/A"
    md.table(
        ["Metric", "Count", "%"],
        [
            ["Hit 'cannot run as root' error", str(n_hit_root), pct(n_hit_root, n)],
            ["Applied useradd+su bypass", str(n_bypassed), bypass_pct],
            ["Stuck on root error (no bypass)", str(n_stuck_root), pct(n_stuck_root, n)],
            ["Ran tests with exit 0 (≥1 time)", str(n_tests_ok), pct(n_tests_ok, n)],
            ["Verifier patch fuzz fallback", str(n_fuzz), pct(n_fuzz, n)],
        ],
        ["l", "r", "r"],
    )

    if n_fuzz:
        md.p("**Fuzz-fallback trajectories:**")
        for r in records:
            if r["patch_fuzz_fallback"]:
                md.p(f"- `{r['trial_name']}`")
        md.blank()

    md.h3("Per-Trajectory Breakdown")
    es_rows = []
    for r in records:
        es_rows.append([
            f"`{r['trial_name']}`",
            "✅" if r["hit_root_error"] else "—",
            "✅" if r["bypassed_root"] else "—",
            "✅" if r["ran_tests_ok"] else "—",
            "✅" if r["patch_fuzz_fallback"] else "—",
        ])
    md.table(
        ["Trial", "Root Err", "Bypass", "Tests OK", "Fuzz Patch"],
        es_rows,
        ["l", "c", "c", "c", "c"],
    )

    # ------------------------------------------------------------------ #
    # 9. Gold patch stats (reduced)
    # ------------------------------------------------------------------ #
    matched = [r for r in records if r["task_name"] in gold_patches]
    if gold_patches:
        md.h2("9. Gold Patch Stats (reduced — source files only)")
        md.p("Statistics computed from `reduced_gold_patches.json` which excludes changelogs, "
             "test files, test fixtures, and documentation from the gold patches.")
        md.blank()

        all_gold = list(gold_patches.values())
        gold_metrics = {
            "Files changed": [g["n_files"] for g in all_gold],
            "Hunks": [g["hunks"] for g in all_gold],
            "Lines added": [g["added"] for g in all_gold],
            "Lines removed": [g["removed"] for g in all_gold],
            "Lines changed": [g["changed_lines"] for g in all_gold],
        }

        md.p(f"**Gold patches loaded:** {len(all_gold)} | **Overlap with trajectories:** {len(matched)}")
        md.blank()

        gp_rows = []
        for label, vals in gold_metrics.items():
            gp_rows.append([
                label,
                fmt(safe_mean(vals), 1),
                fmt(safe_median(vals), 1),
                str(min(vals)),
                str(max(vals)),
            ])
        md.table(["Metric", "Mean", "Median", "Min", "Max"], gp_rows, ["l", "r", "r", "r", "r"])

    # ------------------------------------------------------------------ #
    # 10. Agent edits vs gold patch comparison
    # ------------------------------------------------------------------ #
    def write_agent_vs_gold(subset: list[dict], title: str):
        if not subset:
            md.p(f"*(no trajectories in this subset)*")
            return

        hit_rates = []
        precision_rates = []
        exact_matches = 0

        avsg_rows = []
        for r in subset:
            gold = gold_patches[r["task_name"]]
            gold_files = gold["files"]
            agent_files = r["files_edited"]

            overlap = gold_files & agent_files
            hit = len(overlap) / len(gold_files) if gold_files else 0.0
            prec = len(overlap) / len(agent_files) if agent_files else 0.0
            hit_rates.append(hit)
            precision_rates.append(prec)
            if gold_files and agent_files and gold_files == agent_files:
                exact_matches += 1

            overlap_names = ", ".join(Path(f).name for f in sorted(overlap)) or "—"
            if len(overlap_names) > 50:
                overlap_names = overlap_names[:47] + "..."
            avsg_rows.append([
                f"`{r['trial_name']}`",
                str(len(gold_files)),
                str(len(agent_files)),
                f"{hit:.0%}",
                f"{prec:.0%}",
                overlap_names,
            ])

        md.table(
            ["Trial", "Gold", "Agent", "Recall", "Precision", "Overlap files"],
            avsg_rows,
            ["l", "r", "r", "r", "r", "l"],
        )

        n_m = len(subset)
        md.p(f"**Summary ({title}, {n_m} trajectories):**")
        md.table(
            ["Metric", "Mean", "Median"],
            [
                ["Recall (gold files agent edited)", fmt(safe_mean(hit_rates)), fmt(safe_median(hit_rates))],
                ["Precision (agent edits in gold set)", fmt(safe_mean(precision_rates)), fmt(safe_median(precision_rates))],
                ["Exact file-set match", f"{exact_matches}/{n_m}", ""],
            ],
            ["l", "r", "r"],
        )

    if matched and gold_patches:
        md.h2("10. Agent Edits vs Reduced Gold Patch")
        md.p("Comparison of files the agent edited vs files in the reduced (source-only) gold patch.")
        md.blank()

        md.h3("All Trajectories")
        write_agent_vs_gold(matched, "all")

        build_error_statuses = {"build_failed", "compile_error"}
        matched_build_errors = [r for r in matched if r["build_status"] in build_error_statuses]
        if matched_build_errors:
            md.h3("Build Failed / Compile Error Only")
            write_agent_vs_gold(matched_build_errors, "build/compile errors")

    # ------------------------------------------------------------------ #
    # 11. Per-trajectory summary table
    # ------------------------------------------------------------------ #
    md.h2("11. Per-Trajectory Summary")

    summary_rows = []
    for r in records:
        cost_str = f"${r['cost_usd']:.4f}" if r["cost_usd"] is not None else "N/A"
        reward_str = f"{r['reward']:.2f}" if r["reward"] is not None else "N/A"
        summary_rows.append([
            f"`{r['trial_name']}`",
            str(r["n_steps"]),
            cost_str,
            reward_str,
            r["exit_status"],
            r["build_status"],
        ])

    md.table(
        ["Trial", "Steps", "Cost", "Reward", "Exit", "Build"],
        summary_rows,
        ["l", "r", "r", "r", "l", "l"],
    )

    # Write
    md.write(OUTPUT_PATH)
    print(f"\nWrote {OUTPUT_PATH} ({len(md.lines)} lines)")


if __name__ == "__main__":
    main()
