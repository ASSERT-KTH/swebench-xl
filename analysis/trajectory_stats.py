#!/usr/bin/env python3
"""
Generate an HTML dashboard comparing trajectory-analysis-v2 results across
multiple coding-agent runs.

Usage:
    python trajectory_stats.py <run_dir_1> <run_dir_2> [...] [-o output.html]

Each <run_dir> must contain an analysis-v2_*.json file produced by the
trajectory-analysis-v2 skill.
"""

import argparse
import glob
import html
import json
import os
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Failure taxonomy – descriptions & indicators lifted from failure-taxonomy.md
# ---------------------------------------------------------------------------
FAILURE_TAXONOMY = {
    # Navigation & Search
    "wrong_file_identified": {
        "category": "Navigation & Search",
        "description": "Agent identified and edited the wrong file(s), possibly confused by similarly named files across modules or packages.",
        "indicators": "Edits applied to a file that is unrelated to the failing tests; agent confused FooService in module A with FooService in module B.",
        "large_codebase_sensitive": True,
    },
    "incomplete_search": {
        "category": "Navigation & Search",
        "description": "Agent did not search enough of the codebase; missed relevant files, classes, or methods needed to understand or fix the issue.",
        "indicators": "Agent stopped searching after finding one related file but the fix required changes in another; agent never searched for callers/implementors of the relevant interface.",
        "large_codebase_sensitive": True,
    },
    "search_overload": {
        "category": "Navigation & Search",
        "description": "Agent performed broad searches that returned too many results and failed to narrow down to the relevant code.",
        "indicators": "Agent grepped for a common term, got hundreds of results, then either picked the wrong one or gave up filtering; agent read many irrelevant files before (or without) finding the right one.",
        "large_codebase_sensitive": True,
    },
    "lost_in_structure": {
        "category": "Navigation & Search",
        "description": "Agent could not effectively navigate the project's directory hierarchy, module structure, or package organization.",
        "indicators": "Agent expressed confusion about where files live; tried multiple wrong paths; did not use project conventions (e.g., Maven module layout, src/main vs src/test) to orient.",
        "large_codebase_sensitive": True,
    },
    # Comprehension & Reasoning
    "misunderstood_task": {
        "category": "Comprehension & Reasoning",
        "description": "Agent misinterpreted the issue description, requirements, expected behavior, or acceptance criteria.",
        "indicators": "Agent's stated plan does not match what the issue asks for; agent solves a different problem than described; agent's fix targets the wrong symptom.",
        "large_codebase_sensitive": False,
    },
    "incorrect_root_cause": {
        "category": "Comprehension & Reasoning",
        "description": "Agent diagnosed the wrong root cause and applied a fix that does not address the actual problem.",
        "indicators": "Agent identified a plausible but incorrect cause; reasoning chain has a flawed inference step; fix changes behavior unrelated to the bug.",
        "large_codebase_sensitive": False,
    },
    "cross_file_dependency_missed": {
        "category": "Comprehension & Reasoning",
        "description": "Agent's change did not account for how it propagates to dependent or depended-upon files and modules.",
        "indicators": "Agent changed a method signature but did not update callers; agent modified a base class without checking subclasses; agent changed a serialization format without updating the deserializer.",
        "large_codebase_sensitive": True,
    },
    "abstraction_layer_confusion": {
        "category": "Comprehension & Reasoning",
        "description": "Agent conflated different abstraction layers — e.g., edited a public API when the fix belongs in internal logic, or vice versa.",
        "indicators": "Agent modified a high-level orchestrator when the bug is in a low-level utility; agent patched a transport layer issue at the application layer.",
        "large_codebase_sensitive": True,
    },
    "framework_constraint_missed": {
        "category": "Comprehension & Reasoning",
        "description": "Agent violated a constraint imposed by the build system, framework, or language runtime that governs how code must be structured.",
        "indicators": "Agent added a dependency that creates a cycle; agent used a feature not available in the target Java/Python version; agent broke a required annotation contract.",
        "large_codebase_sensitive": "Partial",
    },
    "type_system_error": {
        "category": "Comprehension & Reasoning",
        "description": "Agent misunderstood or misused the type system — generics, type bounds, variance, type inference, or similar constructs.",
        "indicators": "Agent introduced a raw type where a parameterized type is needed; agent's generic bounds are too narrow or too wide; agent confused covariance with contravariance.",
        "large_codebase_sensitive": "Partial",
    },
    "api_contract_violation": {
        "category": "Comprehension & Reasoning",
        "description": "Agent's changes broke an implicit or explicit API contract, interface specification, or behavioral guarantee.",
        "indicators": "Agent changed a method's return semantics; agent's implementation does not satisfy the interface's documented invariants; agent broke backward compatibility.",
        "large_codebase_sensitive": True,
    },
    # Edit Quality
    "syntax_error": {
        "category": "Edit Quality",
        "description": "Agent produced code that does not parse, compile, or pass static analysis.",
        "indicators": "Build fails with syntax/parse errors in agent-modified files; agent left unclosed braces, mismatched parentheses, or invalid tokens.",
        "large_codebase_sensitive": False,
    },
    "semantic_error": {
        "category": "Edit Quality",
        "description": "Agent's code is syntactically valid but logically incorrect — it does not do what was intended.",
        "indicators": "Code compiles but tests still fail because the logic is wrong; off-by-one error; wrong comparison operator; incorrect boolean logic.",
        "large_codebase_sensitive": False,
    },
    "incomplete_edit": {
        "category": "Edit Quality",
        "description": "Agent made a partial fix that addresses some but not all aspects of the issue.",
        "indicators": "Some fail_to_pass tests now pass but not all; agent fixed one code path but missed another; agent addressed the main case but not edge cases mentioned in the issue.",
        "large_codebase_sensitive": "Partial",
    },
    "invasive_refactor": {
        "category": "Edit Quality",
        "description": "Agent restructured significantly more code than necessary, introducing risk and breaking unrelated functionality.",
        "indicators": "Agent rewrote entire methods or classes when a one-line fix sufficed; agent moved code between files unnecessarily; diff is 10x larger than the gold solution.",
        "large_codebase_sensitive": False,
    },
    "regression_introduced": {
        "category": "Edit Quality",
        "description": "Agent's fix resolves the target issue but causes previously passing tests to fail.",
        "indicators": "pass_to_pass tests break after the agent's changes; agent's fix has unintended side effects on other functionality.",
        "large_codebase_sensitive": True,
    },
    "wrong_edit_location": {
        "category": "Edit Quality",
        "description": "Agent applied correct fix logic but in the wrong method, class, file, or code block.",
        "indicators": "The fix logic is sound but it's in a method that is not on the execution path for the failing test; agent edited an overload that is not called.",
        "large_codebase_sensitive": True,
    },
    "test_oracle_misread": {
        "category": "Edit Quality",
        "description": "Agent misread what the test assertions actually check, leading to a fix that targets the wrong property or behavior.",
        "indicators": "Agent's fix makes a different assertion pass than the one that's actually failing; agent misunderstood the test setup or mocking.",
        "large_codebase_sensitive": False,
    },
    # Effort & Behavior
    "gave_up": {
        "category": "Effort & Behavior",
        "description": "Agent abandoned the task before exhausting reasonable approaches or making a meaningful attempt at a fix.",
        "indicators": "Agent stated it cannot solve the problem and stopped; agent produced no edits; agent submitted an empty or placeholder patch.",
        "large_codebase_sensitive": False,
    },
    "loop_detected": {
        "category": "Effort & Behavior",
        "description": "Agent repeated the same or very similar failing actions multiple times without meaningful variation or learning.",
        "indicators": "Agent applied the same patch 3+ times; agent ran the same failing command repeatedly; agent alternated between two broken approaches without trying a third.",
        "large_codebase_sensitive": False,
    },
    "distracted_by_tangent": {
        "category": "Effort & Behavior",
        "description": "Agent spent significant time and effort exploring or modifying code unrelated to the core issue.",
        "indicators": "Agent spent many steps investigating a red herring; agent tried to fix pre-existing warnings unrelated to the task; agent read dozens of irrelevant files.",
        "large_codebase_sensitive": True,
    },
    "resource_limit_hit": {
        "category": "Effort & Behavior",
        "description": "Agent exhausted its token budget, cost limit, time limit, or step limit before completing the task.",
        "indicators": "Trajectory ends abruptly without a final patch; agent's last message indicates a limit was reached; result.json shows the agent timed out.",
        "large_codebase_sensitive": "Partial",
    },
    # Context & Memory
    "lost_context": {
        "category": "Context & Memory",
        "description": "Agent forgot or contradicted its own earlier findings, re-read files it had already examined, or lost track of its plan.",
        "indicators": "Agent re-opens a file it read 10 steps ago and re-discovers the same information; agent's later reasoning contradicts its earlier (correct) analysis; agent states facts about code that it already disproved.",
        "large_codebase_sensitive": True,
    },
    "context_window_overwhelm": {
        "category": "Context & Memory",
        "description": "Agent's reasoning quality visibly degraded as its context filled up with accumulated code and observations.",
        "indicators": "Early steps show clear, focused reasoning but later steps become vague or confused; agent starts making errors it would not have made earlier; agent stops referencing earlier findings.",
        "large_codebase_sensitive": True,
    },
    "convention_violation": {
        "category": "Context & Memory",
        "description": "Agent's changes do not follow the codebase's established coding patterns, naming conventions, or architectural style.",
        "indicators": "Agent used a different naming scheme; agent put code in a non-standard location; agent used a pattern inconsistent with surrounding code; agent ignored existing utility methods and reimplemented logic.",
        "large_codebase_sensitive": True,
    },
    # Environment & Tooling
    "build_failure_unrecovered": {
        "category": "Environment & Tooling",
        "description": "Agent encountered a build or compile error and could not diagnose or work around it.",
        "indicators": "Agent tried to build, got errors, and either gave up or kept making changes without resolving the build; agent's final state does not compile.",
        "large_codebase_sensitive": False,
    },
    "test_infrastructure_failure": {
        "category": "Environment & Tooling",
        "description": "Tests failed due to infrastructure issues unrelated to the agent's code changes — flaky tests, environment misconfiguration, or timeout.",
        "indicators": "Tests that should pass are failing even without agent changes; test failures are non-deterministic; error messages point to environment issues.",
        "large_codebase_sensitive": False,
    },
    "environment_setup_failure": {
        "category": "Environment & Tooling",
        "description": "Agent could not properly set up the development environment, install dependencies, or configure the workspace.",
        "indicators": "Agent spent many steps trying to install packages or configure the build; environment errors prevented the agent from running tests; agent could not start the application.",
        "large_codebase_sensitive": False,
    },
    "tooling_misuse": {
        "category": "Environment & Tooling",
        "description": "Agent used available tools incorrectly — wrong commands, wrong flags, misunderstood output, or used the wrong tool for the job.",
        "indicators": "Agent ran a test command with wrong arguments; agent misinterpreted a command's output; agent used sed when it should have used a proper edit tool; agent ran destructive commands unnecessarily.",
        "large_codebase_sensitive": False,
    },
}


