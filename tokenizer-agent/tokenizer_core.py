#!/usr/bin/env python3
"""Shared tokenization core, ported from ``tokenizer copy.py``.

This is the single source of truth for "how do we measure the size of a
benchmark instance's repository" — the walk/skip-list/chunking logic itself,
with no dependency on Harbor or on how the repo got onto local disk.
``tokenizer_agent.py`` (the Harbor agent, which downloads a repo out of a
container first) imports this module.
"""

from __future__ import annotations

import csv
import gzip
import os
from pathlib import Path
from typing import Any

import tiktoken

DEFAULT_ENCODING_NAME = os.environ.get("TIKTOKEN_ENCODING", "cl100k_base")

TOP_N_FILES = 50

# Directories to skip entirely (fast-path before os.walk descends).
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
    "venv",
    ".venv",
    "env",
    "build",
    "dist",
    ".gradle",
    ".idea",
    ".vscode",
}

# Extensions we deliberately don't tokenize. Includes true binaries
# (compiled artifacts, images, archives, media) as well as text formats
# whose content is structurally noisy and low-signal for repo-size
# estimation (e.g. .svg path data, .lock files).
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".jar", ".war", ".ear",
    ".so", ".dylib", ".dll", ".exe", ".o", ".a",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".db", ".sqlite", ".sqlite3",
    ".bin", ".dat", ".pkl", ".pickle", ".npy", ".npz",
    ".parquet", ".avro",
    ".DS_Store",
}

# Source code extensions — aggregated separately as a "signal" subset.
SOURCE_CODE_EXTENSIONS = {
    # Python
    ".py", ".pyx", ".pxd", ".pyi",
    # Java / JVM
    ".java", ".kt", ".kts", ".scala", ".groovy", ".gradle",
    # JavaScript / TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # C / C++
    ".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx",
    # C#
    ".cs", ".csx",
    # Go
    ".go",
    # Rust
    ".rs",
    # Ruby
    ".rb", ".rake",
    # PHP
    ".php",
    # Swift / Objective-C
    ".swift", ".m", ".mm",
    # Shell
    ".sh", ".bash", ".zsh",
    # Lua
    ".lua",
    # R
    ".r", ".R",
    # Perl
    ".pl", ".pm",
    # Elixir / Erlang
    ".ex", ".exs", ".erl",
    # Haskell
    ".hs",
    # Dart
    ".dart",
    # PowerShell
    ".ps1", ".psm1",
}

# Max chunk size (chars) fed to tiktoken in a single encode call.
# tiktoken's cl100k_base regex can stack-overflow during backtracking on
# pathological inputs (long single-line strings, dense regex/template text
# common in TS/JS test fixtures). Chunking sidesteps this.
_ENCODE_CHUNK_CHARS = 25_000


