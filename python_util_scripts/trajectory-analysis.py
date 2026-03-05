#!/usr/bin/env python3
"""
Trajectory analysis script for SWEBench-XL trajectories.

Reads all trajectories in ./full-trajectories and computes descriptive stats:
- Step counts and API calls
- Token usage and costs
- Action/command patterns (find/ls, read, grep/search, edit/write, test, git, etc.)
- Exit statuses and rewards
- Timing
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median, stdev

TRAJECTORIES_DIR = Path(__file__).parent.parent / "full-trajectories"
GOLD_PATCHES_PATH = Path(__file__).parent.parent / "benchmark" / "gold_patches.json"


# --- Gold patch parsing ---

def parse_gold_patches() -> dict[str, dict]:
    """Return {instance_id: {files, n_files, added, removed, hunks}} for all gold patches."""
    if not GOLD_PATCHES_PATH.exists():
        return {}
    with GOLD_PATCHES_PATH.open() as f:
        entries = json.load(f)
    result = {}
    for entry in entries:
        iid = entry["instance_id"]
        patch = entry.get("patch", "")
        files = set(re.findall(r"^(?:---|\+\+\+) b/(.+)$", patch, re.MULTILINE))
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

# --- Command categorization ---

CATEGORY_PATTERNS = [
    ("find_ls",   re.compile(r"^\s*(find|ls)\b")),
    # edit must come before read so "cat <<EOF" is classified as edit, not read
    ("edit",      re.compile(
        r"^\s*(sed|awk|tee|patch|nano|vim|vi|emacs)\b"
        r"|^\s*(echo|printf).*>>?\s*\S"                          # echo/printf redirecting to a file
        r"|^\s*cat\s+<<"                                         # heredoc write (cat <<EOF > file)
        r"|^\s*python3?\s+-c\b.*(?:>|open.*['\"]w['\"])"        # python -c with redirect or open('w')
        r"|^\s*mv\b"                                             # mv overwrites destination
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
                i += 1  # skip heredoc body
            if i < len(lines):
                i += 1  # skip closing delimiter line
        else:
            result.append(line)
            i += 1
    return "\n".join(result)


def split_compound_command(cmd: str) -> list[str]:
    """Split a bash compound command into individual sub-command segments.

    Strips heredoc bodies first, then splits on &&, ||, ; and newlines —
    but only outside of single- or double-quoted strings, so that
    semicolons inside sed scripts (e.g. 's/a/b;c/') are not treated as
    command separators.
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
            # && or ||
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


# --- File path extraction ---

def _looks_like_path(tok: str) -> bool:
    """Return True if token looks like a real file/dir path (not a flag or glob wildcard)."""
    tok = tok.strip("'\"")
    if not tok or tok.startswith("-") or tok in (".", "..", "/"):
        return False
    # Must contain a slash or a dot (extension), but not be a pure glob
    if "*" in tok and "/" not in tok:
        return False
    return "/" in tok or ("." in tok and not tok.startswith("."))


def extract_read_files(seg: str) -> set[str]:
    """Files passed to cat (non-heredoc), head, tail, less, more in one segment."""
    files: set[str] = set()
    if re.search(r"cat\s+<<", seg):
        return files  # heredoc write, not a read
    m = re.match(r"\s*(?:cat|head|tail|less|more)\s+(.*)", seg)
    if not m:
        return files
    args = m.group(1).split("|")[0]          # ignore piped sub-commands
    args = re.sub(r"-\w+\s*\d*", "", args)   # strip flags and numeric values
    for tok in args.split():
        tok = tok.strip("'\"")
        if _looks_like_path(tok):
            files.add(tok)
    return files


