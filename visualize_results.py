"""
Visualize PR analysis results as a self-contained HTML report.
Reads the JSON output from analyze_prs.py and generates an HTML file.
"""

import json
import sys
import html
import statistics
from collections import Counter

INPUT_FILE = "pr_analysis_results_test.json"
OUTPUT_FILE = "report.html"


def load_results(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helper: build a horizontal bar chart as an HTML snippet
# ---------------------------------------------------------------------------
def bar_chart(counts: dict, color: str = "#6366f1") -> str:
    if not counts:
        return "<p>No data</p>"
    max_val = max(counts.values()) or 1
    rows = []
    for label, val in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        pct = val / max_val * 100
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{html.escape(str(label))}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'
            f'<span class="bar-value">{val}</span>'
            f'</div>'
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Helper: summary card
# ---------------------------------------------------------------------------
def card(title: str, value, subtitle: str = "") -> str:
    sub = f'<div class="card-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="card">'
        f'<div class="card-value">{html.escape(str(value))}</div>'
        f'<div class="card-title">{html.escape(title)}</div>'
        f'{sub}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Build the full HTML
# ---------------------------------------------------------------------------
def generate_html(results: list) -> str:
    n = len(results)
    if n == 0:
        return "<html><body><h1>No results to display</h1></body></html>"

    # ---- Compute stats ----
    suitable = sum(1 for r in results if r.get("benchmark_verdict", {}).get("is_suitable", False))
    difficulties = [r.get("benchmark_verdict", {}).get("difficulty_score", 0) for r in results]
    difficulties_valid = [d for d in difficulties if d > 0]
    avg_diff = sum(difficulties_valid) / len(difficulties_valid) if difficulties_valid else 0

    categories = Counter(r.get("category", "unknown") for r in results)
    challenges = Counter(r.get("benchmark_verdict", {}).get("primary_challenge", "unknown") for r in results)
    ctx_deps = Counter(r.get("complexity_analysis", {}).get("context_dependency", "unknown") for r in results)
    scopes = Counter(r.get("complexity_analysis", {}).get("scope", "unknown") for r in results)
    localizations = Counter(r.get("complexity_analysis", {}).get("localization", "unknown") for r in results)
    test_types = Counter(r.get("verifiability_audit", {}).get("test_type", "none") for r in results)

    diff_dist = Counter()
    for d in difficulties_valid:
        if d <= 2:
            diff_dist["1-2 Easy"] += 1
        elif d <= 3:
            diff_dist["3 Medium"] += 1
        else:
            diff_dist["4-5 Hard"] += 1

    nav_req = sum(1 for r in results if r.get("large_codebase_factors", {}).get("navigation_step_required", False))
    pat_req = sum(1 for r in results if r.get("large_codebase_factors", {}).get("pattern_matching_required", False))
    multi_file = sum(1 for r in results if r.get("complexity_analysis", {}).get("multi_file_logic", False))
    has_tests = sum(1 for r in results if r.get("verifiability_audit", {}).get("has_tests", False))
    self_cont = sum(1 for r in results if r.get("verifiability_audit", {}).get("self_contained_issue", False))
    breaking_high = sum(1 for r in results if r.get("large_codebase_factors", {}).get("breaking_change_risk") == "high")

    # ---- Raw PR descriptive stats ----
    files_list = [r.get("files_changed", 0) for r in results]
    adds_list = [r.get("additions", 0) for r in results]
    dels_list = [r.get("deletions", 0) for r in results]
    churn_list = [a + d for a, d in zip(adds_list, dels_list)]
    unique_repos = len(set(r.get("repo", "") for r in results))

    def stat_summary(vals):
        if not vals:
            return {"avg": 0, "med": 0, "min": 0, "max": 0, "total": 0}
        return {
            "avg": statistics.mean(vals),
            "med": statistics.median(vals),
            "min": min(vals),
            "max": max(vals),
            "total": sum(vals),
        }

    files_s = stat_summary(files_list)
    adds_s = stat_summary(adds_list)
    dels_s = stat_summary(dels_list)
    churn_s = stat_summary(churn_list)

    # PR size buckets (by total churn)
    size_dist = Counter()
    for c in churn_list:
        if c < 50:
            size_dist["XS (<50)"] += 1
        elif c < 200:
            size_dist["S (50-199)"] += 1
        elif c < 500:
            size_dist["M (200-499)"] += 1
        elif c < 1000:
            size_dist["L (500-999)"] += 1
        else:
            size_dist["XL (1000+)"] += 1

    # ---- PR data as JSON for client-side table ----
    table_data = []
    for r in results:
        verdict = r.get("benchmark_verdict", {})
        complexity = r.get("complexity_analysis", {})
        lcf = r.get("large_codebase_factors", {})
        verify = r.get("verifiability_audit", {})
        table_data.append({
            "pr_number": r.get("pr_number", "?"),
            "pr_url": r.get("pr_url", "#"),
            "repo": r.get("repo", ""),
            "title": r.get("title", "")[:80],
            "category": r.get("category", ""),
            "difficulty": verdict.get("difficulty_score", 0),
            "challenge": verdict.get("primary_challenge", ""),
            "suitable": bool(verdict.get("is_suitable", False)),
            "rejection_reason": str(verdict.get("rejection_reason") or "") if not verdict.get("is_suitable", False) else "",
            "files_changed": r.get("files_changed", 0),
            "additions": r.get("additions", 0),
            "deletions": r.get("deletions", 0),
            "has_tests": bool(verify.get("has_tests", False)),
            "self_contained": bool(verify.get("self_contained_issue", False)),
            "navigation_required": bool(lcf.get("navigation_step_required", False)),
            "multi_file_logic": bool(complexity.get("multi_file_logic", False)),
            "context_dependency": complexity.get("context_dependency", "low"),
            "scope": complexity.get("scope", ""),
            "localization": complexity.get("localization", ""),
            "test_type": verify.get("test_type", "none"),
        })
    table_data_json = json.dumps(table_data, ensure_ascii=False)

    # ---- Collect unique values for filter dropdowns ----
    unique_categories = sorted(set(d["category"] for d in table_data if d["category"]))
    unique_challenges = sorted(set(d["challenge"] for d in table_data if d["challenge"]))
    unique_repos = sorted(set(d["repo"] for d in table_data if d["repo"]))

    def options_html(values):
        return "\n".join(f'<option value="{html.escape(v)}">{html.escape(v)}</option>' for v in values)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PR Benchmark Analysis Report</title>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
    --text: #e2e8f0; --text2: #94a3b8; --accent: #6366f1;
    --green: #22c55e; --red: #ef4444; --yellow: #eab308; --blue: #3b82f6;
    --radius: 8px;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 2rem; line-height: 1.5; }}
  h1 {{ font-size: 1.8rem; margin-bottom: .25rem; }}
  h2 {{ font-size: 1.2rem; margin-bottom: 1rem; color: var(--text2); border-bottom: 1px solid var(--surface2); padding-bottom: .5rem; }}
  .subtitle {{ color: var(--text2); margin-bottom: 2rem; }}

  /* Cards */
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: var(--surface); border-radius: var(--radius); padding: 1.25rem; text-align: center; }}
  .card-value {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .card-title {{ font-size: .85rem; color: var(--text2); margin-top: .25rem; }}
  .card-sub {{ font-size: .75rem; color: var(--text2); }}

  /* Sections */
  .section {{ background: var(--surface); border-radius: var(--radius); padding: 1.5rem; margin-bottom: 1.5rem; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
  @media (max-width: 800px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}

  /* Bar chart */
  .bar-row {{ display: flex; align-items: center; margin-bottom: .4rem; }}
  .bar-label {{ width: 130px; font-size: .85rem; color: var(--text2); flex-shrink: 0; text-align: right; padding-right: .75rem; }}
  .bar-track {{ flex: 1; background: var(--surface2); border-radius: 4px; height: 20px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; transition: width .3s; }}
  .bar-value {{ width: 40px; text-align: right; font-size: .85rem; font-weight: 600; padding-left: .5rem; }}

  /* Table controls */
  .table-controls {{ display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1rem; align-items: center; }}
  .table-controls input[type="text"] {{
    background: var(--surface2); border: 1px solid var(--surface2); color: var(--text);
    border-radius: 6px; padding: .45rem .75rem; font-size: .85rem; width: 240px;
  }}
  .table-controls input[type="text"]:focus {{ outline: none; border-color: var(--accent); }}
  .table-controls select {{
    background: var(--surface2); border: 1px solid var(--surface2); color: var(--text);
    border-radius: 6px; padding: .45rem .5rem; font-size: .85rem; cursor: pointer;
  }}
  .table-controls select:focus {{ outline: none; border-color: var(--accent); }}
  .table-info {{ font-size: .8rem; color: var(--text2); margin-left: auto; }}

  /* Table */
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
  th {{
    text-align: left; padding: .6rem .75rem; color: var(--text2);
    border-bottom: 2px solid var(--surface2); white-space: nowrap; cursor: pointer; user-select: none;
  }}
  th:hover {{ color: var(--text); }}
  th .sort-arrow {{ font-size: .7rem; margin-left: .3rem; opacity: .4; }}
  th.sort-active .sort-arrow {{ opacity: 1; color: var(--accent); }}
  td {{ padding: .6rem .75rem; border-bottom: 1px solid var(--surface2); }}
  tr:hover td {{ background: rgba(99,102,241,.07); }}
  a {{ color: var(--blue); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* Badges */
  .badge {{ padding: 2px 8px; border-radius: 4px; font-size: .75rem; font-weight: 600; }}
  .badge-yes {{ background: rgba(34,197,94,.15); color: var(--green); }}
  .badge-no {{ background: rgba(239,68,68,.15); color: var(--red); }}

  /* Pagination */
  .pagination {{ display: flex; align-items: center; gap: .5rem; margin-top: 1rem; font-size: .85rem; }}
  .pagination button {{
    background: var(--surface2); border: none; color: var(--text); border-radius: 6px;
    padding: .4rem .75rem; cursor: pointer; font-size: .8rem;
  }}
  .pagination button:hover:not(:disabled) {{ background: var(--accent); }}
  .pagination button:disabled {{ opacity: .3; cursor: default; }}
  .pagination .page-info {{ color: var(--text2); }}

  /* Descriptive stats table */
  .desc-stats {{ font-size: .85rem; }}
  .desc-stats th {{ cursor: default; border-bottom: 1px solid var(--surface2); }}
  .desc-stats th:first-child {{ text-align: left; }}
  .desc-stats th:not(:first-child), .desc-stats td:not(:first-child) {{ text-align: right; }}
  .desc-stats td:first-child {{ color: var(--text2); }}
  .desc-stats td {{ font-variant-numeric: tabular-nums; }}

  /* Boolean stats */
  .bool-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }}
  .bool-stat {{ display: flex; justify-content: space-between; background: var(--surface2); border-radius: 6px; padding: .5rem .75rem; font-size: .85rem; }}
  .bool-stat .val {{ font-weight: 700; }}
</style>
</head>
<body>
<h1>PR Benchmark Analysis Report</h1>
<p class="subtitle">{n} pull requests analyzed</p>

<!-- Summary Cards -->
<div class="cards">
  {card("Total PRs", n)}
  {card("Suitable", f"{suitable}/{n}", f"{suitable/n*100:.0f}%")}
  {card("Avg Difficulty", f"{avg_diff:.1f}/5")}
  {card("Has Tests", f"{has_tests}/{n}", f"{has_tests/n*100:.0f}%")}
  {card("Self-Contained", f"{self_cont}/{n}", f"{self_cont/n*100:.0f}%")}
  {card("Navigation Req.", f"{nav_req}/{n}", f"{nav_req/n*100:.0f}%")}
</div>

<!-- PR Descriptive Stats -->
<div class="grid-2">
  <div class="section">
    <h2>PR Size Distribution (lines changed)</h2>
    {bar_chart(dict(size_dist), "#8b5cf6")}
  </div>
  <div class="section">
    <h2>Dataset Overview</h2>
    <div class="stat-table">
      <table class="desc-stats">
        <thead><tr><th></th><th>Avg</th><th>Median</th><th>Min</th><th>Max</th><th>Total</th></tr></thead>
        <tbody>
          <tr><td>Files changed</td><td>{files_s['avg']:.1f}</td><td>{files_s['med']:.0f}</td><td>{files_s['min']}</td><td>{files_s['max']}</td><td>{files_s['total']:,}</td></tr>
          <tr><td>Additions</td><td>{adds_s['avg']:.1f}</td><td>{adds_s['med']:.0f}</td><td>{adds_s['min']}</td><td>{adds_s['max']}</td><td>{adds_s['total']:,}</td></tr>
          <tr><td>Deletions</td><td>{dels_s['avg']:.1f}</td><td>{dels_s['med']:.0f}</td><td>{dels_s['min']}</td><td>{dels_s['max']}</td><td>{dels_s['total']:,}</td></tr>
          <tr><td>Total churn</td><td>{churn_s['avg']:.1f}</td><td>{churn_s['med']:.0f}</td><td>{churn_s['min']}</td><td>{churn_s['max']}</td><td>{churn_s['total']:,}</td></tr>
        </tbody>
      </table>
      <div style="margin-top:.75rem;font-size:.85rem;color:var(--text2)">Unique repos: <strong style="color:var(--text)">{unique_repos}</strong></div>
    </div>
  </div>
</div>

<!-- Charts row -->
<div class="grid-2">
  <div class="section">
    <h2>Categories</h2>
    {bar_chart(dict(categories), "#6366f1")}
  </div>
  <div class="section">
    <h2>Primary Challenge</h2>
    {bar_chart(dict(challenges), "#3b82f6")}
  </div>
</div>

<div class="grid-2">
  <div class="section">
    <h2>Difficulty Distribution</h2>
    {bar_chart(dict(diff_dist), "#eab308")}
  </div>
  <div class="section">
    <h2>Context Dependency</h2>
    {bar_chart(dict(ctx_deps), "#22c55e")}
  </div>
</div>

<div class="grid-2">
  <div class="section">
    <h2>Scope</h2>
    {bar_chart(dict(scopes), "#14b8a6")}
  </div>
  <div class="section">
    <h2>Localization</h2>
    {bar_chart(dict(localizations), "#f43f5e")}
  </div>
</div>

<div class="grid-2">
  <div class="section">
    <h2>Test Types</h2>
    {bar_chart(dict(test_types), "#f97316")}
  </div>
  <div class="section">
    <h2>Large Codebase Factors</h2>
    <div class="bool-grid">
      <div class="bool-stat"><span>Navigation required</span><span class="val">{nav_req}/{n}</span></div>
      <div class="bool-stat"><span>Pattern matching</span><span class="val">{pat_req}/{n}</span></div>
      <div class="bool-stat"><span>Multi-file logic</span><span class="val">{multi_file}/{n}</span></div>
      <div class="bool-stat"><span>High breaking risk</span><span class="val">{breaking_high}/{n}</span></div>
    </div>
  </div>
</div>

<!-- PR Table -->
<div class="section">
  <h2>All Pull Requests</h2>

  <div class="table-controls">
    <select id="filter-preset">
      <option value="">Quick filter...</option>
      <option value="candidates">Benchmark candidates</option>
      <option value="hard_nav">Hard navigation tasks</option>
      <option value="needs_review">Needs review (borderline)</option>
    </select>
    <input type="text" id="search" placeholder="Search PR title, repo...">
    <select id="filter-category"><option value="">All categories</option>{options_html(unique_categories)}</select>
    <select id="filter-challenge"><option value="">All challenges</option>{options_html(unique_challenges)}</select>
    <select id="filter-suitable"><option value="">All</option><option value="true">Suitable</option><option value="false">Not suitable</option></select>
    <select id="filter-repo"><option value="">All repos</option>{options_html(unique_repos)}</select>
    <span class="table-info" id="table-info"></span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-key="pr_number">PR <span class="sort-arrow">&#9650;</span></th>
          <th data-key="repo">Repo <span class="sort-arrow">&#9650;</span></th>
          <th data-key="title">Title <span class="sort-arrow">&#9650;</span></th>
          <th data-key="category">Category <span class="sort-arrow">&#9650;</span></th>
          <th data-key="difficulty">Diff. <span class="sort-arrow">&#9650;</span></th>
          <th data-key="challenge">Challenge <span class="sort-arrow">&#9650;</span></th>
          <th data-key="scope">Scope <span class="sort-arrow">&#9650;</span></th>
          <th data-key="localization">Localization <span class="sort-arrow">&#9650;</span></th>
          <th data-key="suitable">Suitable <span class="sort-arrow">&#9650;</span></th>
          <th data-key="rejection_reason">Rejection Reason <span class="sort-arrow">&#9650;</span></th>
          <th data-key="has_tests">Tests <span class="sort-arrow">&#9650;</span></th>
          <th data-key="test_type">Test Type <span class="sort-arrow">&#9650;</span></th>
          <th data-key="files_changed">Files <span class="sort-arrow">&#9650;</span></th>
          <th data-key="additions">Changes <span class="sort-arrow">&#9650;</span></th>
        </tr>
      </thead>
      <tbody id="table-body"></tbody>
    </table>
  </div>

  <div class="pagination">
    <button id="btn-first">&laquo;</button>
    <button id="btn-prev">&lsaquo; Prev</button>
    <span class="page-info" id="page-info"></span>
    <button id="btn-next">Next &rsaquo;</button>
    <button id="btn-last">&raquo;</button>
  </div>
</div>

<script>
(function() {{
  const DATA = {table_data_json};
  const PER_PAGE = 50;
  let filtered = DATA.slice();
  let sortKey = null;
  let sortAsc = true;
  let page = 0;

  const $ = id => document.getElementById(id);
  const tbody = $('table-body');
  const searchEl = $('search');
  const filterCat = $('filter-category');
  const filterCh = $('filter-challenge');
  const filterSuit = $('filter-suitable');
  const filterRepo = $('filter-repo');
  const filterPreset = $('filter-preset');

  const PRESETS = {{
    candidates: r => r.suitable && r.has_tests && r.self_contained,
    hard_nav: r => r.difficulty >= 4 && r.navigation_required && r.multi_file_logic,
    needs_review: r => !r.suitable && r.difficulty >= 3,
  }};

  function escapeHtml(s) {{
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }}

  function resetManualFilters() {{
    searchEl.value = '';
    filterCat.value = '';
    filterCh.value = '';
    filterSuit.value = '';
    filterRepo.value = '';
  }}

  function applyFilters() {{
    const preset = filterPreset.value;
    const q = searchEl.value.toLowerCase();
    const cat = filterCat.value;
    const ch = filterCh.value;
    const suit = filterSuit.value;
    const repo = filterRepo.value;

    filtered = DATA.filter(r => {{
      if (preset && PRESETS[preset] && !PRESETS[preset](r)) return false;
      if (q && !r.title.toLowerCase().includes(q) && !r.repo.toLowerCase().includes(q) && !String(r.pr_number).includes(q)) return false;
      if (cat && r.category !== cat) return false;
      if (ch && r.challenge !== ch) return false;
      if (suit === 'true' && !r.suitable) return false;
      if (suit === 'false' && r.suitable) return false;
      if (repo && r.repo !== repo) return false;
      return true;
    }});

    if (sortKey) applySort();
    page = 0;
    render();
  }}

  function applySort() {{
    filtered.sort((a, b) => {{
      let va = a[sortKey], vb = b[sortKey];
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (typeof va === 'boolean') {{ va = va ? 1 : 0; vb = vb ? 1 : 0; }}
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    }});
  }}

  function render() {{
    const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
    if (page >= totalPages) page = totalPages - 1;
    const start = page * PER_PAGE;
    const slice = filtered.slice(start, start + PER_PAGE);

    let html = '';
    for (const r of slice) {{
      const badge = r.suitable
        ? '<span class="badge badge-yes">Yes</span>'
        : '<span class="badge badge-no">No</span>';
      html += '<tr>'
        + '<td><a href="' + escapeHtml(r.pr_url) + '" target="_blank">#' + r.pr_number + '</a></td>'
        + '<td>' + escapeHtml(r.repo) + '</td>'
        + '<td>' + escapeHtml(r.title) + '</td>'
        + '<td>' + escapeHtml(r.category) + '</td>'
        + '<td>' + r.difficulty + '</td>'
        + '<td>' + escapeHtml(r.challenge) + '</td>'
        + '<td>' + escapeHtml(r.scope) + '</td>'
        + '<td>' + escapeHtml(r.localization) + '</td>'
        + '<td>' + badge + '</td>'
        + '<td>' + escapeHtml(r.rejection_reason) + '</td>'
        + '<td>' + (r.has_tests ? '<span class="badge badge-yes">Yes</span>' : '<span class="badge badge-no">No</span>') + '</td>'
        + '<td>' + escapeHtml(r.test_type) + '</td>'
        + '<td>' + r.files_changed + '</td>'
        + '<td>+' + r.additions + ' / -' + r.deletions + '</td>'
        + '</tr>';
    }}
    tbody.innerHTML = html;

    $('table-info').textContent = filtered.length + ' of ' + DATA.length + ' PRs';
    $('page-info').textContent = 'Page ' + (page + 1) + ' of ' + totalPages;
    $('btn-first').disabled = page === 0;
    $('btn-prev').disabled = page === 0;
    $('btn-next').disabled = page >= totalPages - 1;
    $('btn-last').disabled = page >= totalPages - 1;
  }}

  // Sort on header click
  document.querySelectorAll('th[data-key]').forEach(th => {{
    th.addEventListener('click', () => {{
      const key = th.dataset.key;
      if (sortKey === key) {{ sortAsc = !sortAsc; }}
      else {{ sortKey = key; sortAsc = true; }}

      document.querySelectorAll('th[data-key]').forEach(h => {{
        h.classList.remove('sort-active');
        h.querySelector('.sort-arrow').innerHTML = '&#9650;';
      }});
      th.classList.add('sort-active');
      th.querySelector('.sort-arrow').innerHTML = sortAsc ? '&#9650;' : '&#9660;';

      applySort();
      page = 0;
      render();
    }});
  }});

  // Filter listeners
  let debounceTimer;
  searchEl.addEventListener('input', () => {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyFilters, 200);
  }});
  filterPreset.addEventListener('change', () => {{
    resetManualFilters();
    applyFilters();
  }});
  filterCat.addEventListener('change', () => {{ filterPreset.value = ''; applyFilters(); }});
  filterCh.addEventListener('change', () => {{ filterPreset.value = ''; applyFilters(); }});
  filterSuit.addEventListener('change', () => {{ filterPreset.value = ''; applyFilters(); }});
  filterRepo.addEventListener('change', () => {{ filterPreset.value = ''; applyFilters(); }});

  // Pagination
  $('btn-first').addEventListener('click', () => {{ page = 0; render(); }});
  $('btn-prev').addEventListener('click', () => {{ page--; render(); }});
  $('btn-next').addEventListener('click', () => {{ page++; render(); }});
  $('btn-last').addEventListener('click', () => {{ page = Math.ceil(filtered.length / PER_PAGE) - 1; render(); }});

  // Initial render
  render();
}})();
</script>

</body>
</html>"""


def main():
    input_file = INPUT_FILE
    output_file = OUTPUT_FILE

    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]

    print(f"Loading results from {input_file}...")
    results = load_results(input_file)
    print(f"Loaded {len(results)} PRs")

    html_content = generate_html(results)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Report written to {output_file}")


if __name__ == "__main__":
    main()
