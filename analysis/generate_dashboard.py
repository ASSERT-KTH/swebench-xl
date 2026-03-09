#!/usr/bin/env python3
"""
Generate a standalone HTML dashboard for browsing benchmark instances.
Reads ./benchmark/filtered_dataset.jsonl and outputs dashboards/benchmark_dashboard.html.
"""

import json
import html
import sys
import os


def load_instances(path: str):
    instances = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    instances.sort(key=lambda x: x["instance_id"])
    return instances


def truncate_field(value: str, max_len: int = 50000) -> tuple[str, bool]:
    if len(value) > max_len:
        return value[:max_len], True
    return value, False


def prepare_instances_for_embedding(instances):
    """Prepare instances for JSON embedding — truncate huge fields."""
    prepared = []
    for inst in instances:
        d = dict(inst)
        # pass_to_pass can be enormous; truncate for the dashboard
        val = d.get("pass_to_pass", "")
        d["pass_to_pass"], d["pass_to_pass_truncated"] = truncate_field(val, 50000)
        prepared.append(d)
    return prepared


def generate_html(instances) -> str:
    data_json = json.dumps(instances, ensure_ascii=False)
    # Escape </script> in embedded data
    data_json = data_json.replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SWE-Bench XL — Instance Dashboard</title>
<style>
:root {{
  --bg: #0f172a;
  --surface: #1e293b;
  --surface2: #334155;
  --surface3: #475569;
  --text: #e2e8f0;
  --text2: #94a3b8;
  --text3: #64748b;
  --accent: #6366f1;
  --accent-hover: #818cf8;
  --green: #22c55e;
  --green-bg: rgba(34,197,94,0.08);
  --red: #ef4444;
  --red-bg: rgba(239,68,68,0.08);
  --yellow: #eab308;
  --blue: #3b82f6;
  --cyan: #06b6d4;
  --radius: 8px;
  --sidebar-w: 320px;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  line-height: 1.6;
  height: 100vh;
  overflow: hidden;
}}

/* Layout */
.layout {{
  display: flex;
  height: 100vh;
}}

/* Sidebar */
.sidebar {{
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--surface);
  border-right: 1px solid var(--surface2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}
.sidebar-header {{
  padding: 1.25rem 1rem 0.75rem;
  border-bottom: 1px solid var(--surface2);
}}
.sidebar-header h1 {{
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.15rem;
}}
.sidebar-header .subtitle {{
  font-size: 0.78rem;
  color: var(--text3);
}}
.search-box {{
  margin: 0.75rem 1rem;
}}
.search-box input {{
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--surface2);
  color: var(--text);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}}
.search-box input:focus {{
  border-color: var(--accent);
}}
.search-box input::placeholder {{
  color: var(--text3);
}}
.instance-list {{
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem 0.5rem;
}}
.instance-list::-webkit-scrollbar {{
  width: 6px;
}}
.instance-list::-webkit-scrollbar-track {{
  background: transparent;
}}
.instance-list::-webkit-scrollbar-thumb {{
  background: var(--surface2);
  border-radius: 3px;
}}
.instance-item {{
  padding: 0.55rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.82rem;
  color: var(--text2);
  transition: background 0.15s, color 0.15s;
  margin-bottom: 2px;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}}
