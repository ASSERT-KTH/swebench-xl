#!/usr/bin/env python3
"""Write the file-type report (README + CSVs) from ``results/file_types/*.json``.

``file_type_breakdown.py`` writes one JSON per benchmark. This script reads
those and writes, next to them:

- ``README.md``: the report — provenance, category definitions with every
  extension each one covers, and per-benchmark tables.
- ``benchmark_summary.csv``: one row per (benchmark, category).
- ``benchmark_share_wide.csv``: one row per benchmark, one column per
  category's pooled token share (handy for stacked bar charts).
- ``repo_summary.csv``: one row per (benchmark, repo, category).
- ``instances.csv``: one row per instance, ``<category>_tokens`` /
  ``<category>_files`` columns.
- ``extension_categories.csv``: every extension -> category mapping used.

Usage:
    python file_type_report.py [--dir results/file_types]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from file_type_breakdown import CATEGORIES, CATEGORY_NAMES

SCRIPT_DIR = Path(__file__).resolve().parent

# file stem -> display name, in report order.
BENCHMARKS: dict[str, str] = {
    "verified": "SWE-bench Verified",
    "pro": "SWE-bench Pro",
    "xl": "SWE-bench XL",
    "xl_subset": "SWE-bench XL (subset)",
    "deepswe": "DeepSWE (DataCurve)",
}

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "source_code": "The paper's existing source-code definition (`SOURCE_CODE_EXTENSIONS` "
    "in `tokenizer_core.py`), unchanged, so it sums exactly to the published "
    "`source_code_tokens`.",
    "other_code": "Code-like files outside the paper's definition: markup, "
    "stylesheets, templates, query/schema languages, notebooks, build scripts, "
    "assembly/WebAssembly text.",
    "docs": "Human-written prose and documentation formats.",
    "config_build": "Configuration, build and dependency-manifest files, "
    "including lock files.",
    "localization": "Translation catalogs.",
    "data_fixtures": "Data, test fixtures and expected-output baselines, generated "
    "or build output, certificates/keys. `.json` and `.txt` are here because "
    "their largest files in these repos are fixtures, vocab files and word "
    "lists, not configuration or prose.",
    "no_extension": "Files without an extension (`LICENSE`, `Makefile`, "
    "`Dockerfile`, `CHANGES`, extensionless fixtures). Their type can't be "
    "determined from the extension.",
    "other": "Every extension not listed in another category (the long tail).",
}

STAT_KEYS = ("mean", "median", "stdev", "min", "max", "sum")


def _extensions(cat: str) -> list[str]:
    # tokenizer_core lowercases extensions before matching, so ``.R`` and
    # ``.r`` are the same entry; list each once.
    return sorted({ext.lower() for ext in CATEGORIES[cat]})


def _load(results_dir: Path) -> dict[str, dict[str, Any]]:
    data = {}
    for stem in BENCHMARKS:
        path = results_dir / f"{stem}.json"
        if not path.is_file():
            raise SystemExit(f"Missing {path}; run file_type_breakdown.py first.")
        with open(path, encoding="utf-8") as f:
            data[stem] = json.load(f)
    return data


def _category_row(metrics: dict[str, Any], cat: str) -> dict[str, Any]:
    m = metrics[cat]
    row: dict[str, Any] = {}
    for key in STAT_KEYS:
        row[f"tokens_{key}"] = m["tokens"][key]
    for key in STAT_KEYS:
        row[f"files_{key}"] = m["files"][key]
    row["pooled_token_share"] = m["pooled_token_share"]
    row["mean_token_share"] = m["token_share"]["mean"]
    row["median_token_share"] = m["token_share"]["median"]
    return row


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_csvs(data: dict[str, dict[str, Any]], out_dir: Path) -> None:
    summary, share_wide, repos, instances = [], [], [], []
    for stem, d in data.items():
        for cat in CATEGORY_NAMES:
            summary.append(
                {"benchmark": stem, "category": cat, "n_instances": d["n_instances"]}
                | _category_row(d["metrics"], cat)
            )
        share_wide.append(
            {"benchmark": stem}
            | {cat: d["metrics"][cat]["pooled_token_share"] for cat in CATEGORY_NAMES}
        )
        for r in d["repos"]:
            for cat in CATEGORY_NAMES:
                repos.append(
                    {
                        "benchmark": stem,
                        "repo": r["repo"],
                        "n_instances": r["n_instances"],
                        "category": cat,
                    }
                    | _category_row(r["metrics"], cat)
                )
        for inst in d["instances"]:
            row = {
                "benchmark": stem,
                "instance_id": inst["instance_id"],
                "repo": inst["repo"],
                "total_tokens": inst["total_tokens"],
                "total_files": inst["total_files"],
            }
            for cat in CATEGORY_NAMES:
                row[f"{cat}_tokens"] = inst["by_category"][cat]["tokens"]
                row[f"{cat}_files"] = inst["by_category"][cat]["files"]
            instances.append(row)

    _write_csv(out_dir / "benchmark_summary.csv", summary)
    _write_csv(out_dir / "benchmark_share_wide.csv", share_wide)
    _write_csv(out_dir / "repo_summary.csv", repos)
    _write_csv(out_dir / "instances.csv", instances)
    _write_csv(
        out_dir / "extension_categories.csv",
        [
            {"extension": ext, "category": cat}
            for cat in CATEGORIES
            for ext in _extensions(cat)
        ],
    )


def _n(x: float) -> str:
    return f"{x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:.1%}"


def _category_section() -> str:
    lines = [
        "| Category | What it contains |",
        "| --- | --- |",
    ]
    for cat in CATEGORY_NAMES:
        lines.append(f"| `{cat}` | {CATEGORY_DESCRIPTIONS[cat]} |")
    lines += ["", "### Extensions per category", ""]
    lines.append(
        "Extensions are matched case-insensitively against the file's last "
        "extension (`foo.test.ts` -> `.ts`). The same mapping is in "
        "`extension_categories.csv`."
    )
    lines.append("")
    for cat in CATEGORIES:
        exts = _extensions(cat)
        listed = " ".join(f"`{e}`" for e in exts)
        lines.append(f"**`{cat}`** ({len(exts)}): {listed}")
        lines.append("")
    lines.append(
        "**`other`**: anything not listed above. The largest contributors are "
        "listed under each benchmark's table below."
    )
    return "\n".join(lines)


def _other_top(d: dict[str, Any], n: int = 5) -> str:
    known = {e for exts in CATEGORIES.values() for e in exts}
    totals: dict[str, int] = {}
    for inst in d["instances"]:
        for ext, info in inst["by_extension"].items():
            if ext not in known:
                totals[ext] = totals.get(ext, 0) + info["tokens"]
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return ", ".join(f"`{e}` ({_n(t)})" for e, t in top)


def _benchmark_section(stem: str, d: dict[str, Any]) -> str:
    m = d["metrics"]
    lines = [
        f"### {BENCHMARKS[stem]}",
        "",
        f"{d['n_instances']} instances, {d['n_repos']} repositories.",
        "",
        "| Category | Mean tokens | Median tokens | Total tokens | Share | Mean files |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cat in CATEGORY_NAMES:
        c = m[cat]
        lines.append(
            f"| `{cat}` | {_n(c['tokens']['mean'])} | {_n(c['tokens']['median'])} | "
            f"{_n(c['tokens']['sum'])} | {_pct(c['pooled_token_share'])} | "
            f"{_n(c['files']['mean'])} |"
        )
    lines.append(
        f"| **total** | **{_n(m['total_tokens']['mean'])}** | "
        f"**{_n(m['total_tokens']['median'])}** | **{_n(m['total_tokens']['sum'])}** | "
        f"**100%** | **{_n(m['total_files']['mean'])}** |"
    )
    lines += ["", f"Largest `other` extensions (total tokens): {_other_top(d)}.", ""]
    return "\n".join(lines)


def _overview(data: dict[str, dict[str, Any]]) -> str:
    header = "| Benchmark | " + " | ".join(f"`{c}`" for c in CATEGORY_NAMES) + " |"
    sep = "| --- |" + " ---: |" * len(CATEGORY_NAMES)
    rows = [
        f"| {BENCHMARKS[stem]} | "
        + " | ".join(_pct(d["metrics"][c]["pooled_token_share"]) for c in CATEGORY_NAMES)
        + " |"
        for stem, d in data.items()
    ]
    return "\n".join([header, sep, *rows])


def write_readme(data: dict[str, dict[str, Any]], out_dir: Path) -> None:
    provenance = "\n".join(
        f"| {BENCHMARKS[stem]} | `{stem}.json` | `tokenizer-agent/{d['job_dir']}` | "
        f"{d['n_instances']} |"
        for stem, d in data.items()
    )
    benchmark_sections = "\n".join(
        _benchmark_section(stem, d) for stem, d in data.items()
    )
    cats = ", ".join(f"`{c}`" for c in CATEGORY_NAMES)

    readme = f"""# Token counts per file type