def esc(text):
    """HTML-escape text."""
    return html.escape(str(text)) if text is not None else ""


def find_analysis_file(run_dir):
    """Find the analysis-v2_*.json file in a run directory."""
    pattern = os.path.join(run_dir, "analysis-v2_*.json")
    files = glob.glob(pattern)
    if not files:
        sys.exit(f"Error: no analysis-v2_*.json found in {run_dir}")
    return files[0]


def load_run(path):
    with open(path) as f:
        return json.load(f)


def run_label(data):
    m = data["run_metadata"]
    return f"{m['agent_name']} ({m['model']})"


# ---------------------------------------------------------------------------
# Tooltip content builder
# ---------------------------------------------------------------------------
def tooltip_attrs(failure_mode):
    """Return a data-tooltip attribute string for a failure mode."""
    info = FAILURE_TAXONOMY.get(failure_mode)
    if not info:
        return ""
    lcs = info["large_codebase_sensitive"]
    if lcs is True:
        lcs_str = "Yes"
    elif lcs is False:
        lcs_str = "No"
    else:
        lcs_str = str(lcs)
    tip = (
        f"{info['category']}\\n\\n"
        f"{info['description']}\\n\\n"
        f"Indicators: {info['indicators']}\\n\\n"
        f"Large-codebase sensitive: {lcs_str}"
    )
    return f' data-tooltip="{esc(tip)}"'