.instance-item:hover {{
  background: var(--surface2);
  color: var(--text);
}}
.instance-item.active {{
  background: var(--accent);
  color: #fff;
}}
.instance-item .inst-id {{
  font-weight: 600;
  font-size: 0.82rem;
}}
.instance-item .inst-title {{
  font-size: 0.73rem;
  opacity: 0.8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.instance-count {{
  padding: 0.5rem 1rem;
  font-size: 0.75rem;
  color: var(--text3);
  border-top: 1px solid var(--surface2);
}}

/* Main content */
.main {{
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}}
.main::-webkit-scrollbar {{
  width: 8px;
}}
.main::-webkit-scrollbar-track {{
  background: transparent;
}}
.main::-webkit-scrollbar-thumb {{
  background: var(--surface2);
  border-radius: 4px;
}}

/* Instance header */
.inst-header {{
  margin-bottom: 1.25rem;
}}
.inst-header h2 {{
  font-size: 1.35rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}}
.inst-header .meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.82rem;
  color: var(--text2);
}}
.inst-header .meta .badge {{
  background: var(--surface2);
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.78rem;
}}
.inst-header .meta .badge.lang {{
  background: rgba(99,102,241,0.15);
  color: var(--accent-hover);
}}
.inst-header .meta a {{
  color: var(--blue);
  text-decoration: none;
}}
.inst-header .meta a:hover {{
  text-decoration: underline;
}}

/* Tabs */
.tabs {{
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--surface2);
  margin-bottom: 1.25rem;
  overflow-x: auto;
}}
.tab {{
  padding: 0.6rem 1.2rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text2);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
  user-select: none;
}}
.tab:hover {{
  color: var(--text);
}}
.tab.active {{
  color: var(--accent-hover);
  border-bottom-color: var(--accent);
}}
.tab-content {{
  display: none;
}}
.tab-content.active {{
  display: block;
}}

/* Cards / sections */
.section {{
  background: var(--surface);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1rem;
}}
.section h3 {{
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text);
}}
.meta-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}}
.meta-item {{
  background: var(--surface2);
  border-radius: 6px;
  padding: 0.75rem 1rem;
}}
.meta-item .label {{
  font-size: 0.72rem;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}}
.meta-item .value {{
  font-size: 0.88rem;
  color: var(--text);
  word-break: break-all;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
}}