Breakdown of each benchmark's repository size (in `cl100k_base` tokens) by
file type: source code, other code, docs, config/build, localization,
data/fixtures, files without an extension, and other.

This file and the CSVs next to it are generated by `file_type_report.py` from
`results/file_types/*.json`. Don't edit them by hand; see
[Regenerating](#regenerating).

## Provenance

The numbers come from the same tokenizer runs as the published
`results/<benchmark>.json` files. Nothing was re-tokenized: each instance's
per-extension counts (`by_extension` in its `token_counts.json`) were grouped
into categories. The totals are therefore identical to the published ones.
`file_type_breakdown.py` checks, for every instance, that the categories sum
to `total_tokens` and `total_files`, and that `source_code` equals the
published `source_code_tokens` and `source_code_files`.

| Benchmark | JSON | Raw run data | Instances |
| --- | --- | --- | ---: |
{provenance}

SWE-bench XL (subset) is the {data['xl_subset']['n_instances']} XL instances listed in
`tokenizer-agent/results/xl_subset_instances.txt`, taken from the same XL run.

Repositories are parsed from the instance ids. DeepSWE ids don't contain the
repository, so it was read from `repository_url` in each task's `task.toml`.

## Categories

The categories are defined by file extension alone: each file is assigned to
a category based only on its extension, as listed below. File names and
directory locations are not considered.

{_category_section()}

## Results

**Share** is the category's part of all tokens in the benchmark (sum over
instances of the category / sum of `total_tokens`). Mean and median are per
instance. A median of 0 with a non-zero mean means only some repositories
have files in that category.