# ---------------------------------------------------------------------------
# HTML generation helpers
# ---------------------------------------------------------------------------
OUTCOME_COLORS = {
    "resolved": "#22c55e",
    "partially_resolved": "#f59e0b",
    "unresolved": "#ef4444",
    "error": "#a855f7",
}

QUALITY_COLORS = {
    "effective": "#22c55e", "strong": "#22c55e", "correct": "#22c55e", "efficient": "#22c55e",
    "partial": "#f59e0b", "adequate": "#f59e0b",
    "poor": "#ef4444", "weak": "#ef4444", "incorrect": "#ef4444", "wasteful": "#ef4444",
    "not_applicable": "#94a3b8", "no_edit": "#94a3b8", "absent": "#94a3b8", "abandoned": "#94a3b8",
}


def badge(text, color):
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
        f'font-size:0.78rem;font-weight:600;color:#fff;background:{color};'
        f'white-space:nowrap">{esc(text)}</span>'
    )


def outcome_badge(outcome):
    return badge(outcome.replace("_", " "), OUTCOME_COLORS.get(outcome, "#64748b"))


def quality_badge(val):
    return badge(val.replace("_", " "), QUALITY_COLORS.get(val, "#64748b"))


def pct(n, total):
    if total == 0:
        return "0%"
    return f"{n / total * 100:.1f}%"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_overview_card(data):
    m = data["run_metadata"]
    total = m["analyzed_count"]
    ts = data.get("analysis_timestamp", "")[:10]
    parts = []
    parts.append('<div class="card">')
    parts.append(f'<h3>{esc(m["agent_name"])} <span class="model-tag">{esc(m["model"])}</span></h3>')
    parts.append(f'<p class="subtext">Dataset: {esc(m["dataset"])} &middot; Analysed: {esc(ts)}</p>')

    # KPI row
    parts.append('<div class="kpi-row">')
    for label, val, color in [
        ("Instances", m["total_instances"], "#64748b"),
        ("Resolved", m["resolved_count"], "#22c55e"),
        ("Unresolved", m["unresolved_count"], "#ef4444"),
        ("Partial", m.get("partially_resolved_count", 0), "#f59e0b"),
        ("Error", m.get("error_count", 0), "#a855f7"),
        ("Rate", f'{m["resolution_rate"]:.0%}' if isinstance(m["resolution_rate"], float) else m["resolution_rate"], "#3b82f6"),
    ]:
        parts.append(
            f'<div class="kpi" style="border-top:3px solid {color}">'
            f'<div class="kpi-val">{val}</div>'
            f'<div class="kpi-label">{label}</div>'
            f'</div>'
        )
    parts.append('</div>')  # kpi-row

    # Outcome donut (simple bar chart fallback)
    res = m["resolved_count"]
    unres = m["unresolved_count"]
    par = m.get("partially_resolved_count", 0)
    err = m.get("error_count", 0)
    parts.append('<div class="bar-chart">')
    for count, color, label in [
        (res, "#22c55e", "Resolved"),
        (par, "#f59e0b", "Partial"),
        (unres, "#ef4444", "Unresolved"),
        (err, "#a855f7", "Error"),
    ]:
        w = count / total * 100 if total else 0
        if w > 0:
            parts.append(
                f'<div class="bar-seg" style="width:{w}%;background:{color}" '
                f'title="{label}: {count} ({w:.1f}%)">'
                f'{"" if w < 5 else count}'
                f'</div>'
            )
    parts.append('</div>')

    parts.append('</div>')  # card
    return "\n".join(parts)


def build_run_summary(data):
    parts = []
    parts.append('<div class="card">')
    parts.append('<h3>Executive Summary</h3>')
    parts.append(f'<div class="summary-text">{esc(data["run_summary"])}</div>')
    parts.append('</div>')
    return "\n".join(parts)


