"""Classify bash commands as Read, Write, Explore, or Other and extract file paths."""
from __future__ import annotations

import re
import shlex
from traj.models import Operation


# Patterns: (regex_for_command, action, path_extraction_hint)
# Order matters — first match wins for each segment of a piped command.
# The below lists contain commands that are allways READ/WRITE/EXPLORE regardless of flags. More complex commands like grep/rg and git are handled separately.
READ_COMMANDS = [
    "cat", "head", "tail", "less", "more", "batcat", "bat",
]

WRITE_COMMANDS = [
    "patch", "install",
]

EXPLORE_COMMANDS = [
    "find", "ls", "tree", "wc", "du", "file", "stat", "realpath", "which",
]


def classify_bash(command: str, step: int, sub_agent: bool = False,
                  sub_agent_name: str | None = None) -> list[Operation]:
    """Classify a bash command string and return normalised Operations.

    A single bash command can produce multiple operations (e.g. rg both
    explores and reads). Piped commands are split and each segment is
    classified independently.
    """
    # Strip common bash wrappers
    cmd = command.strip()
    for prefix in ["/bin/bash -lc ", "/bin/bash -c ", "bash -lc ", "bash -c "]:
        if cmd.startswith(prefix):
            # Remove the prefix and unwrap outer quotes
            inner = cmd[len(prefix):]
            if (inner.startswith("'") and inner.endswith("'")) or \
               (inner.startswith('"') and inner.endswith('"')):
                inner = inner[1:-1]
            cmd = inner
            break

    # Split on && to handle chained commands
    segments = _split_chains(cmd)
    ops: list[Operation] = []
    for seg in segments:
        ops.extend(_classify_segment(seg.strip(), step, sub_agent, sub_agent_name))
    return ops if ops else [_make_op("Other", "", command, "bash", step, sub_agent, sub_agent_name)]


def _split_chains(cmd: str) -> list[str]:
    """Split on && and ; but not inside quotes."""
    segments = []
    current: list[str] = []
    in_quote = None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if c in ('"', "'") and in_quote is None:
            in_quote = c
        elif c == in_quote:
            in_quote = None
        elif in_quote is None:
            if c == '&' and i + 1 < len(cmd) and cmd[i + 1] == '&':
                segments.append("".join(current))
                current = []
                i += 2
                continue
            if c == ';':
                segments.append("".join(current))
                current = []
                i += 1
                continue
        current.append(c)
        i += 1
    if current:
        segments.append("".join(current))
    return [s for s in segments if s.strip()]


def _classify_segment(seg: str, step: int, sub_agent: bool,
                      sub_agent_name: str | None) -> list[Operation]:
    """Classify a single command segment (may still contain pipes)."""
    # Take the first command in a pipe chain as the primary
    pipe_parts = _split_pipes(seg)
    primary = pipe_parts[0].strip() if pipe_parts else seg.strip()
    base_cmd = _get_base_command(primary)

    ops: list[Operation] = []

    # --- grep / ripgrep ---
    if base_cmd in ("grep", "egrep", "fgrep", "rg"):
        actions = _classify_grep(primary, base_cmd)
        for action, path in actions:
            ops.append(_make_op(action, path, seg, base_cmd, step, sub_agent, sub_agent_name))
        return ops

    # --- sed ---
    if base_cmd == "sed":
        if "-i" in primary or "--in-place" in primary:
            path = _extract_last_path(primary)
            return [_make_op("Write", path, seg, "sed", step, sub_agent, sub_agent_name)]
        elif "-n" in primary:
            path = _extract_last_path(primary)
            return [_make_op("Read", path, seg, "sed", step, sub_agent, sub_agent_name)]
        path = _extract_last_path(primary)
        return [_make_op("Read", path, seg, "sed", step, sub_agent, sub_agent_name)]

    # --- simple read commands ---
    if base_cmd in READ_COMMANDS:
        path = _extract_last_path(primary)
        return [_make_op("Read", path, seg, base_cmd, step, sub_agent, sub_agent_name)]

    # --- simple write commands ---
    if base_cmd in WRITE_COMMANDS:
        path = _extract_last_path(primary)
        return [_make_op("Write", path, seg, base_cmd, step, sub_agent, sub_agent_name)]

    # --- explore commands ---
    if base_cmd in EXPLORE_COMMANDS:
        path = _extract_path_for_explore(primary, base_cmd)
        return [_make_op("Explore", path, seg, base_cmd, step, sub_agent, sub_agent_name)]

    # --- redirections (echo/printf > file) ---
    if ">" in seg:
        redir_path = _extract_redirect_target(seg)
        if redir_path:
            return [_make_op("Write", redir_path, seg, base_cmd, step, sub_agent, sub_agent_name)]

    # --- cp / mv / mkdir / touch ---
    if base_cmd in ("cp", "mv"):
        path = _extract_last_path(primary)
        return [_make_op("Write", path, seg, base_cmd, step, sub_agent, sub_agent_name)]
    if base_cmd in ("mkdir", "touch", "rm", "rmdir"):
        path = _extract_last_path(primary)
        return [_make_op("Write", path, seg, base_cmd, step, sub_agent, sub_agent_name)]
    if base_cmd == "tee":
        path = _extract_last_path(primary)
        return [_make_op("Write", path, seg, base_cmd, step, sub_agent, sub_agent_name)]

    # --- git ---
    if base_cmd == "git":
        return _classify_git(primary, seg, step, sub_agent, sub_agent_name)

    # --- cd / pwd / echo (informational) ---
    if base_cmd in ("cd", "pwd", "echo", "printf", "export", "source", ".", "true", "false"):
        return []  # skip — not file operations

    return []


