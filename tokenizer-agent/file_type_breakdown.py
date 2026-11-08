#!/usr/bin/env python3
"""Break a completed tokenizer job's token counts down by file type.

Reads the per-trial ``token_counts.json`` files that ``RepoTokenizerAgent``
already wrote (the same files ``benchmark_size_stats.py`` aggregates into
``results/<benchmark>.json``), groups each instance's ``by_extension`` counts
into file-type categories, and writes one JSON with:

- ``categories``: the extension -> category mapping used, so the grouping is
  auditable (anything unlisted falls into ``other``).
- ``metrics``: mean/median/stdev/min/max/sum across instances of tokens,
  files, and token share for each category.
- ``repos``: the same per-category numbers aggregated per repository (most
  benchmarks have several instances of one repo at different commits).
- ``instances``: per-instance category counts plus the raw ``by_extension``
  breakdown, for regrouping without re-running anything.

No re-tokenization happens here, so the totals are identical to the
published ``results/<benchmark>.json``; the script asserts that every
instance's categories sum back to its ``total_tokens``/``total_files`` and
that ``source_code`` matches ``source_code_tokens``/``source_code_files``.

Classification is by extension only, because that is all ``token_counts.json``
keeps per file (paths are only stored for the top 50 files). So it can't tell
a README from any other ``.md`` file, or test code from non-test code.

Repository names are parsed from the instance id (SWE-bench style
``owner__repo-123`` / SWE-bench Pro ``instance_owner__repo-<sha>...``). For
benchmarks whose ids don't encode the repo (DeepSWE), pass ``--task-defs`` with
a directory of downloaded Harbor task definitions; the repo is then read from
each ``<task>/task.toml``'s ``[metadata] repository_url``. To get them at the
exact refs a job ran against::

    python -c "import json,glob; [print(f\"{t['org']}/{t['name']}@{t['ref']}\") \\
        for t in (json.load(open(f))['task_id'] for f in glob.glob('jobs/<job>/*/result.json'))]" \\
      | xargs -I{} harbor task download {} -o <task_defs_dir>

Usage:
    python file_type_breakdown.py <job_dir> -o results/file_types/<benchmark>.json
        [--task-defs DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import tomllib
from pathlib import Path
from typing import Any

from benchmark_size_stats import _find_token_counts_files
from tokenizer_core import SOURCE_CODE_EXTENSIONS

SCRIPT_DIR = Path(__file__).resolve().parent

NO_EXTENSION = "(no extension)"

# Extension -> category. ``source_code`` is exactly the paper's
# ``source_code_tokens`` definition (``SOURCE_CODE_EXTENSIONS``); the rest are
# everything else, grouped. Unlisted extensions land in ``other``.
CATEGORIES: dict[str, set[str]] = {
    "source_code": set(SOURCE_CODE_EXTENSIONS),
    # Programming, markup, style, template and query languages that are not
    # part of the paper's source-code definition.
    "other_code": {
        ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less", ".pcss",
        ".styl", ".vue", ".svelte", ".astro", ".sql", ".proto", ".graphql",
        ".ipynb", ".mts", ".cts", ".coffee", ".zig", ".jl", ".clj", ".cljc",
        ".el", ".vim", ".elm", ".gleam", ".fs", ".vb", ".vbs", ".vala",
        ".tcl", ".awk", ".m4", ".fish", ".nu", ".bat", ".cmd", ".psd1",
        ".cmake", ".mk", ".mak", ".bzl", ".star", ".nix", ".tf", ".hcl",
        ".bicep", ".rego", ".cue", ".jsonnet", ".libsonnet", ".jq",
        ".wat", ".wast", ".asm", ".s", ".ll", ".mlir", ".cu", ".metal",
        ".hlsl", ".shader", ".y", ".l", ".g4", ".lalrpop", ".pest", ".ne",
        ".ohm", ".gbnf", ".mustache", ".hbs", ".handlebars", ".ejs", ".pug",
        ".haml", ".j2", ".jinja", ".jinja2", ".tmpl", ".tpl", ".mako",
        ".jsp", ".cshtml", ".templ", ".xsl", ".xslt", ".ipy", ".pxi",
        ".painless", ".esql", ".cypher", ".gremlin", ".promql", ".cairo",
        ".circom", ".tact", ".rkt", ".scm", ".teal", ".luau", ".wren",
        ".imba", ".chpl", ".stan", ".qasm", ".slang", ".slint", ".typ",
    },
    # Human-written prose / documentation formats.
    "docs": {
        ".md", ".mdx", ".markdown", ".mkd", ".rst", ".adoc", ".asciidoc",
        ".tex", ".org", ".textile", ".rtf", ".ronn", ".bib", ".readme",
        ".1",  # man pages
    },
    # Configuration, build and dependency-manifest files.
    "config_build": {
        ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".config",
        ".properties", ".env", ".jsonc", ".json5", ".xml", ".xsd", ".dtd",
        ".lock", ".sum", ".mod", ".work", ".plist", ".pbxproj", ".xcscheme",
        ".xcworkspacedata", ".nuspec", ".webmanifest", ".code-workspace",
        ".dockerfile", ".service", ".socket", ".timer", ".desktop", ".prefs",
        ".tfvars", ".in", ".am", ".ac", ".editorconfig", ".gitignore",
        ".gitattributes", ".npmrc", ".nvmrc", ".babelrc", ".eslintrc",
        ".prettierrc", ".flake8", ".pylintrc", ".coveragerc", ".def",
        ".entitlements", ".manifest", ".mf", ".pc", ".spec",
    },
    # Translation catalogs.
    "localization": {".po", ".pot", ".lcl", ".strings", ".xlf", ".resx"},
    # Data, test fixtures/baselines, generated artifacts, certificates.
    # Plain ``.txt`` lives here: in these repos it is overwhelmingly data
    # (perf fixtures, word lists, egg-info SOURCES.txt), not prose.
    "data_fixtures": {
        ".txt", ".json", ".jsonl", ".ndjson", ".geojson", ".csv", ".tsv",
        ".dsv", ".ecsv", ".snap", ".ambr", ".golden", ".baseline", ".types",
        ".symbols", ".map", ".tsbuildinfo", ".tiktoken", ".dict", ".replay",
        ".pg_dump", ".out", ".stdout", ".stderr", ".expected", ".log",
        ".patch", ".diff", ".csv-spec", ".sql-spec", ".eps", ".ps", ".afm",
        ".pem", ".crt", ".cer", ".csr", ".key", ".pub", ".asc", ".gpg",
        ".hdr", ".fits", ".xyz", ".ics", ".eml", ".har", ".sarif",
        ".62-now", ".1962-now",  # astropy leap-second/IERS tables
    },
    # Extensionless files: LICENSE, Makefile, Dockerfile, CHANGES, fixtures...
    # Kept separate since their type can't be told from the extension.
    "no_extension": {NO_EXTENSION},
}
CATEGORY_NAMES = (*CATEGORIES, "other")

_EXT_TO_CATEGORY = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts}
_overlap = sum(len(e) for e in CATEGORIES.values()) - len(_EXT_TO_CATEGORY)
assert _overlap == 0, "an extension is listed under more than one category"

_PRO_ID = re.compile(r"^instance_(?P<owner>.+?)__(?P<repo>.+?)-[0-9a-f]{40}")
_SWEBENCH_ID = re.compile(r"^(?P<owner>.+?)__(?P<repo>.+)-\d+$")


def categorize(ext: str) -> str:
    return _EXT_TO_CATEGORY.get(ext, "other")


def _load_task_repos(task_defs: Path | None) -> dict[str, str]:
    """Map task name -> ``owner/repo`` from downloaded Harbor task.toml files."""
    repos: dict[str, str] = {}
    if task_defs is None:
        return repos
    for toml_path in task_defs.glob("*/task.toml"):
        with open(toml_path, "rb") as f:
            meta = tomllib.load(f).get("metadata", {})
        url = meta.get("repository_url")
        if url:
            name = meta.get("task_id", toml_path.parent.name)
            repos[name] = url.removeprefix("https://github.com/").removesuffix(".git")
    return repos


def resolve_repo(instance_id: str, task_repos: dict[str, str]) -> str:
    if instance_id in task_repos:
        return task_repos[instance_id]
    for pattern in (_PRO_ID, _SWEBENCH_ID):
        m = pattern.match(instance_id)
        if m:
            return f"{m['owner']}/{m['repo']}"
    raise SystemExit(
        f"Can't determine the repository for {instance_id!r}; pass --task-defs "
        "with the job's downloaded Harbor task definitions."
    )


def _instance_breakdown(data: dict[str, Any], repo: str) -> dict[str, Any]:
    by_category = {cat: {"tokens": 0, "files": 0} for cat in CATEGORY_NAMES}
    for ext, info in data["by_extension"].items():
        entry = by_category[categorize(ext)]
        entry["tokens"] += info["tokens"]
        entry["files"] += info["files"]

    total_tokens = data["total_tokens"]
    instance_id = data["instance_id"]
    # Sanity checks: categories partition the published totals exactly.
    assert sum(c["tokens"] for c in by_category.values()) == total_tokens, instance_id
    assert sum(c["files"] for c in by_category.values()) == data["total_files"], instance_id
    assert by_category["source_code"]["tokens"] == data["source_code_tokens"], instance_id
    assert by_category["source_code"]["files"] == data["source_code_files"], instance_id

    for entry in by_category.values():
        entry["token_share"] = entry["tokens"] / total_tokens if total_tokens else 0.0

    return {
        "instance_id": instance_id,
        "repo": repo,
        "total_tokens": total_tokens,
        "total_files": data["total_files"],
        "by_category": by_category,
        "by_extension": data["by_extension"],
    }


def _compute_stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
        "sum": sum(values),
    }


def _category_metrics(instances: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-category tokens/files/token_share stats across ``instances``.

    ``pooled_token_share`` is the category's share of all tokens summed over
    the instances (size-weighted); ``token_share`` stats are over per-instance
    shares (each instance weighted equally).
    """
    grand_total = sum(inst["total_tokens"] for inst in instances)
    metrics: dict[str, Any] = {
        "total_tokens": _compute_stats([inst["total_tokens"] for inst in instances]),
        "total_files": _compute_stats([inst["total_files"] for inst in instances]),
    }
    for cat in CATEGORY_NAMES:
        cats = [inst["by_category"][cat] for inst in instances]
        tokens_sum = sum(c["tokens"] for c in cats)
        metrics[cat] = {
            "tokens": _compute_stats([c["tokens"] for c in cats]),
            "files": _compute_stats([c["files"] for c in cats]),
            "token_share": _compute_stats([c["token_share"] for c in cats]),
            "pooled_token_share": tokens_sum / grand_total if grand_total else 0.0,
        }
    return metrics