def build_failure_distribution(data):
    dist = data["failure_mode_distribution"]
    if not dist:
        return ""
    sorted_modes = sorted(dist.items(), key=lambda x: -x[1])
    total_failures = sum(dist.values())
    parts = []
    parts.append('<div class="card">')
    parts.append('<h3>Failure Mode Distribution</h3>')
    parts.append('<table class="data-table"><thead><tr>')
    parts.append('<th>Failure Mode</th><th>Category</th><th>Count</th><th>% of Failures</th><th>Bar</th>')
    parts.append('</tr></thead><tbody>')
    max_count = sorted_modes[0][1] if sorted_modes else 1
    for mode, count in sorted_modes:
        info = FAILURE_TAXONOMY.get(mode, {})
        cat = info.get("category", "Unknown")
        bar_w = count / max_count * 100
        pct_val = count / total_failures * 100 if total_failures else 0
        parts.append(
            f'<tr>'
            f'<td class="hoverable"{tooltip_attrs(mode)}>{esc(mode.replace("_", " "))}</td>'
            f'<td class="cat-badge">{esc(cat)}</td>'
            f'<td style="text-align:right;font-weight:600">{count}</td>'
            f'<td style="text-align:right">{pct_val:.1f}%</td>'
            f'<td style="min-width:120px"><div class="h-bar" style="width:{bar_w}%"></div></td>'
            f'</tr>'
        )
    parts.append('</tbody></table>')
    parts.append('</div>')
    return "\n".join(parts)


def build_large_codebase_impact(data):
    lci = data["large_codebase_impact"]
    parts = []
    parts.append('<div class="card">')
    parts.append('<h3>Large Codebase Impact</h3>')
    parts.append('<div class="kpi-row">')

    rate_display = f'{lci["large_codebase_induced_rate"]:.0%}' if isinstance(lci["large_codebase_induced_rate"], float) else lci["large_codebase_induced_rate"]
    for label, val, color in [
        ("Scale-Induced Failures", lci["large_codebase_induced_count"], "#ef4444"),
        ("Scale-Induced Rate", rate_display, "#f59e0b"),
    ]:
        parts.append(
            f'<div class="kpi" style="border-top:3px solid {color}">'
            f'<div class="kpi-val">{val}</div>'
            f'<div class="kpi-label">{label}</div>'
            f'</div>'
        )
    parts.append('</div>')

    # Most common scale failures
    parts.append('<div style="margin:12px 0"><strong>Most Common Scale Failures:</strong> ')
    for mode in lci.get("most_common_scale_failures", []):
        parts.append(f'<span class="hoverable tag"{tooltip_attrs(mode)}>{esc(mode.replace("_", " "))}</span> ')
    parts.append('</div>')

    parts.append(f'<div class="summary-text">{esc(lci["summary"])}</div>')
    parts.append('</div>')
    return "\n".join(parts)


def build_deep_dives(data):
    dives = data.get("failure_category_deep_dives", [])
    if not dives:
        return ""
    parts = []
    parts.append('<div class="card">')
    parts.append('<h3>Failure Category Deep Dives</h3>')
    for dive in dives:
        mode = dive["failure_mode"]
        parts.append(f'<details class="deep-dive"><summary class="hoverable"{tooltip_attrs(mode)}>')
        parts.append(
            f'<strong>{esc(mode.replace("_", " "))}</strong> &mdash; '
            f'{dive["instance_count"]} instance(s), '
            f'{dive.get("large_codebase_induced_count", 0)} scale-induced '
            f'({dive.get("large_codebase_induced_rate", 0):.0%})'
        )
        parts.append('</summary>')
        parts.append(f'<div class="deep-dive-body">')
        parts.append(f'<p>{esc(dive["summary"])}</p>')
        parts.append(f'<p><strong>Scale explanation:</strong> {esc(dive.get("large_codebase_explanation", ""))}</p>')
        parts.append('<p><strong>Instances:</strong> ')
        for iid in dive.get("instance_ids", []):
            parts.append(f'<span class="instance-id">{esc(iid)}</span> ')
        parts.append('</p></div>')
        parts.append('</details>')
    parts.append('</div>')
    return "\n".join(parts)


def build_quality_distribution(data):
    """Build a quality dimensions visualization with per-dimension stacked bars."""
    trajectories = data["trajectories"]
    total = len(trajectories)
    dims = [
        ("navigation_quality", "Navigation", ["effective", "partial", "poor", "not_applicable"]),
        ("reasoning_quality",  "Reasoning",  ["strong", "adequate", "weak", "absent"]),
        ("edit_quality",       "Edit",        ["correct", "partial", "incorrect", "no_edit"]),
        ("effort_efficiency",  "Effort",      ["efficient", "adequate", "wasteful", "abandoned"]),
    ]

    parts = []
    parts.append('<div class="card">')
    parts.append('<h3>Quality Dimensions</h3>')
    parts.append('<div class="quality-grid">')
    for dim_key, dim_label, levels in dims:
        counts = defaultdict(int)
        for t in trajectories:
            counts[t.get(dim_key, "unknown")] += 1

        parts.append(f'<div class="quality-dim">')
        parts.append(f'<div class="quality-dim-label">{dim_label}</div>')
        parts.append(f'<div class="bar-chart" style="height:22px">')
        for v in levels:
            c = counts.get(v, 0)
            if c == 0:
                continue
            w = c / total * 100
            color = QUALITY_COLORS.get(v, "#64748b")
            parts.append(
                f'<div class="bar-seg" style="width:{w}%;background:{color}" '
                f'title="{v.replace("_", " ")}: {c} ({w:.1f}%)">'
                f'{"" if w < 8 else c}'
                f'</div>'
            )
        parts.append('</div>')
        # Legend row
        parts.append('<div class="quality-legend">')
        for v in levels:
            c = counts.get(v, 0)
            color = QUALITY_COLORS.get(v, "#64748b")
            parts.append(
                f'<span class="quality-legend-item">'
                f'<span class="legend-dot" style="background:{color}"></span>'
                f'{v.replace("_", " ")} <strong>{c}</strong>'
                f'</span>'
            )
        parts.append('</div>')
        parts.append('</div>')
    parts.append('</div></div>')
    return "\n".join(parts)


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