def should_skip_extension(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() in SKIP_EXTENSIONS


def try_read_text(path: str) -> str | None:
    """Return file text or None if the file appears binary."""
    try:
        with open(path, "r", encoding="utf-8", errors="strict") as f:
            return f.read()
    except (UnicodeDecodeError, ValueError):
        return None
    except OSError:
        return None


def _safe_encode_count(enc: tiktoken.Encoding, content: str) -> int:
    """Count tokens for `content`, chunking to avoid tiktoken regex backtracking errors."""
    if len(content) <= _ENCODE_CHUNK_CHARS:
        try:
            return len(enc.encode(content, disallowed_special=()))
        except ValueError:
            pass  # Fall through to chunked path

    total = 0
    n = len(content)
    i = 0
    while i < n:
        end = min(i + _ENCODE_CHUNK_CHARS, n)
        # Prefer to break on a newline to avoid splitting tokens unnecessarily
        if end < n:
            nl = content.rfind("\n", i, end)
            if nl > i:
                end = nl + 1
        chunk = content[i:end]
        try:
            total += len(enc.encode(chunk, disallowed_special=()))
        except ValueError:
            # Last-resort: shrink further. If even a tiny chunk fails,
            # fall back to a char-based approximation for that slice.
            sub_size = 4096
            j = 0
            while j < len(chunk):
                sub = chunk[j : j + sub_size]
                try:
                    total += len(enc.encode(sub, disallowed_special=()))
                except ValueError:
                    # Approximate: ~4 chars per token for unencodable slices.
                    total += max(1, len(sub) // 4)
                j += sub_size
        i = end
    return total


def count_lines(content: str) -> tuple[int, int]:
    """Return (lines, nonblank_lines) for decoded file text.

    A line is a ``\n``-terminated run of text; an unterminated last line
    still counts, so ``"a\nb"`` and ``"a\nb\n"`` are both 2 lines. Text is
    read with universal newlines, so ``\r\n`` and ``\r`` count as ``\n``.
    A line is non-blank if it has any non-whitespace character.
    """
    parts = content.split("\n")
    if parts[-1] == "":
        parts.pop()
    return len(parts), sum(1 for line in parts if line.strip())


def _file_bytes(path: str) -> int | None:
    """On-disk size of `path` (following symlinks), or None if it can't be stat'ed."""
    try:
        return os.stat(path).st_size
    except OSError:
        return None


def walk_and_count(
    repo_dir: Path,
    enc: tiktoken.Encoding,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Walk a local copy of the repo tree and return per-file counts.

    Every file under `repo_dir` (outside SKIP_DIRS) gets an entry in the
    returned list. Files we tokenize have ``tokenized=True`` plus tokens,
    chars, lines and bytes. Files we don't have ``tokenized=False``, a
    ``skip_reason`` (``"extension"``: in SKIP_EXTENSIONS; ``"binary"``: not
    valid UTF-8; ``"unreadable"``: e.g. a broken symlink) and only ``bytes``. ``by_extension`` only
    aggregates tokenized files, as before.
    """
    file_results: list[dict[str, Any]] = []
    by_extension: dict[str, dict[str, int]] = {}  # ext → {tokens, files, lines, ...}

    for root, dirs, files in os.walk(repo_dir):
        # Prune skipped directories in-place so os.walk won't descend
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, repo_dir)
            _, ext = os.path.splitext(fname)
            ext = ext.lower() if ext else "(no extension)"
            size = _file_bytes(fpath)

            if should_skip_extension(fpath):
                content = None
                skip_reason = "extension"
            else:
                content = try_read_text(fpath)
                if content is None:
                    skip_reason = "unreadable" if size is None else "binary"

            if content is None:
                file_results.append({
                    "path": rel_path, "ext": ext, "tokenized": False,
                    "skip_reason": skip_reason, "bytes": size,
                })
                continue

            tokens = _safe_encode_count(enc, content)
            lines, nonblank_lines = count_lines(content)

            file_results.append({
                "path": rel_path, "ext": ext, "tokenized": True,
                "tokens": tokens, "chars": len(content), "bytes": size,
                "lines": lines, "nonblank_lines": nonblank_lines,
            })

            entry = by_extension.setdefault(
                ext, {"tokens": 0, "files": 0, "lines": 0, "nonblank_lines": 0, "bytes": 0}
            )
            entry["tokens"] += tokens
            entry["files"] += 1
            entry["lines"] += lines
            entry["nonblank_lines"] += nonblank_lines
            entry["bytes"] += size or 0

    return file_results, by_extension


def build_token_result(
    instance_id: str,
    file_results: list[dict[str, Any]],
    by_extension: dict[str, dict[str, int]],
    encoding_name: str,
) -> dict[str, Any]:
    tokenized = [f for f in file_results if f["tokenized"]]
    skipped = [f for f in file_results if not f["tokenized"]]

    total_tokens = sum(f["tokens"] for f in tokenized)
    total_characters = sum(f["chars"] for f in tokenized)
    total_files = len(tokenized)
    total_lines = sum(f["lines"] for f in tokenized)
    total_nonblank_lines = sum(f["nonblank_lines"] for f in tokenized)
    total_bytes = sum(f["bytes"] or 0 for f in tokenized)

    sorted_ext = dict(
        sorted(by_extension.items(), key=lambda x: x[1]["tokens"], reverse=True)
    )

    top_files = [
        {"path": f["path"], "tokens": f["tokens"], "chars": f["chars"]}
        for f in sorted(tokenized, key=lambda x: x["tokens"], reverse=True)[:TOP_N_FILES]
    ]

    source = {"tokens": 0, "files": 0, "lines": 0, "nonblank_lines": 0, "bytes": 0}
    for ext, info in by_extension.items():
        if ext in SOURCE_CODE_EXTENSIONS:
            for key in source:
                source[key] += info[key]

    return {
        "instance_id": instance_id,
        "encoding": encoding_name,
        "total_tokens": total_tokens,
        "total_characters": total_characters,
        "total_files": total_files,
        "total_lines": total_lines,
        "total_nonblank_lines": total_nonblank_lines,
        "total_bytes": total_bytes,
        "source_code_tokens": source["tokens"],
        "source_code_files": source["files"],
        "source_code_lines": source["lines"],
        "source_code_nonblank_lines": source["nonblank_lines"],
        "source_code_bytes": source["bytes"],
        "skipped_files": len(skipped),
        "skipped_bytes": sum(f["bytes"] or 0 for f in skipped),
        "by_extension": sorted_ext,
        "top_files": top_files,
    }


# Column order of the per-file CSV written next to token_counts.json.
FILE_CSV_COLUMNS = [
    "path", "ext", "tokenized", "skip_reason",
    "tokens", "chars", "bytes", "lines", "nonblank_lines",
]


def write_files_csv(file_results: list[dict[str, Any]], out_path: Path) -> None:
    """Write one row per file (tokenized or not) as gzip-compressed CSV."""
    with gzip.open(out_path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FILE_CSV_COLUMNS, extrasaction="raise")
        writer.writeheader()
        for row in sorted(file_results, key=lambda r: r["path"]):
            writer.writerow({**row, "tokenized": int(row["tokenized"])})
