#!/usr/bin/env python3
"""Shared tokenization core, ported from ``tokenizer copy.py``.

This is the single source of truth for "how do we measure the size of a
benchmark instance's repository" — the walk/skip-list/chunking logic itself,
with no dependency on Harbor or on how the repo got onto local disk.
``tokenizer_agent.py`` (the Harbor agent, which downloads a repo out of a
container first) imports this module.
"""

from __future__ import annotations

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


def walk_and_count(
    repo_dir: Path,
    enc: tiktoken.Encoding,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Walk a local copy of the repo tree and return per-file token counts."""
    file_results: list[dict[str, Any]] = []
    by_extension: dict[str, dict[str, int]] = {}  # ext → {tokens, files}

    for root, dirs, files in os.walk(repo_dir):
        # Prune skipped directories in-place so os.walk won't descend
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            fpath = os.path.join(root, fname)

            if should_skip_extension(fpath):
                continue

            content = try_read_text(fpath)
            if content is None:
                continue

            tokens = _safe_encode_count(enc, content)
            rel_path = os.path.relpath(fpath, repo_dir)
            _, ext = os.path.splitext(fname)
            ext = ext.lower() if ext else "(no extension)"

            file_results.append({"path": rel_path, "tokens": tokens, "chars": len(content)})

            entry = by_extension.setdefault(ext, {"tokens": 0, "files": 0})
            entry["tokens"] += tokens
            entry["files"] += 1

    return file_results, by_extension


def build_token_result(
    instance_id: str,
    file_results: list[dict[str, Any]],
    by_extension: dict[str, dict[str, int]],
    encoding_name: str,
) -> dict[str, Any]:
    total_tokens = sum(f["tokens"] for f in file_results)
    total_characters = sum(f.get("chars", 0) for f in file_results)
    total_files = len(file_results)

    sorted_ext = dict(
        sorted(by_extension.items(), key=lambda x: x[1]["tokens"], reverse=True)
    )

    top_files = sorted(file_results, key=lambda x: x["tokens"], reverse=True)[
        :TOP_N_FILES
    ]

    source_code_tokens = 0
    source_code_files = 0
    for ext, info in by_extension.items():
        if ext in SOURCE_CODE_EXTENSIONS:
            source_code_tokens += info["tokens"]
            source_code_files += info["files"]

    return {
        "instance_id": instance_id,
        "encoding": encoding_name,
        "total_tokens": total_tokens,
        "total_characters": total_characters,
        "total_files": total_files,
        "source_code_tokens": source_code_tokens,
        "source_code_files": source_code_files,
        "by_extension": sorted_ext,
        "top_files": top_files,
    }