/* Diff */
.diff-container {{
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
}}
.diff-header {{
  padding: 0.65rem 1rem;
  background: var(--surface2);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.diff-stats {{
  display: flex;
  gap: 0.75rem;
  font-size: 0.78rem;
}}
.diff-stats .additions {{ color: var(--green); }}
.diff-stats .deletions {{ color: var(--red); }}
.diff-body {{
  overflow-x: auto;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.65;
}}
.diff-file-header {{
  background: rgba(99,102,241,0.1);
  padding: 0.4rem 1rem;
  color: var(--accent-hover);
  font-weight: 600;
  border-top: 1px solid var(--surface2);
}}
.diff-hunk {{
  background: rgba(99,102,241,0.05);
  padding: 0.25rem 1rem;
  color: var(--cyan);
  font-size: 0.78rem;
}}
.diff-line {{
  padding: 0 1rem;
  white-space: pre-wrap;
  word-break: break-all;
  min-height: 1.65em;
}}
.diff-line.add {{
  background: var(--green-bg);
  color: var(--green);
}}
.diff-line.del {{
  background: var(--red-bg);
  color: var(--red);
}}
.diff-line.ctx {{
  color: var(--text2);
}}

/* Issue description */
.description {{
  background: var(--surface);
  border-radius: var(--radius);
  padding: 1.25rem;
  line-height: 1.7;
  font-size: 0.9rem;
}}
.description h1, .description h2, .description h3 {{
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: var(--text);
}}
.description h1 {{ font-size: 1.3rem; }}
.description h2 {{ font-size: 1.1rem; }}
.description h3 {{ font-size: 0.95rem; }}
.description p {{
  margin-bottom: 0.75rem;
}}
.description code {{
  background: var(--surface2);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.85em;
}}
.description pre {{
  background: var(--bg);
  border: 1px solid var(--surface2);
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  margin-bottom: 0.75rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.83rem;
  line-height: 1.5;
}}
.description pre code {{
  background: transparent;
  padding: 0;
}}
.description ul, .description ol {{
  margin-left: 1.5rem;
  margin-bottom: 0.75rem;
}}
.description blockquote {{
  border-left: 3px solid var(--accent);
  padding-left: 1rem;
  color: var(--text2);
  margin-bottom: 0.75rem;
}}
.description a {{
  color: var(--blue);
  text-decoration: none;
}}
.description a:hover {{
  text-decoration: underline;
}}
.description img {{
  max-width: 100%;
  border-radius: 6px;
  margin: 0.5rem 0;
}}

/* File list */
.file-list {{
  list-style: none;
  padding: 0;
}}
.file-list li {{
  padding: 0.4rem 0.75rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.82rem;
  color: var(--text2);
  border-bottom: 1px solid var(--surface2);
}}
.file-list li:last-child {{
  border-bottom: none;
}}
.file-list li::before {{
  content: '📄 ';
}}

/* Command list */
.cmd-list {{
  list-style: none;
  padding: 0;
}}
.cmd-list li {{
  padding: 0.5rem 0.75rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.78rem;
  color: var(--cyan);
  background: var(--bg);
  border-radius: 4px;
  margin-bottom: 0.35rem;
  white-space: pre-wrap;
  word-break: break-all;
}}

/* Test list */
.test-list {{
  max-height: 400px;
  overflow-y: auto;
  background: var(--bg);
  border-radius: 6px;
  padding: 0.5rem 0;
}}
.test-list::-webkit-scrollbar {{
  width: 6px;
}}
.test-list::-webkit-scrollbar-thumb {{
  background: var(--surface2);
  border-radius: 3px;
}}
.test-item {{
  padding: 0.3rem 0.75rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.78rem;
  color: var(--text2);
  border-bottom: 1px solid rgba(51,65,85,0.5);
}}
.test-item:last-child {{
  border-bottom: none;
}}
.test-item.fail {{
  color: var(--red);
}}
.test-item.pass {{
  color: var(--green);
}}

/* Expand/Collapse */
.expand-btn {{
  display: inline-block;
  background: var(--surface2);
  color: var(--accent-hover);
  border: none;
  border-radius: 4px;
  padding: 0.35rem 0.75rem;
  font-size: 0.78rem;
  cursor: pointer;
  margin-top: 0.5rem;
}}
.expand-btn:hover {{
  background: var(--surface3);
}}

/* Nav hint */
.nav-hint {{
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  background: var(--surface);
  border: 1px solid var(--surface2);
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
  font-size: 0.72rem;
  color: var(--text3);
  z-index: 100;
}}
.nav-hint kbd {{
  background: var(--surface2);
  border: 1px solid var(--surface3);
  border-radius: 3px;
  padding: 0.1rem 0.35rem;
  font-family: inherit;
  font-size: 0.72rem;
}}

/* Empty state */
.empty {{
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text3);
}}
.empty .icon {{
  font-size: 3rem;
  margin-bottom: 1rem;
}}

/* Responsive */
@media (max-width: 768px) {{
  .layout {{
    flex-direction: column;
  }}
  .sidebar {{
    width: 100%;
    min-width: 100%;
    max-height: 40vh;
  }}
  .main {{
    padding: 1rem;
  }}
}}
</style>
</head>
<body>
<div class="layout">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-header">
      <h1>SWE-Bench XL</h1>
      <div class="subtitle">Benchmark Instance Browser</div>
    </div>
    <div class="search-box">
      <input type="text" id="search" placeholder="Search instances… (id, title)" autocomplete="off">
    </div>
    <div class="instance-list" id="instanceList"></div>
    <div class="instance-count" id="instanceCount"></div>
  </div>

  <!-- Main content -->
  <div class="main" id="mainContent">
    <div class="empty" id="emptyState">
      <div class="icon">📊</div>
      <div>Select an instance from the sidebar to view details</div>
    </div>
    <div id="instanceView" style="display:none;">
      <!-- Header -->
      <div class="inst-header" id="instHeader"></div>

      <!-- Tabs -->
      <div class="tabs" id="tabBar"></div>

      <!-- Tab content -->
      <div id="tabContents"></div>
    </div>
  </div>
</div>

<div class="nav-hint">
  <kbd>↑</kbd> <kbd>↓</kbd> navigate &nbsp;·&nbsp; <kbd>/</kbd> search
</div>

<script>
// === Embedded data ===
const INSTANCES = {data_json};

// === State ===
let currentIdx = -1;
let currentTab = 'issue';
let filteredIndices = INSTANCES.map((_, i) => i);

// === Sidebar ===
function renderSidebar() {{
  const list = document.getElementById('instanceList');
  const countEl = document.getElementById('instanceCount');
  list.innerHTML = '';
  filteredIndices.forEach(idx => {{
    const inst = INSTANCES[idx];
    const el = document.createElement('div');
    el.className = 'instance-item' + (idx === currentIdx ? ' active' : '');
    const shortId = inst.instance_id.replace('elastic__elasticsearch-', 'ES-');
    el.innerHTML = `<span class="inst-id">${{shortId}}</span><span class="inst-title">${{escHtml(inst.problem_statement_title)}}</span>`;
    el.onclick = () => selectInstance(idx);
    list.appendChild(el);
  }});
  countEl.textContent = `${{filteredIndices.length}} of ${{INSTANCES.length}} instances`;
}}

function filterInstances(query) {{
  query = query.toLowerCase();
  if (!query) {{
    filteredIndices = INSTANCES.map((_, i) => i);
  }} else {{
    filteredIndices = [];
    INSTANCES.forEach((inst, i) => {{
      if (inst.instance_id.toLowerCase().includes(query) ||
          inst.problem_statement_title.toLowerCase().includes(query)) {{
        filteredIndices.push(i);
      }}
    }});
  }}
  renderSidebar();
}}

// === Main content ===
function selectInstance(idx) {{
  currentIdx = idx;
  renderSidebar();
  renderInstance();

  // Scroll active item into view
  const active = document.querySelector('.instance-item.active');
  if (active) active.scrollIntoView({{ block: 'nearest' }});
}}

function renderInstance() {{
  if (currentIdx < 0) return;
  const inst = INSTANCES[currentIdx];

  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('instanceView').style.display = 'block';

  // Header
  const header = document.getElementById('instHeader');
  const prUrl = `https://github.com/${{inst.repo}}/pull/${{inst.pr_number}}`;
  const commitUrl = `https://github.com/${{inst.repo}}/commit/${{inst.base_commit}}`;
  header.innerHTML = `
    <h2>${{escHtml(inst.problem_statement_title)}}</h2>
    <div class="meta">
      <span class="badge">${{inst.instance_id}}</span>
      <span class="badge lang">${{inst.repo_language}}</span>
      <span class="badge">v${{inst.version}}</span>
      <span><a href="${{prUrl}}" target="_blank">PR #${{inst.pr_number}}</a></span>
      <span><a href="${{commitUrl}}" target="_blank">Base: ${{inst.base_commit.slice(0,10)}}…</a></span>
    </div>
  `;

  // Tabs
  const tabs = [
    {{ id: 'issue', label: 'Issue' }},
    {{ id: 'gold', label: 'Gold Patch' }},
    {{ id: 'test', label: 'Test Patch' }},
    {{ id: 'tests', label: 'Tests' }},
    {{ id: 'files', label: 'Files & Commands' }},
  ];
  const tabBar = document.getElementById('tabBar');
  tabBar.innerHTML = tabs.map(t =>
    `<div class="tab${{t.id === currentTab ? ' active' : ''}}" data-tab="${{t.id}}">${{t.label}}</div>`
  ).join('');
  tabBar.querySelectorAll('.tab').forEach(el => {{
    el.onclick = () => {{
      currentTab = el.dataset.tab;
      renderInstance();
    }};
  }});

  // Content
  const content = document.getElementById('tabContents');
  content.innerHTML = '';

  tabs.forEach(t => {{
    const div = document.createElement('div');
    div.className = 'tab-content' + (t.id === currentTab ? ' active' : '');
    div.innerHTML = renderTab(t.id, inst);
    content.appendChild(div);
  }});
}}

function renderTab(tabId, inst) {{
  switch(tabId) {{
    case 'issue':
      return `
        <div class="description">
          ${{renderMarkdown(inst.problem_statement_description)}}
        </div>`;

    case 'gold':
      return renderDiff(inst.patch, 'Gold Patch');

    case 'test':
      return renderDiff(inst.test_patch, 'Test Patch');

    case 'tests':
      return renderTests(inst);

    case 'files':
      return renderFiles(inst);

    default:
      return '';
  }}
}}

// === Diff renderer ===
function renderDiff(patch, title) {{
  if (!patch) return '<div class="section"><em>No patch data</em></div>';

  const lines = patch.split('\\n');
  let adds = 0, dels = 0;
  const htmlLines = [];

  lines.forEach(line => {{
    if (line.startsWith('--- ') || line.startsWith('+++ ')) {{
      htmlLines.push(`<div class="diff-file-header">${{escHtml(line)}}</div>`);
    }} else if (line.startsWith('@@')) {{
      htmlLines.push(`<div class="diff-hunk">${{escHtml(line)}}</div>`);
    }} else if (line.startsWith('+')) {{
      adds++;
      htmlLines.push(`<div class="diff-line add">${{escHtml(line)}}</div>`);
    }} else if (line.startsWith('-')) {{
      dels++;
      htmlLines.push(`<div class="diff-line del">${{escHtml(line)}}</div>`);
    }} else {{
      htmlLines.push(`<div class="diff-line ctx">${{escHtml(line)}}</div>`);
    }}
  }});

  // Count files
  const fileCount = (patch.match(/^--- a\\//gm) || []).length;

  return `
    <div class="diff-container">
      <div class="diff-header">
        <span>${{title}} — ${{fileCount}} file${{fileCount !== 1 ? 's' : ''}}</span>
        <div class="diff-stats">
          <span class="additions">+${{adds}}</span>
          <span class="deletions">−${{dels}}</span>
        </div>
      </div>
      <div class="diff-body">${{htmlLines.join('')}}</div>
    </div>`;
}}

// === Tests renderer ===
function renderTests(inst) {{
  let failTests = [];
  let passTests = [];
  try {{ failTests = JSON.parse(inst.fail_to_pass); }} catch(e) {{ failTests = [inst.fail_to_pass]; }}
  try {{ passTests = JSON.parse(inst.pass_to_pass); }} catch(e) {{ passTests = [inst.pass_to_pass]; }}

  const failHtml = failTests.map(t => `<div class="test-item fail">${{escHtml(t)}}</div>`).join('');
  const passCount = passTests.length;
  const passShown = passTests.slice(0, 100);
  const passHtml = passShown.map(t => `<div class="test-item pass">${{escHtml(t)}}</div>`).join('');
  const truncNote = passCount > 100 ? `<div style="padding:0.5rem 0.75rem;color:var(--text3);font-size:0.78rem;">…and ${{passCount - 100}} more tests</div>` : '';

  return `
    <div class="section">
      <h3>Fail to Pass (${{failTests.length}})</h3>
      <div class="test-list">${{failHtml}}</div>
    </div>
    <div class="section">
      <h3>Pass to Pass (${{passCount}})</h3>
      ${{inst.pass_to_pass_truncated ? '<div style="color:var(--yellow);font-size:0.78rem;margin-bottom:0.5rem;">⚠ List was truncated for performance</div>' : ''}}
      <div class="test-list">${{passHtml}}${{truncNote}}</div>
    </div>`;
}}

// === Files renderer ===
function renderFiles(inst) {{
  let sourceFiles = [];
  let testFiles = [];
  let gradleCmds = [];
  try {{ sourceFiles = JSON.parse(inst.source_files); }} catch(e) {{}}
  try {{ testFiles = JSON.parse(inst.selected_test_files_to_run); }} catch(e) {{}}
  try {{ gradleCmds = JSON.parse(inst.gradle_commands); }} catch(e) {{}}

  const srcHtml = sourceFiles.map(f => `<li>${{escHtml(f)}}</li>`).join('');
  const testHtml = testFiles.map(f => `<li>${{escHtml(f)}}</li>`).join('');
  const cmdHtml = gradleCmds.map(c => `<li>${{escHtml(c)}}</li>`).join('');

  return `
    <div class="section">
      <h3>Source Files (${{sourceFiles.length}})</h3>
      <ul class="file-list">${{srcHtml}}</ul>
    </div>
    <div class="section">
      <h3>Test Files (${{testFiles.length}})</h3>
      <ul class="file-list">${{testHtml}}</ul>
    </div>
    <div class="section">
      <h3>Gradle Commands (${{gradleCmds.length}})</h3>
      <ul class="cmd-list">${{cmdHtml}}</ul>
    </div>`;
}}

// === Markdown renderer (lightweight) ===
function renderMarkdown(text) {{
  if (!text) return '';
  let html = escHtml(text);

  // Code blocks (``` ... ```)
  html = html.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (_, lang, code) =>
    `<pre><code>${{code}}</code></pre>`);

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold and italic
  html = html.replace(/\\*\\*\\*(.+?)\\*\\*\\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  html = html.replace(/\\*(.+?)\\*/g, '<em>$1</em>');

  // Links
  html = html.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank">$1</a>');

  // Images
  html = html.replace(/!\\[([^\\]]*?)\\]\\(([^)]+)\\)/g, '<img src="$2" alt="$1">');

  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr>');

  // Unordered lists
  html = html.replace(/^[\\*\\-] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\\/li>\\n?)+)/g, '<ul>$1</ul>');

  // Paragraphs — wrap lines that aren't already in tags
  html = html.replace(/^(?!<[hupboa\\-lr])(\\S.+)$/gm, '<p>$1</p>');

  // Clean up extra newlines
  html = html.replace(/\\n{{2,}}/g, '\\n');

  return html;
}}