### Overview: share of tokens per category

{_overview(data)}

{benchmark_sections}
## Data files

All token counts are `cl100k_base` tokens. Categories are {cats}.

| File | One row per | Columns |
| --- | --- | --- |
| `benchmark_summary.csv` | benchmark × category | `benchmark`, `category`, `n_instances`, `tokens_{{mean,median,stdev,min,max,sum}}`, `files_{{mean,median,stdev,min,max,sum}}`, `pooled_token_share`, `mean_token_share`, `median_token_share` |
| `benchmark_share_wide.csv` | benchmark | `benchmark`, then each category's `pooled_token_share` (for stacked bar charts) |
| `repo_summary.csv` | benchmark × repository × category | same as `benchmark_summary.csv`, plus `repo` |
| `instances.csv` | instance | `benchmark`, `instance_id`, `repo`, `total_tokens`, `total_files`, `<category>_tokens`, `<category>_files` |
| `extension_categories.csv` | extension | `extension`, `category` (anything not listed is `other`) |
| `<benchmark>.json` | benchmark | everything above plus every instance's raw `by_extension` counts, so categories can be regrouped without re-running anything |

`pooled_token_share` weights instances by size (the category's tokens summed
over instances, divided by all tokens). `mean_token_share` is the mean of the
per-instance shares (each instance weighted equally). Standard deviations are
population standard deviations, as in `results/<benchmark>.json`.

## Regenerating

From `tokenizer-agent/`:

```bash
python file_type_breakdown.py jobs/verified -o results/file_types/verified.json
python file_type_breakdown.py jobs/pro -o results/file_types/pro.json
python file_type_breakdown.py jobs/xl -o results/file_types/xl.json
python file_type_breakdown.py jobs/xl -o results/file_types/xl_subset.json \\
    --instances results/xl_subset_instances.txt
python file_type_breakdown.py jobs/deepswe -o results/file_types/deepswe.json \\
    --task-defs <dir with the DeepSWE task definitions>
python file_type_report.py
```

See `file_type_breakdown.py`'s docstring for how to download the DeepSWE task
definitions at the refs the job used. To change which category an extension
belongs to, edit `CATEGORIES` in `file_type_breakdown.py` and rerun all of the
above.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the file-type report.")
    parser.add_argument(
        "--dir",
        type=Path,
        default=SCRIPT_DIR / "results" / "file_types",
        help="Directory holding the per-benchmark JSONs; outputs go here too",
    )
    args = parser.parse_args()

    data = _load(args.dir)
    write_csvs(data, args.dir)
    write_readme(data, args.dir)
    print(f"Wrote README.md and CSVs to {args.dir}")


if __name__ == "__main__":
    main()