def extract_grep_files(seg: str) -> set[str]:
    """Files/dirs passed to grep/rg/ag in one segment (may include pipes)."""
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
    """Files written/modified by one edit-category command segment."""
    files: set[str] = set()

    def add(tok: str) -> None:
        tok = tok.strip("'\"")
        if _looks_like_path(tok):
            files.add(tok)

    # cat <<EOF > file
    m = re.search(r"cat\s+<<['\"]?\w+['\"]?\s+>\s*(\S+)", seg)
    if m:
        add(m.group(1))
        return files

    # sed -i [backup] 'script' file
    if re.match(r"\s*sed\b", seg):
        rest = re.sub(r"-[iE]\S*", "", seg[seg.index("sed") + 3:])
        rest = re.sub(r"'[^']*'", "", rest)
        rest = re.sub(r'"[^"]*"', "", rest)
        tokens = rest.split()
        if tokens:
            add(tokens[-1])
        return files

    # python3 -c '...' > outfile
    if re.match(r"\s*python3?\s+-c\b", seg):
        for rm in re.finditer(r">{1,2}\s*(\S+)", seg):
            add(rm.group(1))
        return files

    # mv tmp realfile  (e.g. python writes to .tmp then mv-renames)
    mm = re.match(r"\s*mv\s+\S+\s+(\S+)", seg)
    if mm:
        add(mm.group(1))
        return files

    # echo/printf > file  or  >> file
    if re.match(r"\s*(?:echo|printf)\b", seg):
        for rm in re.finditer(r">{1,2}\s*(\S+)", seg):
            add(rm.group(1))
        return files

    # tee file
    tm = re.match(r"\s*tee\s+(\S+)", seg)
    if tm:
        add(tm.group(1))
        return files

    # Generic > redirect fallback
    m = re.search(r">\s*([^\s|;]+)", seg)
    if m:
        add(m.group(1))
    return files


# --- Elasticsearch / test-run patterns ---

ES_ROOT_ERROR = re.compile(
    r"can not run elasticsearch as root", re.IGNORECASE
)

# The bypass always: creates a user (`useradd`) and then switches to it (`su`)
# to run the test command.
ES_ROOT_BYPASS = re.compile(r"\buseradd\b", re.IGNORECASE)

# Matches gradlew/gradle commands that actually *run* tests, not just compile.
# Two signals:
#   1. The Gradle task name ends in `:test` or is the bare word `test`
#      (e.g.  ./gradlew :x-pack:plugin:esql:test  or  gradle test)
#   2. The --tests flag is present (explicit test-filter, always a test run)
GRADLE_TEST_RUN = re.compile(
    r"^\s*(\./gradlew(?:\.real)?|gradle)\b"           # gradlew or gradle
    r"(?=.*(?::test\b|(?<!\w)test\b)|.*--tests\b)",   # task :test OR --tests flag
    re.IGNORECASE,
)


# --- Observation parsing ---

def parse_observation(content: str) -> dict | None:
    """Return {'output': str, 'returncode': int} or None."""
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


# --- Per-trajectory analysis ---

def _verifier_build_status(traj_dir: Path, reward: float | None) -> str:
    """Derive build/test status from verifier outputs."""
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

    # --- Basic identifiers ---
    trial_name = traj_dir.name
    task_name = result.get("task_name", trial_name.rsplit("__", 1)[0])

    # --- Rewards / success ---
    verifier = result.get("verifier_result", {})
    reward = verifier.get("rewards", {}).get("reward", None)
    resolved = bool(reward and reward >= 1.0)

    # --- Cost & tokens from result.json ---
    agent_result = result.get("agent_result", {})
    cost_usd = agent_result.get("cost_usd")
    n_input_tokens = agent_result.get("n_input_tokens")
    n_output_tokens = agent_result.get("n_output_tokens")
    n_cache_tokens = agent_result.get("n_cache_tokens")

    # --- Timing ---
    started_at = result.get("started_at")
    finished_at = result.get("finished_at")
    duration_sec = None
    if started_at and finished_at:
        from datetime import datetime, timezone
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        try:
            t0 = datetime.strptime(started_at, fmt).replace(tzinfo=timezone.utc)
            t1 = datetime.strptime(finished_at, fmt).replace(tzinfo=timezone.utc)
            duration_sec = (t1 - t0).total_seconds()
        except ValueError:
            pass

    # --- Trajectory steps (ATIF format) ---
    steps = traj.get("steps", [])
    agent_steps = [s for s in steps if s.get("source") == "agent"]

    # In ATIF, format-error turns are agent steps with no tool_calls.
    # Valid steps have exactly one tool_call with the executed command.
    valid_steps = [s for s in agent_steps if s.get("tool_calls")]
    n_format_errors = len(agent_steps) - len(valid_steps)
    n_steps = len(valid_steps)
    api_calls = n_steps

    # Exit status: from mini-swe-agent info block (most accurate source)
    exit_status = "unknown"
    if mini_traj_path.exists():
        with mini_traj_path.open() as f:
            mini_info = json.load(f).get("info", {})
        exit_status = mini_info.get("exit_status", "unknown")
    elif valid_steps:
        last_cmd = valid_steps[-1]["tool_calls"][0]["arguments"].get("command", "")
        if "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in last_cmd:
            exit_status = "Submitted"

    # --- Command categorization & file tracking ---
    action_counts: Counter = Counter()
    files_read: set[str] = set()
    files_searched: set[str] = set()
    files_edited: set[str] = set()
    n_errors = 0
    n_empty_outputs = 0

    # Elasticsearch / test-run tracking
    hit_root_error = False   # agent saw "can not run elasticsearch as root"
    bypassed_root = False    # agent used useradd+su bypass
    ran_tests_ok = False     # at least one test command exited with returncode 0

    for step in valid_steps:
        cmd = step["tool_calls"][0]["arguments"].get("command", "").strip()

        # Split compound commands (&&, ||, ;, newlines) so each sub-command is
        # categorized and its touched files tracked independently.
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

        # Detect root-bypass attempt: command uses both useradd and su
        if ES_ROOT_BYPASS.search(cmd) and re.search(r"\bsu\b", cmd):
            bypassed_root = True

        # Observation is co-located on the same step
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

            # Check for the ES root error anywhere in the output
            if ES_ROOT_ERROR.search(output):
                hit_root_error = True

            # Only count as "ran tests" if the gradlew task actually executes
            # tests (task ends in :test or --tests flag is present).
            # Plain compile tasks like :compileJava also match the "test"
            # action category but must not count here.
            if any(GRADLE_TEST_RUN.match(seg) for seg in segs) and rc == 0:
                ran_tests_ok = True

    total_actions = sum(action_counts.values())
    build_status = _verifier_build_status(traj_dir, reward)

    # Check whether the verifier had to fall back to fuzzy patch application
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
        # Elasticsearch / test-run stats
        "hit_root_error": hit_root_error,
        "bypassed_root": bypassed_root,
        "ran_tests_ok": ran_tests_ok,
        # Verifier patch application
        "patch_fuzz_fallback": patch_fuzz_fallback,
    }