def build_breakdown(job_dir: Path, task_repos: dict[str, str]) -> dict[str, Any]:
    instances: list[dict[str, Any]] = []
    for path in _find_token_counts_files(job_dir):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        instances.append(
            _instance_breakdown(data, resolve_repo(data["instance_id"], task_repos))
        )
    if not instances:
        raise SystemExit(f"No token_counts.json files found under {job_dir}.")

    instances.sort(key=lambda inst: inst["total_tokens"], reverse=True)

    by_repo: dict[str, list[dict[str, Any]]] = {}
    for inst in instances:
        by_repo.setdefault(inst["repo"], []).append(inst)
    repos = [
        {
            "repo": repo,
            "n_instances": len(repo_instances),
            "metrics": _category_metrics(repo_instances),
        }
        for repo, repo_instances in by_repo.items()
    ]
    repos.sort(key=lambda r: r["metrics"]["total_tokens"]["mean"], reverse=True)

    return {
        "job_dir": os.path.relpath(job_dir, SCRIPT_DIR),
        "n_instances": len(instances),
        "n_repos": len(repos),
        "categories": {cat: sorted(exts) for cat, exts in CATEGORIES.items()}
        | {"other": "any extension not listed above"},
        "metrics": _category_metrics(instances),
        "repos": repos,
        "instances": instances,
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"n_instances = {summary['n_instances']}, n_repos = {summary['n_repos']}")
    print(f"{'category':<15} {'pooled share':>12} {'mean tokens':>14} {'median tokens':>14}")
    for cat in CATEGORY_NAMES:
        m = summary["metrics"][cat]
        print(
            f"{cat:<15} {m['pooled_token_share']:>12.1%} "
            f"{m['tokens']['mean']:>14,.0f} {m['tokens']['median']:>14,.0f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Break RepoTokenizerAgent results down by file type."
    )
    parser.add_argument("job_dir", type=Path, help="Path to a Harbor job directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Where to write the JSON (default: <job_dir>/file_type_breakdown.json)",
    )
    parser.add_argument(
        "--task-defs",
        type=Path,
        default=None,
        help="Directory of downloaded Harbor task definitions (<task>/task.toml), "
        "used to look up repos for instance ids that don't encode one",
    )
    args = parser.parse_args()

    job_dir = args.job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        raise SystemExit(f"Job directory not found: {job_dir}")

    summary = build_breakdown(job_dir, _load_task_repos(args.task_defs))

    output_path = args.output or (job_dir / "file_type_breakdown.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    _print_summary(summary)
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
