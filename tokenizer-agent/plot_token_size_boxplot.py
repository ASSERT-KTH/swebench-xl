#!/usr/bin/env python3
"""Generate a pgfplots boxplot figure of benchmark instance token sizes.

Reads every ``benchmark_size_stats.json`` (the format ``benchmark_size_stats.py``
writes) it can find, computes a five-number summary (min, 25th percentile,
median, 75th percentile, max) of ``total_tokens`` across each benchmark's
instances, and prints a copy-paste-ready LaTeX/pgfplots figure: benchmarks on
the y-axis, token count (log scale) on the x-axis, one horizontal box-and-
whisker per benchmark. Replaces the old mean/median/stdev bar chart.

Requires pgfplots' ``statistics`` library for the ``boxplot prepared`` key —
add ``\\usepgfplotslibrary{statistics}`` to your document preamble once (the
generated figure includes this as a reminder comment, but it has to go
before ``\\begin{document}``, not inside the figure itself).

Sources:
    - Every ``*.json`` file directly under ``--results-dir`` (default:
      ``results/`` next to this script) — currently ``verified.json``,
      ``pro.json``, ``deepswe.json``, ``xl.json``.

Usage:
    python plot_token_size_boxplot.py [--results-dir DIR] [--metric FIELD]
        [-o OUTPUT]

Known gap: this only covers SWE-bench Verified/Pro/XL and DeepSWE (DataCurve). Check whether the paper wants any other benchmark (e.g.
SWE-Gym, Multi-SWE-bench) added before finalizing the figure — that's a
paper-scope call, not something this script can decide from the results
directory alone.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# filename stem (results/<stem>.json) -> display name for the y-axis.
# Add an entry here as soon as a new benchmark's stats land in results/.
BENCHMARK_NAMES: dict[str, str] = {
    "xl": "SWE-bench XL",
    "pro": "SWE-bench Pro",
    "verified": "SWE-bench Verified",
    "deepswe": "DeepSWE (DataCurve)",
}

# Top-to-bottom row order in the figure. Anything found but not listed here
# is appended at the end (alphabetically) so new/renamed files still show up
# instead of silently vanishing.
BENCHMARK_ORDER: list[str] = ["xl", "pro", "verified", "deepswe"]


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    """Return (q1, median, q3) using linear interpolation (numpy-compatible)."""
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, statistics.median(values), q3


def _five_number_summary(values: list[float], metric: str) -> dict[str, float]:
    if not values:
        raise ValueError(f"no instances with '{metric}' values")
    q1, median, q3 = _quartiles(values)
    return {
        "lower": min(values),
        "q1": q1,
        "median": median,
        "q3": q3,
        "upper": max(values),
        "n": len(values),
    }


def _load_stats_file(path: Path, metric: str) -> dict[str, float]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    values = [inst[metric] for inst in data["instances"]]
    # The x-axis is log-scale, which can't place a value <= 0, so drop
    # non-positive values here rather than let pgfplots choke on an
    # unplottable whisker.
    n_total = len(values)
    positive = [v for v in values if v > 0]
    if len(positive) < n_total:
        print(
            f"warning: {path.name}: dropped {n_total - len(positive)} instance(s) "
            f"with {metric} <= 0 (can't be shown on a log-scale axis)"
        )
    return _five_number_summary(positive, metric)


def _collect_results(results_dir: Path, metric: str) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    if not results_dir.is_dir():
        print(f"warning: results dir not found: {results_dir}")
        return stats
    for path in sorted(results_dir.glob("*.json")):
        stem = path.stem
        try:
            stats[stem] = _load_stats_file(path, metric)
        except (KeyError, ValueError) as e:
            print(f"warning: skipping {path} ({e})")
            continue
        if stem not in BENCHMARK_NAMES:
            print(
                f"warning: {path} has no display name in BENCHMARK_NAMES "
                f"(showing as {stem!r}) — add one if this should have a nicer label"
            )
    return stats


def _fmt(n: float) -> str:
    """Render a token count for pgfplots coordinates (no scientific notation)."""
    return f"{n:.0f}"


def _boxplot_entry(name: str, s: dict[str, float]) -> str:
    return (
        "      \\addplot+[boxplot prepared={{\n"
        "        lower whisker={lower}, lower quartile={q1},\n"
        "        median={median},\n"
        "        upper quartile={q3}, upper whisker={upper}\n"
        "      }}] coordinates {{}};\n"
        "      % {name}: n={n}, min={lower}, q1={q1:.0f}, median={median:.0f}, "
        "q3={q3:.0f}, max={upper}"
    ).format(
        name=name,
        n=s["n"],
        lower=_fmt(s["lower"]),
        q1=s["q1"],
        median=s["median"],
        q3=s["q3"],
        upper=_fmt(s["upper"]),
    )


METRIC_LABELS = {
    "total_tokens": "Token",
    "source_code_tokens": "Source-Code Token",
    "total_characters": "Character",
}


def build_figure(
    stats: dict[str, dict[str, float]],
    metric: str,
    xscale: str = "log",
) -> str:
    rows = dict(stats)

    ordered_keys = [k for k in BENCHMARK_ORDER if k in rows]
    ordered_keys += sorted(k for k in rows if k not in BENCHMARK_ORDER)
    if not ordered_keys:
        raise SystemExit("No benchmark stats found to plot.")

    display_names = BENCHMARK_NAMES
    yticklabels = ", ".join(display_names.get(k, k) for k in ordered_keys)
    n_rows = len(ordered_keys)

    plots = "\n".join(_boxplot_entry(display_names.get(k, k), rows[k]) for k in ordered_keys)

    metric_label = METRIC_LABELS.get(metric, metric)

    is_log = xscale == "log"
    xmode_line = "xmode=log,\n      " if is_log else ""
    scale_note = "log scale" if is_log else "linear scale"
    label_suffix = "" if is_log else "-linear"

    return f"""% Requires pgfplots' statistics library for `boxplot prepared` — add this