# --- Aggregate stats helpers ---

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


# --- Main ---

def main():
    traj_dirs = sorted(TRAJECTORIES_DIR.iterdir())
    if not traj_dirs:
        print(f"No trajectories found in {TRAJECTORIES_DIR}")
        sys.exit(1)

    gold_patches = parse_gold_patches()
    print(f"Loaded {len(gold_patches)} gold patches.")
    print(f"Analyzing {len(traj_dirs)} trajectories...\n")

    records: list[dict] = []
    for d in traj_dirs:
        if d.is_dir():
            try:
                rec = analyze_trajectory(d)
                records.append(rec)
            except Exception as e:
                print(f"  [WARN] Failed to parse {d.name}: {e}")

    n = len(records)
    print(f"Parsed {n} trajectories successfully.\n")

    # ------------------------------------------------------------------ #
    # 1. Overview
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("OVERVIEW")
    print("=" * 60)

    n_resolved = sum(1 for r in records if r["resolved"])
    exit_statuses = Counter(r["exit_status"] for r in records)
    build_statuses = Counter(r["build_status"] for r in records)
    rewards = [r["reward"] for r in records if r["reward"] is not None]

    print(f"  Total trajectories:    {n}")
    print(f"  Resolved (reward>=1):  {n_resolved} ({100*n_resolved/n:.1f}%)")
    print(f"  Mean reward:           {fmt(safe_mean(rewards), 3)}")
    print(f"  Exit statuses:         {dict(exit_statuses)}")
    print(f"  Build statuses:        {dict(build_statuses)}")
    print(f"    tests_passed  — all required tests passed")
    print(f"    tests_failed  — tests ran but required ones failed")
    print(f"    compile_error — class loading failure (::classMethod)")
    print(f"    build_failed  — build error, no tests ran")
    print()

    # ------------------------------------------------------------------ #
    # 2. Steps & API calls
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("STEPS & API CALLS")
    print("=" * 60)

    steps = [r["n_steps"] for r in records]
    api_calls = [r["api_calls"] for r in records]

    print(f"  Steps per trajectory:  min / median / mean / max / stdev")
    print(f"    {min(steps)} / {fmt(safe_median(steps),1)} / {fmt(safe_mean(steps),1)} / {max(steps)} / {fmt(safe_stdev(steps),1)}")
    print()
    print(f"  API calls per trajectory:  min / median / mean / max / stdev")
    print(f"    {min(api_calls)} / {fmt(safe_median(api_calls),1)} / {fmt(safe_mean(api_calls),1)} / {max(api_calls)} / {fmt(safe_stdev(api_calls),1)}")
    print()

    # ------------------------------------------------------------------ #
    # 3. Cost & tokens
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("COST & TOKENS")
    print("=" * 60)

    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    in_toks = [r["n_input_tokens"] for r in records if r["n_input_tokens"] is not None]
    out_toks = [r["n_output_tokens"] for r in records if r["n_output_tokens"] is not None]
    cache_toks = [r["n_cache_tokens"] for r in records if r["n_cache_tokens"] is not None]

    if costs:
        print(f"  Total cost (USD):      ${sum(costs):.4f}")
        print(f"  Cost per trajectory:   min / median / mean / max")
        print(f"    ${min(costs):.4f} / ${safe_median(costs):.4f} / ${safe_mean(costs):.4f} / ${max(costs):.4f}")
    print()
    print(f"  Input tokens  (mean / median): {fmt(safe_mean(in_toks),0)} / {fmt(safe_median(in_toks),0)}")
    print(f"  Output tokens (mean / median): {fmt(safe_mean(out_toks),0)} / {fmt(safe_median(out_toks),0)}")
    print(f"  Cache tokens  (mean / median): {fmt(safe_mean(cache_toks),0)} / {fmt(safe_median(cache_toks),0)}")
    print()

    # ------------------------------------------------------------------ #
    # 4. Duration
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("TIMING")
    print("=" * 60)

    durations = [r["duration_sec"] for r in records if r["duration_sec"] is not None]
    if durations:
        print(f"  Wall-clock duration (seconds):  min / median / mean / max")
        print(f"    {min(durations):.0f} / {safe_median(durations):.0f} / {safe_mean(durations):.0f} / {max(durations):.0f}")
        print(f"  Total wall-clock time: {sum(durations)/3600:.2f} hours")
    print()

    # ------------------------------------------------------------------ #
    # 5. Action patterns
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("ACTION / COMMAND PATTERNS")
    print("=" * 60)

    total_actions: Counter = Counter()
    for r in records:
        for cat, cnt in r["actions"].items():
            total_actions[cat] += cnt

    grand_total = sum(total_actions.values())
    print(f"  Total commands across all trajectories: {grand_total}")
    print()
    print(f"  {'Category':<12}  {'Count':>6}  {'% of total':>10}  {'Mean/traj':>10}")
    print(f"  {'-'*12}  {'-'*6}  {'-'*10}  {'-'*10}")
    for cat, count in sorted(total_actions.items(), key=lambda x: -x[1]):
        pct = 100 * count / grand_total if grand_total else 0
        mean_per_traj = count / n
        print(f"  {cat:<12}  {count:>6}  {pct:>9.1f}%  {mean_per_traj:>10.1f}")
    print()

    print(f"  Per-trajectory action counts (mean / median / max):")
    total_acts_per_traj = [r["total_actions"] for r in records]
    print(f"    Total:       {fmt(safe_mean(total_acts_per_traj),1)} / {fmt(safe_median(total_acts_per_traj),1)} / {max(total_acts_per_traj)}")
    for cat in sorted(total_actions.keys(), key=lambda c: -total_actions[c]):
        vals = [r["actions"].get(cat, 0) for r in records]
        print(f"    {cat:<12}: {fmt(safe_mean(vals),1)} / {fmt(safe_median(vals),1)} / {max(vals)}")
    print()

    # ------------------------------------------------------------------ #
    # 6. File access stats
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("FILE ACCESS (unique file/dir paths per trajectory)")
    print("=" * 60)

    def file_stats_row(label: str, key: str) -> None:
        vals = [r[key] for r in records]
        print(f"  {label:<22}  mean={fmt(safe_mean(vals),1)}  median={fmt(safe_median(vals),1)}  max={max(vals)}")

    file_stats_row("Files read (cat/head/tail)", "n_files_read")
    file_stats_row("Files searched (grep/rg)",   "n_files_searched")
    file_stats_row("Files edited/written",        "n_files_edited")
    file_stats_row("Total unique files touched",  "n_files_touched")
    print()

    # Per-trajectory breakdown
    print(f"  {'Trial':<42}  {'Read':>5}  {'Grep':>5}  {'Edit':>5}  {'Total':>6}")
    print(f"  {'-'*42}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*6}")
    for r in records:
        print(
            f"  {r['trial_name']:<42}  {r['n_files_read']:>5}  "
            f"{r['n_files_searched']:>5}  {r['n_files_edited']:>5}  {r['n_files_touched']:>6}"
        )
    print()

    # ------------------------------------------------------------------ #
    # 7. Error rates
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("ERROR & OUTPUT STATS")
    print("=" * 60)

    n_err = [r["n_errors"] for r in records]
    n_empty = [r["n_empty_outputs"] for r in records]
    n_fmt = [r["n_format_errors"] for r in records]

    print(f"  Failed commands (non-zero returncode) per trajectory:")
    print(f"    mean / median / max: {fmt(safe_mean(n_err),1)} / {fmt(safe_median(n_err),1)} / {max(n_err)}")
    print(f"  Empty outputs per trajectory:")
    print(f"    mean / median / max: {fmt(safe_mean(n_empty),1)} / {fmt(safe_median(n_empty),1)} / {max(n_empty)}")
    print(f"  Format errors (multi-block turns) per trajectory:")
    print(f"    mean / median / max: {fmt(safe_mean(n_fmt),1)} / {fmt(safe_median(n_fmt),1)} / {max(n_fmt)}")
    print()

    # ------------------------------------------------------------------ #
    # 8. Elasticsearch root-error & test-run stats
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("ELASTICSEARCH / TEST-RUN STATS")
    print("=" * 60)

    n_hit_root   = sum(1 for r in records if r["hit_root_error"])
    n_bypassed   = sum(1 for r in records if r["bypassed_root"])
    n_tests_ok   = sum(1 for r in records if r["ran_tests_ok"])
    n_fuzz       = sum(1 for r in records if r["patch_fuzz_fallback"])

    # Trajectories where the agent hit the error but did NOT bypass
    n_stuck_root = sum(
        1 for r in records if r["hit_root_error"] and not r["bypassed_root"]
    )

    print(f"  Hit 'cannot run as root' error:  {n_hit_root} / {n} ({100*n_hit_root/n:.1f}%)")
    print(f"    Of those, applied useradd+su bypass: {n_bypassed} ({100*n_bypassed/n_hit_root:.1f}% of affected)"
          if n_hit_root else f"    Of those, applied useradd+su bypass: {n_bypassed}")
    print(f"    Of those, did NOT bypass (stuck):    {n_stuck_root}")
    print(f"  Ran tests with exit 0 (at least once): {n_tests_ok} / {n} ({100*n_tests_ok/n:.1f}%)")
    print()
    print(f"  Verifier patch fuzz fallback (test_patch applied with --fuzz=5):")
    print(f"    {n_fuzz} / {n} ({100*n_fuzz/n:.1f}%)")
    fuzz_trials = [r["trial_name"] for r in records if r["patch_fuzz_fallback"]]
    for t in fuzz_trials:
        print(f"    - {t}")
    print()

    print(f"  Per-trajectory breakdown:")
    print(f"  {'Trial':<42}  {'RootErr':>7}  {'Bypass':>6}  {'TestsOK':>7}  {'FuzzPatch':>9}")
    print(f"  {'-'*42}  {'-'*7}  {'-'*6}  {'-'*7}  {'-'*9}")
    for r in records:
        print(
            f"  {r['trial_name']:<42}  "
            f"{'yes' if r['hit_root_error'] else 'no':>7}  "
            f"{'yes' if r['bypassed_root'] else 'no':>6}  "
            f"{'yes' if r['ran_tests_ok'] else 'no':>7}  "
            f"{'yes' if r['patch_fuzz_fallback'] else 'no':>9}"
        )
    print()

    # ------------------------------------------------------------------ #
    # 9. Gold patch stats  (was 8)
    # ------------------------------------------------------------------ #
    matched = [r for r in records if r["task_name"] in gold_patches]
    if gold_patches:
        print("=" * 60)
        print("GOLD PATCH STATS (all patches in benchmark)")
        print("=" * 60)

        all_gold = list(gold_patches.values())
        gn_files  = [g["n_files"]       for g in all_gold]
        gadded    = [g["added"]          for g in all_gold]
        gremoved  = [g["removed"]        for g in all_gold]
        gchanged  = [g["changed_lines"]  for g in all_gold]
        ghunks    = [g["hunks"]          for g in all_gold]

        print(f"  Gold patches loaded:    {len(all_gold)}")
        print(f"  Of which overlap with trajectories: {len(matched)}")
        print()
        print(f"  {'Metric':<20}  {'mean':>7}  {'median':>7}  {'min':>5}  {'max':>5}")
        print(f"  {'-'*20}  {'-'*7}  {'-'*7}  {'-'*5}  {'-'*5}")
        for label, vals in [
            ("Files changed",  gn_files),
            ("Hunks",          ghunks),
            ("Lines added",    gadded),
            ("Lines removed",  gremoved),
            ("Lines changed",  gchanged),
        ]:
            print(
                f"  {label:<20}  {fmt(safe_mean(vals),1):>7}  {fmt(safe_median(vals),1):>7}"
                f"  {min(vals):>5}  {max(vals):>5}"
            )
        print()

    # ------------------------------------------------------------------ #
    # 10. Agent edits vs gold patch comparison (overlapping tasks only)
    # ------------------------------------------------------------------ #
    def print_agent_vs_gold(subset: list[dict], title: str) -> None:
        if not subset:
            print(f"  (no trajectories in this subset)\n")
            return

        hit_rates = []
        precision_rates = []
        exact_matches = 0

        print(f"  {'Trial':<42}  {'Gold':>5}  {'Agent':>5}  {'Hit':>5}  {'Prec':>5}  {'Overlap files'}")
        print(f"  {'-'*42}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*30}")

        for r in subset:
            gold = gold_patches[r["task_name"]]
            gold_files = gold["files"]
            agent_files = r["files_edited"]

            overlap = gold_files & agent_files
            hit  = len(overlap) / len(gold_files)  if gold_files  else 0.0
            prec = len(overlap) / len(agent_files) if agent_files else 0.0
            hit_rates.append(hit)
            precision_rates.append(prec)
            if gold_files and agent_files and gold_files == agent_files:
                exact_matches += 1

            overlap_names = ", ".join(Path(f).name for f in sorted(overlap)) or "-"
            print(
                f"  {r['trial_name']:<42}  {len(gold_files):>5}  {len(agent_files):>5}  "
                f"{hit:>4.0%}  {prec:>4.0%}  {overlap_names[:40]}"
            )

        print()
        n_m = len(subset)
        print(f"  Summary over {n_m} matched trajectories ({title}):")
        print(f"    Recall  (gold files the agent edited):   "
              f"mean={fmt(safe_mean(hit_rates),2)}  median={fmt(safe_median(hit_rates),2)}")
        print(f"    Precision (agent edits in gold set):     "
              f"mean={fmt(safe_mean(precision_rates),2)}  median={fmt(safe_median(precision_rates),2)}")
        print(f"    Exact file-set match:  {exact_matches}/{n_m}")
        print()

    if matched and gold_patches:
        print("=" * 60)
        print("AGENT EDITS vs GOLD PATCH (per overlapping trajectory)")
        print("=" * 60)
        print_agent_vs_gold(matched, "all")

        build_error_statuses = {"build_failed", "compile_error"}
        matched_build_errors = [
            r for r in matched if r["build_status"] in build_error_statuses
        ]
        print("=" * 60)
        print("AGENT EDITS vs GOLD PATCH (build_failed / compile_error only)")
        print("=" * 60)
        print_agent_vs_gold(matched_build_errors, "build/compile errors")

    # ------------------------------------------------------------------ #
    # 11. Per-trajectory table
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("PER-TRAJECTORY SUMMARY")
    print("=" * 60)

    print(f"  {'Trial':<42}  {'Steps':>5}  {'Cost$':>7}  {'Reward':>6}  {'Exit':<28}  {'Build':<14}")
    print(f"  {'-'*42}  {'-'*5}  {'-'*7}  {'-'*6}  {'-'*28}  {'-'*14}")
    for r in records:
        cost_str = f"${r['cost_usd']:.4f}" if r["cost_usd"] is not None else "    N/A"
        reward_str = f"{r['reward']:.2f}" if r["reward"] is not None else "   N/A"
        print(
            f"  {r['trial_name']:<42}  {r['n_steps']:>5}  {cost_str:>7}  "
            f"{reward_str:>6}  {r['exit_status']:<28}  {r['build_status']:<14}"
        )
    print()


if __name__ == "__main__":
    main()