def _classify_grep(cmd: str, base_cmd: str) -> list[tuple[str, str]]:
    """Classify grep/rg and return (action, path) pairs."""
    results: list[tuple[str, str]] = []

    # --files flag means pure file listing (Explore only)
    if "--files" in cmd:
        path = _extract_path_for_explore(cmd, base_cmd)
        return [("Explore", path)]

    # -l / --files-with-matches means Explore only
    if re.search(r'\s-[a-zA-Z]*l', cmd) or "--files-with-matches" in cmd:
        path = _extract_path_for_explore(cmd, base_cmd)
        return [("Explore", path)]

    # -c / --count means Explore only
    if re.search(r'\s-[a-zA-Z]*c\b', cmd) or "--count" in cmd:
        path = _extract_path_for_explore(cmd, base_cmd)
        return [("Explore", path)]

    # Default: grep shows content (Explore + Read)
    path = _extract_path_for_explore(cmd, base_cmd)
    results.append(("Explore", path))
    results.append(("Read", path))
    return results


def _classify_git(cmd: str, full_seg: str, step: int, sub_agent: bool,
                  sub_agent_name: str | None) -> list[Operation]:
    """Classify git subcommands."""
    parts = cmd.split()
    if len(parts) < 2:
        return []
    subcmd = parts[1] if parts[1] != "--no-pager" else (parts[2] if len(parts) > 2 else "")

    if subcmd in ("diff", "log", "show", "blame", "status"):
        return [_make_op("Read", "", full_seg, f"git {subcmd}", step, sub_agent, sub_agent_name)]
    if subcmd in ("add", "commit", "checkout", "apply", "stash"):
        path = _extract_last_path(cmd)
        return [_make_op("Write", path, full_seg, f"git {subcmd}", step, sub_agent, sub_agent_name)]
    if subcmd in ("ls-files", "branch", "tag"):
        return [_make_op("Explore", "", full_seg, f"git {subcmd}", step, sub_agent, sub_agent_name)]
    return []


def _get_base_command(cmd: str) -> str:
    """Extract the base command name from a command string."""
    cmd = cmd.lstrip()
    # Skip env vars like FOO=bar
    while re.match(r'^[A-Za-z_][A-Za-z_0-9]*=\S*\s', cmd):
        cmd = re.sub(r'^[A-Za-z_][A-Za-z_0-9]*=\S*\s+', '', cmd)
    parts = cmd.split()
    if not parts:
        return ""
    return parts[0].split("/")[-1]  # handle /usr/bin/cat -> cat


def _split_pipes(cmd: str) -> list[str]:
    """Split a command on pipe characters, respecting quotes."""
    parts = []
    current: list[str] = []
    in_quote = None
    for c in cmd:
        if c in ('"', "'") and in_quote is None:
            in_quote = c
        elif c == in_quote:
            in_quote = None
        elif c == '|' and in_quote is None:
            parts.append("".join(current))
            current = []
            continue
        current.append(c)
    if current:
        parts.append("".join(current))
    return parts


def _extract_last_path(cmd: str) -> str:
    """Extract the last path-like argument from a command."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    # Walk backwards, skip flags
    for token in reversed(tokens):
        if token.startswith("-"):
            continue
        if "/" in token or "." in token:
            return token
    return ""


def _extract_path_for_explore(cmd: str, base_cmd: str) -> str:
    """Extract path argument for explore commands."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    # For find, the path is usually the first non-flag argument after 'find'
    if base_cmd == "find":
        found_cmd = False
        for t in tokens:
            if t == "find":
                found_cmd = True
                continue
            if found_cmd and not t.startswith("-"):
                return t
        return ""

    # For ls/tree, similar
    if base_cmd in ("ls", "tree"):
        for t in tokens[1:]:
            if not t.startswith("-"):
                return t
        return "."

    # For grep/rg, try to find a path-like arg that isn't the pattern
    return _extract_last_path(cmd)


def _extract_redirect_target(cmd: str) -> str:
    """Extract the target path from a redirect (> or >>)."""
    match = re.search(r'>{1,2}\s*(\S+)', cmd)
    if match:
        target = match.group(1)
        if target and not target.startswith("&"):
            return target
    return ""


def _make_op(action: str, path: str, detail: str, tool: str, step: int,
             sub_agent: bool, sub_agent_name: str | None) -> Operation:
    return Operation(
        step=step,
        action=action,
        path=path,
        tool=tool,
        detail=f"bash: {detail.strip()[:200]}",
        sub_agent=sub_agent,
        sub_agent_name=sub_agent_name,
    )