% to your preamble (once, not per-figure), before \\begin{{document}}:
%   \\usepgfplotslibrary{{statistics}}
\\begin{{figure}}[t]
  \\centering
  \\begin{{tikzpicture}}
    \\begin{{axis}}[
      title={{{metric_label} Size of Benchmarks}},
      xlabel={{{metric_label}s ({scale_note})}},
      {xmode_line}width=13cm,
      height={0.9 + 0.9 * n_rows}cm,
      ytick={{1,...,{n_rows}}},
      yticklabels={{{yticklabels}}},
      y dir=reverse,
      ymin=0.5, ymax={n_rows + 0.5},
      enlarge x limits=0.1,
      boxplot/draw direction=x,
      every axis plot post/.append style={{fill=blue!20}},
    ]
{plots}
    \\end{{axis}}
  \\end{{tikzpicture}}
  \\caption{{TODO: placeholder caption. Distribution (min, 25th/50th/75th
    percentile, max) of instance {metric_label.lower()} size across
    {{{', '.join(display_names.get(k, k) for k in ordered_keys)}}}.}}
  \\label{{fig:avg-token-size{label_suffix}}}
\\end{{figure}}
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a pgfplots boxplot figure of benchmark token sizes."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=SCRIPT_DIR / "results",
        help="Directory of benchmark_size_stats.json files (default: ./results)",
    )
    parser.add_argument(
        "--metric",
        default="source_code_tokens",
        choices=["total_tokens", "source_code_tokens", "total_characters"],
        help="Per-instance field to summarize (default: source_code_tokens)",
    )
    parser.add_argument(
        "--xscale",
        choices=["log", "linear", "both"],
        default="log",
        help=(
            "x-axis scale (default: log — needed since benchmarks span ~500x "
            "in size; 'both' prints/writes one figure per scale for comparison)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Write the figure here instead of only printing it to stdout. "
            "With --xscale both, this is used as a base path: '_log' / "
            "'_linear' are inserted before the suffix."
        ),
    )
    args = parser.parse_args()

    stats = _collect_results(args.results_dir, args.metric)

    xscales = ["log", "linear"] if args.xscale == "both" else [args.xscale]
    for xscale in xscales:
        figure = build_figure(stats, args.metric, xscale)
        print(figure)

        if args.output:
            if args.xscale == "both":
                out_path = args.output.with_stem(f"{args.output.stem}_{xscale}")
            else:
                out_path = args.output
            out_path.write_text(figure, encoding="utf-8")
            print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