// === Utilities ===
function escHtml(s) {{
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

// === Keyboard navigation ===
document.addEventListener('keydown', (e) => {{
  // Don't intercept when typing in search
  if (document.activeElement.id === 'search' && e.key !== 'Escape') return;

  if (e.key === 'ArrowDown' || e.key === 'j') {{
    e.preventDefault();
    const pos = filteredIndices.indexOf(currentIdx);
    if (pos < filteredIndices.length - 1) {{
      selectInstance(filteredIndices[pos + 1]);
    }} else if (currentIdx < 0 && filteredIndices.length > 0) {{
      selectInstance(filteredIndices[0]);
    }}
  }} else if (e.key === 'ArrowUp' || e.key === 'k') {{
    e.preventDefault();
    const pos = filteredIndices.indexOf(currentIdx);
    if (pos > 0) {{
      selectInstance(filteredIndices[pos - 1]);
    }}
  }} else if (e.key === '/') {{
    e.preventDefault();
    document.getElementById('search').focus();
  }} else if (e.key === 'Escape') {{
    document.getElementById('search').blur();
  }}
}});

// === Search handler ===
document.getElementById('search').addEventListener('input', (e) => {{
  filterInstances(e.target.value);
}});

// === Init ===
renderSidebar();
if (INSTANCES.length > 0) {{
  selectInstance(0);
}}
</script>
</body>
</html>"""


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    input_path = os.path.join(repo_root, "benchmark", "filtered_dataset.jsonl")
    output_path = os.path.join(repo_root, "dashboards", "benchmark_dashboard.html")

    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Reading instances from {input_path}...")
    instances = load_instances(input_path)
    print(f"Loaded {len(instances)} instances")

    prepared = prepare_instances_for_embedding(instances)
    html_content = generate_html(prepared)

    with open(output_path, "w") as f:
        f.write(html_content)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Generated {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