def build_trajectory_table(data):
    trajectories = data["trajectories"]
    parts = []
    parts.append('<div class="card">')
    parts.append(f'<h3>All Instances ({len(trajectories)})</h3>')
    parts.append('<div class="table-scroll">')
    parts.append('<table class="data-table instance-table"><thead><tr>')
    parts.append(
        '<th>Instance</th><th>Outcome</th><th>Reward</th>'
        '<th>Primary Failure</th><th>Secondary Failures</th>'
        '<th>Scale-Induced</th>'
        '<th>Nav</th><th>Reason</th><th>Edit</th><th>Effort</th>'
        '<th>Tags</th><th>Summary</th><th>Key Moment</th>'
    )
    parts.append('</tr></thead><tbody>')

    for t in sorted(trajectories, key=lambda x: (x["outcome"] != "resolved", x["instance_id"])):
        pf = t.get("primary_failure_mode")
        sf = t.get("secondary_failure_modes", [])
        lci = t.get("large_codebase_induced", False)
        lci_notes = t.get("large_codebase_notes") or ""

        pf_cell = f'<span class="hoverable"{tooltip_attrs(pf)}>{esc(pf.replace("_", " "))}</span>' if pf else '&mdash;'
        sf_cell = ", ".join(
            f'<span class="hoverable"{tooltip_attrs(s)}>{esc(s.replace("_", " "))}</span>' for s in sf
        ) if sf else '&mdash;'

        lci_cell = (
            f'<span class="hoverable" data-tooltip="{esc(lci_notes)}">Yes</span>' if lci
            else "No"
        ) if t["outcome"] != "resolved" else '&mdash;'

        tags_cell = " ".join(f'<span class="tag">{esc(tag)}</span>' for tag in t.get("tags", []))
        summary_cell = esc(t.get("summary", ""))
        km_cell = esc(t.get("key_moment") or "")

        parts.append(
            f'<tr class="outcome-{t["outcome"]}">'
            f'<td class="instance-id" style="white-space:nowrap">{esc(t["instance_id"])}</td>'
            f'<td>{outcome_badge(t["outcome"])}</td>'
            f'<td style="text-align:center">{t.get("reward") if t.get("reward") is not None else "&mdash;"}</td>'
            f'<td>{pf_cell}</td>'
            f'<td>{sf_cell}</td>'
            f'<td style="text-align:center">{lci_cell}</td>'
            f'<td>{quality_badge(t.get("navigation_quality", "unknown"))}</td>'
            f'<td>{quality_badge(t.get("reasoning_quality", "unknown"))}</td>'
            f'<td>{quality_badge(t.get("edit_quality", "unknown"))}</td>'
            f'<td>{quality_badge(t.get("effort_efficiency", "unknown"))}</td>'
            f'<td>{tags_cell}</td>'
            f'<td class="summary-cell">{summary_cell}</td>'
            f'<td class="summary-cell">{km_cell}</td>'
            f'</tr>'
        )
    parts.append('</tbody></table>')
    parts.append('</div></div>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Comparison tab
# ---------------------------------------------------------------------------

def build_comparison(runs):
    parts = []

    # Side-by-side KPIs
    parts.append('<div class="card">')
    parts.append('<h3>Resolution Comparison</h3>')
    parts.append('<div class="compare-grid">')
    for data in runs:
        m = data["run_metadata"]
        rate = m["resolution_rate"]
        rate_str = f'{rate:.0%}' if isinstance(rate, float) else rate
        parts.append(
            f'<div class="compare-col">'
            f'<h4>{esc(m["agent_name"])}<br/><span class="model-tag">{esc(m["model"])}</span></h4>'
            f'<div class="big-number">{rate_str}</div>'
            f'<div class="subtext">resolution rate</div>'
            f'<div style="margin-top:8px">'
            f'{m["resolved_count"]} resolved / {m["analyzed_count"]} total'
            f'</div>'
            f'</div>'
        )
    parts.append('</div></div>')

    # Failure mode comparison table
    all_modes = set()
    for data in runs:
        all_modes.update(data["failure_mode_distribution"].keys())
    all_modes = sorted(all_modes)

    parts.append('<div class="card">')
    parts.append('<h3>Failure Mode Comparison</h3>')
    parts.append('<table class="data-table"><thead><tr>')
    parts.append('<th>Failure Mode</th><th>Category</th>')
    for data in runs:
        parts.append(f'<th style="text-align:right">{esc(data["run_metadata"]["agent_name"])}</th>')
    parts.append('<th>Diff</th><th>Visual</th>')
    parts.append('</tr></thead><tbody>')

    for mode in all_modes:
        info = FAILURE_TAXONOMY.get(mode, {})
        cat = info.get("category", "Unknown")
        counts = [data["failure_mode_distribution"].get(mode, 0) for data in runs]
        diff = counts[-1] - counts[0] if len(counts) == 2 else ""
        diff_str = ""
        if isinstance(diff, int):
            if diff > 0:
                diff_str = f'<span style="color:#ef4444">+{diff}</span>'
            elif diff < 0:
                diff_str = f'<span style="color:#22c55e">{diff}</span>'
            else:
                diff_str = '<span style="color:#94a3b8">0</span>'

        max_c = max(max(counts), 1)
        bar_html = '<div style="display:flex;gap:2px;align-items:end;height:24px">'
        bar_colors = ["#3b82f6", "#f97316", "#8b5cf6", "#06b6d4"]
        for i, c in enumerate(counts):
            w = c / max_c * 80
            bar_html += f'<div style="width:{max(w, 2)}px;height:100%;background:{bar_colors[i % len(bar_colors)]};border-radius:2px" title="{runs[i]["run_metadata"]["agent_name"]}: {c}"></div>'
        bar_html += '</div>'

        parts.append(
            f'<tr>'
            f'<td class="hoverable"{tooltip_attrs(mode)}>{esc(mode.replace("_", " "))}</td>'
            f'<td class="cat-badge">{esc(cat)}</td>'
        )
        for c in counts:
            parts.append(f'<td style="text-align:right;font-weight:600">{c}</td>')
        parts.append(f'<td style="text-align:center">{diff_str}</td>')
        parts.append(f'<td>{bar_html}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')

    # Large codebase impact comparison
    parts.append('<div class="card">')
    parts.append('<h3>Large Codebase Impact Comparison</h3>')
    parts.append('<div class="compare-grid">')
    for data in runs:
        lci = data["large_codebase_impact"]
        rate_str = f'{lci["large_codebase_induced_rate"]:.0%}' if isinstance(lci["large_codebase_induced_rate"], float) else lci["large_codebase_induced_rate"]
        parts.append(
            f'<div class="compare-col">'
            f'<h4>{esc(data["run_metadata"]["agent_name"])}</h4>'
            f'<div class="big-number">{rate_str}</div>'
            f'<div class="subtext">scale-induced failure rate</div>'
            f'<div style="margin-top:8px">{lci["large_codebase_induced_count"]} scale-induced failures</div>'
            f'<div style="margin-top:4px"><strong>Top scale failures:</strong> '
        )
        for mode in lci.get("most_common_scale_failures", []):
            parts.append(f'<span class="hoverable tag"{tooltip_attrs(mode)}>{esc(mode.replace("_", " "))}</span> ')
        parts.append('</div></div>')
    parts.append('</div></div>')

    # Quality dimensions comparison
    dims_compare = [
        ("navigation_quality", "Navigation", ["effective", "partial", "poor", "not_applicable"]),
        ("reasoning_quality",  "Reasoning",  ["strong", "adequate", "weak", "absent"]),
        ("edit_quality",       "Edit",        ["correct", "partial", "incorrect", "no_edit"]),
        ("effort_efficiency",  "Effort",      ["efficient", "adequate", "wasteful", "abandoned"]),
    ]

    parts.append('<div class="card">')
    parts.append('<h3>Quality Dimensions Comparison</h3>')

    for dim_key, dim_label, levels in dims_compare:
        parts.append(f'<h4 style="margin:16px 0 8px">{dim_label}</h4>')
        parts.append('<div class="compare-grid">')
        for data in runs:
            vals = defaultdict(int)
            for t in data["trajectories"]:
                vals[t.get(dim_key, "unknown")] += 1
            total = len(data["trajectories"])
            parts.append(f'<div class="compare-col"><strong>{esc(data["run_metadata"]["agent_name"])}</strong><div class="bar-chart" style="margin:6px 0">')
            for v in levels:
                c = vals.get(v, 0)
                if c == 0:
                    continue
                w = c / total * 100
                color = QUALITY_COLORS.get(v, "#64748b")
                parts.append(
                    f'<div class="bar-seg" style="width:{w}%;background:{color}" '
                    f'title="{v.replace("_", " ")}: {c} ({w:.1f}%)">'
                    f'{"" if w < 8 else f"{c}"}'
                    f'</div>'
                )
            parts.append('</div>')
            # Legend
            parts.append('<div class="quality-legend">')
            for v in levels:
                c = vals.get(v, 0)
                color = QUALITY_COLORS.get(v, "#64748b")
                parts.append(
                    f'<span class="quality-legend-item">'
                    f'<span class="legend-dot" style="background:{color}"></span>'
                    f'{v.replace("_", " ")} <strong>{c}</strong>'
                    f'</span>'
                )
            parts.append('</div></div>')
        parts.append('</div>')
    parts.append('</div>')

    # Per-instance head-to-head
    all_instances = set()
    instance_data = {}
    for data in runs:
        for t in data["trajectories"]:
            iid = t["instance_id"]
            all_instances.add(iid)
            if iid not in instance_data:
                instance_data[iid] = {}
            instance_data[iid][data["run_metadata"]["agent_name"]] = t

    parts.append('<div class="card">')
    parts.append(f'<h3>Head-to-Head Instance Comparison ({len(all_instances)} instances)</h3>')
    parts.append('<div class="table-scroll">')
    parts.append('<table class="data-table"><thead><tr>')
    parts.append('<th>Instance</th>')
    for data in runs:
        name = data["run_metadata"]["agent_name"]
        parts.append(f'<th colspan="3" style="text-align:center;border-bottom:2px solid #e2e8f0">{esc(name)}</th>')
    parts.append('</tr><tr>')
    parts.append('<th></th>')
    for _ in runs:
        parts.append('<th>Outcome</th><th>Failure Mode</th><th>Scale?</th>')
    parts.append('</tr></thead><tbody>')

    for iid in sorted(all_instances):
        outcomes = []
        for data in runs:
            name = data["run_metadata"]["agent_name"]
            t = instance_data.get(iid, {}).get(name)
            if t:
                outcomes.append(t["outcome"])
            else:
                outcomes.append(None)

        # Highlight rows where agents differ
        unique_outcomes = set(o for o in outcomes if o)
        row_class = "diff-row" if len(unique_outcomes) > 1 else ""

        parts.append(f'<tr class="{row_class}">')
        parts.append(f'<td class="instance-id" style="white-space:nowrap">{esc(iid)}</td>')
        for data in runs:
            name = data["run_metadata"]["agent_name"]
            t = instance_data.get(iid, {}).get(name)
            if t:
                pf = t.get("primary_failure_mode")
                pf_display = f'<span class="hoverable"{tooltip_attrs(pf)}>{esc(pf.replace("_", " "))}</span>' if pf else '&mdash;'
                lci = t.get("large_codebase_induced", False)
                lci_display = "Yes" if lci and t["outcome"] != "resolved" else ("No" if t["outcome"] != "resolved" else "&mdash;")
                parts.append(f'<td>{outcome_badge(t["outcome"])}</td>')
                parts.append(f'<td>{pf_display}</td>')
                parts.append(f'<td style="text-align:center">{lci_display}</td>')
            else:
                parts.append('<td colspan="3" style="text-align:center;color:#94a3b8">N/A</td>')
        parts.append('</tr>')

    parts.append('</tbody></table></div></div>')

    # Divergence summary
    both_resolved = 0
    both_failed = 0
    divergent = []
    agent_names = [d["run_metadata"]["agent_name"] for d in runs]
    for iid in sorted(all_instances):
        outcomes_for_inst = []
        for data in runs:
            name = data["run_metadata"]["agent_name"]
            t = instance_data.get(iid, {}).get(name)
            outcomes_for_inst.append(t["outcome"] if t else None)
        if all(o == "resolved" for o in outcomes_for_inst):
            both_resolved += 1
        elif all(o and o != "resolved" for o in outcomes_for_inst):
            both_failed += 1
        elif len(set(o for o in outcomes_for_inst if o)) > 1:
            divergent.append((iid, outcomes_for_inst))

    if len(runs) == 2:
        parts.append('<div class="card">')
        parts.append('<h3>Outcome Divergence Summary</h3>')
        parts.append('<div class="kpi-row">')
        parts.append(f'<div class="kpi" style="border-top:3px solid #22c55e"><div class="kpi-val">{both_resolved}</div><div class="kpi-label">Both Resolved</div></div>')
        parts.append(f'<div class="kpi" style="border-top:3px solid #ef4444"><div class="kpi-val">{both_failed}</div><div class="kpi-label">Both Failed</div></div>')
        parts.append(f'<div class="kpi" style="border-top:3px solid #f59e0b"><div class="kpi-val">{len(divergent)}</div><div class="kpi-label">Divergent</div></div>')
        parts.append('</div>')

        if divergent:
            parts.append('<h4 style="margin:16px 0 8px">Divergent Instances</h4>')
            parts.append('<table class="data-table"><thead><tr>')
            parts.append('<th>Instance</th>')
            for name in agent_names:
                parts.append(f'<th>{esc(name)}</th>')
            parts.append('</tr></thead><tbody>')
            for iid, outs in divergent:
                parts.append(f'<tr><td class="instance-id">{esc(iid)}</td>')
                for o in outs:
                    if o:
                        parts.append(f'<td>{outcome_badge(o)}</td>')
                    else:
                        parts.append('<td style="color:#94a3b8">N/A</td>')
                parts.append('</tr>')
            parts.append('</tbody></table>')
        parts.append('</div>')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main HTML builder
# ---------------------------------------------------------------------------

def build_html(runs, output_path):
    run_labels = [run_label(d) for d in runs]
    tab_ids = [f"run-{i}" for i in range(len(runs))]

    css = """
:root {
    --bg: #0f172a;
    --surface: #1e293b;
    --surface-hover: #334155;
    --border: #334155;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --accent: #3b82f6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 0;
}
.dashboard {
    max-width: 1600px;
    margin: 0 auto;
    padding: 24px 32px;
}
header {
    text-align: center;
    padding: 32px 0 24px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}
header p {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-top: 4px;
}
.tabs {
    display: flex;
    gap: 4px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 24px;
    flex-wrap: wrap;
}
.tab {
    padding: 10px 24px;
    cursor: pointer;
    border: none;
    background: none;
    color: var(--text-muted);
    font-size: 0.95rem;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    transition: all 0.15s;
    margin-bottom: -2px;
}
.tab:hover { color: var(--text); background: var(--surface); border-radius: 6px 6px 0 0; }
.tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
    font-weight: 600;
}
.tab-content { display: none; }
.tab-content.active { display: block; }
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
}
.card h3 {
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--text);
}
.model-tag {
    font-size: 0.8rem;
    font-weight: 400;
    color: var(--text-muted);
    background: var(--bg);
    padding: 2px 8px;
    border-radius: 4px;
}
.subtext { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 12px; }
.kpi-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin: 12px 0;
}
.kpi {
    background: var(--bg);
    border-radius: 8px;
    padding: 16px 20px;
    min-width: 100px;
    flex: 1;
    text-align: center;
}
.kpi-val { font-size: 1.6rem; font-weight: 700; }
.kpi-label { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.bar-chart {
    display: flex;
    border-radius: 6px;
    overflow: hidden;
    height: 28px;
    background: var(--bg);
}
.bar-seg {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
    color: #fff;
    transition: opacity 0.15s;
    min-width: 2px;
}
.bar-seg:hover { opacity: 0.85; }
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}
.data-table th {
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    position: sticky;
    top: 0;
    background: var(--surface);
    z-index: 1;
}
.data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
}
.data-table tbody tr:hover { background: var(--surface-hover); }
.h-bar {
    height: 18px;
    background: var(--accent);
    border-radius: 4px;
    min-width: 2px;
    transition: width 0.3s;
}
.hoverable {
    cursor: help;
    border-bottom: 1px dotted var(--text-muted);
    position: relative;
}
.tooltip {
    display: none;
    position: fixed;
    background: #1a1a2e;
    color: var(--text);
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 14px 18px;
    max-width: 450px;
    font-size: 0.82rem;
    line-height: 1.5;
    z-index: 10000;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    pointer-events: none;
    white-space: pre-wrap;
}
.tag {
    display: inline-block;
    background: var(--bg);
    color: var(--text-muted);
    padding: 1px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    margin: 1px 2px;
}
.instance-id {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.8rem;
    color: var(--accent);
}
.summary-cell {
    max-width: 350px;
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.4;
}
.cat-badge {
    font-size: 0.75rem;
    color: var(--text-muted);
}
.compare-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
}
.compare-col {
    background: var(--bg);
    border-radius: 8px;
    padding: 20px;
    text-align: center;
}
.compare-col h4 { margin-bottom: 12px; font-size: 1rem; }
.big-number { font-size: 2.5rem; font-weight: 800; color: var(--accent); }
.deep-dive {
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
}
.deep-dive summary {
    padding: 12px 16px;
    cursor: pointer;
    background: var(--bg);
    user-select: none;
}
.deep-dive summary:hover { background: var(--surface-hover); }
.deep-dive-body {
    padding: 16px;
    font-size: 0.88rem;
    line-height: 1.6;
}
.deep-dive-body p { margin-bottom: 10px; }
.table-scroll {
    overflow-x: auto;
    max-height: 800px;
    overflow-y: auto;
}
.diff-row { background: rgba(251, 191, 36, 0.06) !important; }
.quality-grid { display: flex; flex-direction: column; gap: 16px; }
.quality-dim {}
.quality-dim-label { font-weight: 600; font-size: 0.9rem; margin-bottom: 6px; }
.quality-legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 6px; }
.quality-legend-item { display: flex; align-items: center; gap: 5px; font-size: 0.78rem; color: var(--text-muted); }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; display: inline-block; flex-shrink: 0; }
.outcome-resolved td:first-child { border-left: 3px solid #22c55e; }
.outcome-unresolved td:first-child { border-left: 3px solid #ef4444; }
.outcome-partially_resolved td:first-child { border-left: 3px solid #f59e0b; }
.outcome-error td:first-child { border-left: 3px solid #a855f7; }
@media (max-width: 768px) {
    .dashboard { padding: 12px 12px; }
    .kpi-row { gap: 6px; }
    .kpi { min-width: 80px; padding: 10px; }
    .kpi-val { font-size: 1.2rem; }
    .tab { padding: 8px 14px; font-size: 0.85rem; }
}
"""

    js = """
document.addEventListener('DOMContentLoaded', function() {
    // Tab switching
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.target).classList.add('active');
        });
    });

    // Tooltip system
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    document.body.appendChild(tooltip);

    document.addEventListener('mouseover', function(e) {
        const el = e.target.closest('.hoverable');
        if (el && el.dataset.tooltip) {
            tooltip.textContent = el.dataset.tooltip.replace(/\\\\n/g, '\\n');
            tooltip.style.display = 'block';
        }
    });
    document.addEventListener('mousemove', function(e) {
        if (tooltip.style.display === 'block') {
            let left = e.clientX + 16;
            let top = e.clientY + 16;
            const rect = tooltip.getBoundingClientRect();
            if (left + rect.width > window.innerWidth - 20) {
                left = e.clientX - rect.width - 16;
            }
            if (top + rect.height > window.innerHeight - 20) {
                top = e.clientY - rect.height - 16;
            }
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        }
    });
    document.addEventListener('mouseout', function(e) {
        const el = e.target.closest('.hoverable');
        if (el) {
            tooltip.style.display = 'none';
        }
    });
});
"""

    body_parts = []
    body_parts.append('<div class="dashboard">')
    body_parts.append('<header>')
    body_parts.append('<h1>Trajectory Analysis Dashboard</h1>')
    body_parts.append(f'<p>{len(runs)} run(s) &middot; {sum(d["run_metadata"]["analyzed_count"] for d in runs)} total trajectories</p>')
    body_parts.append('</header>')

    # Tabs
    body_parts.append('<div class="tabs">')
    for i, label in enumerate(run_labels):
        active = "active" if i == 0 else ""
        body_parts.append(f'<button class="tab {active}" data-target="{tab_ids[i]}">{esc(label)}</button>')
    if len(runs) > 1:
        body_parts.append(f'<button class="tab" data-target="comparison">Comparison</button>')
    body_parts.append('</div>')

    # Per-run tabs
    for i, data in enumerate(runs):
        active = "active" if i == 0 else ""
        body_parts.append(f'<div id="{tab_ids[i]}" class="tab-content {active}">')
        body_parts.append(build_overview_card(data))
        body_parts.append(build_run_summary(data))
        body_parts.append(build_failure_distribution(data))
        body_parts.append(build_large_codebase_impact(data))
        body_parts.append(build_quality_distribution(data))
        body_parts.append(build_deep_dives(data))
        body_parts.append(build_trajectory_table(data))
        body_parts.append('</div>')

    # Comparison tab
    if len(runs) > 1:
        body_parts.append('<div id="comparison" class="tab-content">')
        body_parts.append(build_comparison(runs))
        body_parts.append('</div>')

    body_parts.append('</div>')

    final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trajectory Analysis Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
{"".join(body_parts)}
<script>{js}</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(final_html)
    print(f"Dashboard written to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate an HTML dashboard from trajectory-analysis-v2 JSON files."
    )
    parser.add_argument(
        "run_dirs",
        nargs="+",
        help="Directories containing analysis-v2_*.json files",
    )
    parser.add_argument(
        "-o", "--output",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "trajectory_dashboard.html"),
        help="Output HTML file path (default: trajectory_dashboard.html in script dir)",
    )
    args = parser.parse_args()

    runs = []
    for d in args.run_dirs:
        path = find_analysis_file(d)
        data = load_run(path)
        runs.append(data)
        m = data["run_metadata"]
        print(f"Loaded: {m['agent_name']} ({m['model']}) — {m['resolved_count']}/{m['analyzed_count']} resolved")

    build_html(runs, args.output)


if __name__ == "__main__":
    main()
