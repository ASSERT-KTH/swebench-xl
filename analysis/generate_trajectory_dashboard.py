#!/usr/bin/env python3
"""
Generate a standalone HTML dashboard for visualizing agent trajectories.

Usage:
    python generate_trajectory_dashboard.py <run_dir> [<run_dir2> ...]
    python generate_trajectory_dashboard.py ./re-run-with-wrapper ./full-trajectories

Reads Harbor run directories containing trial results and generates
trajectory_dashboard.html in the dashboards/ directory.
"""

import json
import os
import sys
import glob as globmod
from pathlib import Path

def load_run(run_dir: str) -> dict:
    """Load a single run directory (e.g. re-run-with-wrapper/)."""
    run_dir = os.path.abspath(run_dir)
    run_name = os.path.basename(run_dir)

    # Load run-level metadata
    run_config = {}
    config_path = os.path.join(run_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            run_config = json.load(f)

    run_result = {}
    result_path = os.path.join(run_dir, "result.json")
    if os.path.exists(result_path):
        with open(result_path) as f:
            run_result = json.load(f)

    # Find trial directories
    trials = []
    for entry in sorted(os.listdir(run_dir)):
        trial_dir = os.path.join(run_dir, entry)
        if not os.path.isdir(trial_dir):
            continue
        trial_result_path = os.path.join(trial_dir, "result.json")
        if not os.path.exists(trial_result_path):
            continue

        trial = load_trial(trial_dir, entry)
        if trial:
            trials.append(trial)

    return {
        "run_name": run_name,
        "config": run_config,
        "result": run_result,
        "trials": trials,
    }


def load_trial(trial_dir: str, trial_name: str):
    """Load a single trial directory."""
    # Trial result
    result_path = os.path.join(trial_dir, "result.json")
    try:
        with open(result_path) as f:
            result = json.load(f)
    except Exception:
        return None

    # Extract key info
    task_name = result.get("task_name", trial_name.rsplit("__", 1)[0])
    reward_str = "?"
    reward_path = os.path.join(trial_dir, "verifier", "reward.txt")
    if os.path.exists(reward_path):
        with open(reward_path) as f:
            reward_str = f.read().strip()

    # Agent config
    agent_config = result.get("config", {}).get("agent", {})
    agent_name = agent_config.get("name", "unknown")
    model_name = agent_config.get("model_name", "unknown")

    # Load trajectory (prefer ATIF format)
    trajectory = None
    traj_path = os.path.join(trial_dir, "agent", "trajectory.json")
    if os.path.exists(traj_path):
        try:
            with open(traj_path) as f:
                trajectory = json.load(f)
        except Exception:
            pass

    # Fallback: load mini-swe-agent format
    raw_messages = None
    raw_info = None
    raw_traj_files = globmod.glob(
        os.path.join(trial_dir, "agent", "*.trajectory.json")
    )
    for rtf in raw_traj_files:
        if rtf != traj_path:
            try:
                with open(rtf) as f:
                    raw = json.load(f)
                raw_messages = raw.get("messages", [])
                raw_info = raw.get("info", {})
            except Exception:
                pass
            break

    # Verifier output
    verifier = {}
    verifier_output_path = os.path.join(trial_dir, "verifier", "output.json")
    if os.path.exists(verifier_output_path):
        try:
            with open(verifier_output_path) as f:
                verifier["output"] = json.load(f)
        except Exception:
            pass

    test_stdout_path = os.path.join(trial_dir, "verifier", "test-stdout.txt")
    if os.path.exists(test_stdout_path):
        try:
            with open(test_stdout_path) as f:
                content = f.read()
                # Truncate if huge
                if len(content) > 100000:
                    content = content[:100000] + "\n\n... [TRUNCATED] ..."
                verifier["test_stdout"] = content
        except Exception:
            pass

    # Build steps from ATIF trajectory
    MAX_OBS = 8000  # truncate long observations to keep file size sane
    MAX_MSG = 15000
    steps = []
    if trajectory and "steps" in trajectory:
        for s in trajectory["steps"]:
            obs = _extract_observation(s.get("observation"))
            if len(obs) > MAX_OBS:
                obs = obs[:MAX_OBS] + "\n\n... [truncated for dashboard] ..."
            msg = s.get("message", "")
            if len(msg) > MAX_MSG:
                msg = msg[:MAX_MSG] + "\n\n... [truncated for dashboard] ..."
            step = {
                "step_id": s.get("step_id", 0),
                "source": s.get("source", "unknown"),
                "message": msg,
                "tool_calls": s.get("tool_calls", []),
                "observation": obs,
                "metrics": s.get("metrics"),
            }
            steps.append(step)
    elif raw_messages:
        # Convert raw messages to step-like format
        step_id = 0
        for msg in raw_messages:
            step_id += 1
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    p.get("text", str(p)) for p in content if isinstance(p, dict)
                )
            if len(content) > MAX_MSG:
                content = content[:MAX_MSG] + "\n\n... [truncated for dashboard] ..."

            source = {"system": "system", "user": "user", "assistant": "agent"}.get(
                role, role
            )

            step = {
                "step_id": step_id,
                "source": source,
                "message": content,
                "tool_calls": [],
                "observation": "",
                "metrics": None,
            }
            steps.append(step)

    # Final metrics
    final_metrics = {}
    if trajectory:
        final_metrics = trajectory.get("final_metrics", {})
    elif raw_info:
        model_stats = raw_info.get("model_stats", {})
        final_metrics = {
            "total_cost_usd": model_stats.get("instance_cost"),
            "api_calls": model_stats.get("api_calls"),
        }

    # Exit status
    exit_status = ""
    if raw_info:
        exit_status = raw_info.get("exit_status", "")

    return {
        "trial_name": trial_name,
        "task_name": task_name,
        "agent_name": agent_name,
        "model_name": model_name,
        "reward": reward_str,
        "exit_status": exit_status,
        "steps": steps,
        "step_count": len(steps),
        "final_metrics": final_metrics,
        "verifier": verifier,
    }


def _extract_observation(obs) -> str:
    """Extract observation text from various formats."""
    if obs is None:
        return ""
    if isinstance(obs, str):
        return obs
    if isinstance(obs, dict):
        if "results" in obs:
            parts = []
            for r in obs["results"]:
                if isinstance(r, dict):
                    parts.append(r.get("content", str(r)))
                else:
                    parts.append(str(r))
            return "\n".join(parts)
        return json.dumps(obs, indent=2)
    if isinstance(obs, list):
        parts = []
        for r in obs:
            if isinstance(r, dict):
                parts.append(r.get("content", str(r)))
            else:
                parts.append(str(r))
        return "\n".join(parts)
    return str(obs)


def generate_html(runs) -> str:
    data_json = json.dumps(runs, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")

    return (
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SWE-Bench XL — Trajectory Viewer</title>
<style>
:root {
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
  --green-bg: rgba(34,197,94,0.12);
  --red: #ef4444;
  --red-bg: rgba(239,68,68,0.12);
  --yellow: #eab308;
  --blue: #3b82f6;
  --cyan: #06b6d4;
  --orange: #f97316;
  --radius: 8px;
  --sidebar-w: 300px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  line-height: 1.6;
  overflow: hidden;
}

/* Layout */
.layout { display: flex; height: 100vh; }

/* Sidebar */
.sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--surface);
  border-right: 1px solid var(--surface2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  padding: 1.25rem 1rem 0.75rem;
  border-bottom: 1px solid var(--surface2);
}
.sidebar-header h1 { font-size: 1.05rem; font-weight: 700; }
.sidebar-header .subtitle { font-size: 0.75rem; color: var(--text3); }
.run-selector {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--surface2);
}
.run-selector select {
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--surface2);
  color: var(--text);
  border-radius: 6px;
  padding: 0.45rem 0.5rem;
  font-size: 0.82rem;
  cursor: pointer;
  outline: none;
}
.run-selector select:focus { border-color: var(--accent); }
.search-box { padding: 0.5rem 0.75rem; }
.search-box input {
  width: 100%;
  background: var(--surface2);
  border: 1px solid var(--surface2);
  color: var(--text);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.82rem;
  outline: none;
}
.search-box input:focus { border-color: var(--accent); }
.search-box input::placeholder { color: var(--text3); }

/* Run summary bar */
.run-summary {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--surface2);
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
}
.run-summary .stat {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.run-summary .stat .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.run-summary .stat .dot.pass { background: var(--green); }
.run-summary .stat .dot.fail { background: var(--red); }

.trial-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem 0.5rem;
}
.trial-list::-webkit-scrollbar { width: 6px; }
.trial-list::-webkit-scrollbar-thumb { background: var(--surface2); border-radius: 3px; }

.trial-item {
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.15s;
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.trial-item:hover { background: var(--surface2); }
.trial-item.active { background: var(--accent); }
.trial-item .reward-badge {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  flex-shrink: 0;
}
.trial-item .reward-badge.pass { background: var(--green-bg); color: var(--green); border: 1.5px solid var(--green); }
.trial-item .reward-badge.fail { background: var(--red-bg); color: var(--red); border: 1.5px solid var(--red); }
.trial-item .reward-badge.unknown { background: var(--surface2); color: var(--text3); border: 1.5px solid var(--text3); }
.trial-item .trial-info { overflow: hidden; }
.trial-item .trial-id { font-size: 0.8rem; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.trial-item.active .trial-id { color: #fff; }
.trial-item .trial-meta { font-size: 0.7rem; color: var(--text3); }
.trial-item.active .trial-meta { color: rgba(255,255,255,0.7); }
.trial-item.active .reward-badge.pass { background: rgba(34,197,94,0.3); color: #fff; border-color: rgba(255,255,255,0.4); }
.trial-item.active .reward-badge.fail { background: rgba(239,68,68,0.3); color: #fff; border-color: rgba(255,255,255,0.4); }

.sidebar-footer {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--surface2);
  font-size: 0.72rem;
  color: var(--text3);
}

/* Main */
.main {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.main::-webkit-scrollbar { width: 8px; }
.main::-webkit-scrollbar-thumb { background: var(--surface2); border-radius: 4px; }

/* Trial header */
.trial-header {
  padding: 1.25rem 2rem 1rem;
  border-bottom: 1px solid var(--surface2);
  background: var(--surface);
  flex-shrink: 0;
}
.trial-header h2 { font-size: 1.2rem; font-weight: 700; margin-bottom: 0.3rem; }
.trial-header .meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  font-size: 0.8rem;
  color: var(--text2);
  align-items: center;
}
.badge {
  background: var(--surface2);
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  font-size: 0.75rem;
}
.badge.pass { background: var(--green-bg); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
.badge.fail { background: var(--red-bg); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }
.badge.model { background: rgba(6,182,212,0.1); color: var(--cyan); }
.badge.cost { background: rgba(249,115,22,0.1); color: var(--orange); }

/* Content tabs */
.content-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--surface2);
  background: var(--surface);
  padding: 0 2rem;
  flex-shrink: 0;
}
.c-tab {
  padding: 0.55rem 1.1rem;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text2);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
  user-select: none;
}
.c-tab:hover { color: var(--text); }
.c-tab.active { color: var(--accent-hover); border-bottom-color: var(--accent); }

.tab-panel { display: none; flex: 1; overflow-y: auto; padding: 1.25rem 2rem; }
.tab-panel.active { display: block; }
.tab-panel::-webkit-scrollbar { width: 8px; }
.tab-panel::-webkit-scrollbar-thumb { background: var(--surface2); border-radius: 4px; }

/* Trajectory view */
.trajectory {
  max-width: 900px;
}
.step {
  margin-bottom: 1rem;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--surface2);
}
.step-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.85rem;
  background: var(--surface);
  font-size: 0.78rem;
  cursor: pointer;
  user-select: none;
}
.step-header:hover { background: var(--surface2); }
.step-num {
  background: var(--surface2);
  color: var(--text2);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}
.step-source {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.04em;
}
.step-source.system { color: var(--text3); }
.step-source.user { color: var(--blue); }
.step-source.agent { color: var(--green); }
.step-preview {
  flex: 1;
  color: var(--text3);
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.step-cost {
  color: var(--text3);
  font-size: 0.7rem;
  flex-shrink: 0;
}
.step-toggle {
  color: var(--text3);
  font-size: 0.7rem;
  flex-shrink: 0;
  transition: transform 0.2s;
}
.step.expanded .step-toggle { transform: rotate(90deg); }
.step-body {
  display: none;
  padding: 0.85rem;
  background: var(--bg);
  border-top: 1px solid var(--surface2);
}
.step.expanded .step-body { display: block; }

/* Message content */
.msg-content {
  font-size: 0.85rem;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text);
  max-height: 600px;
  overflow-y: auto;
}
.msg-content::-webkit-scrollbar { width: 6px; }
.msg-content::-webkit-scrollbar-thumb { background: var(--surface2); border-radius: 3px; }

/* Tool call */
.tool-call {
  margin-top: 0.75rem;
  background: var(--surface);
  border-radius: 6px;
  border: 1px solid var(--surface2);
  overflow: hidden;
}
.tool-call-header {
  padding: 0.4rem 0.75rem;
  background: var(--surface2);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--cyan);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.tool-call-body {
  padding: 0.6rem 0.75rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.78rem;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

/* Observation */
.observation {
  margin-top: 0.75rem;
  background: var(--surface);
  border-radius: 6px;
  border: 1px solid var(--surface2);
  overflow: hidden;
}
.obs-header {
  padding: 0.4rem 0.75rem;
  background: rgba(99,102,241,0.08);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--accent-hover);
}
.obs-body {
  padding: 0.6rem 0.75rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.76rem;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}
.obs-body::-webkit-scrollbar { width: 6px; }
.obs-body::-webkit-scrollbar-thumb { background: var(--surface2); border-radius: 3px; }

/* Verifier panel */
.verifier-section {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 1.25rem;
  margin-bottom: 1rem;
}
.verifier-section h3 {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}
.test-result {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.6rem;
  font-size: 0.82rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  border-bottom: 1px solid var(--surface2);
}
.test-result:last-child { border-bottom: none; }
.test-result .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.test-result .status-dot.pass { background: var(--green); }
.test-result .status-dot.fail { background: var(--red); }
.test-result .test-name { color: var(--text2); font-size: 0.78rem; }

/* Log viewer */
.log-viewer {
  background: var(--bg);
  border: 1px solid var(--surface2);
  border-radius: 6px;
  padding: 1rem;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.76rem;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 600px;
  overflow-y: auto;
  line-height: 1.5;
}
.log-viewer::-webkit-scrollbar { width: 6px; }
.log-viewer::-webkit-scrollbar-thumb { background: var(--surface2); border-radius: 3px; }

/* Metrics */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.metric-card {
  background: var(--surface);
  border-radius: 6px;
  padding: 0.85rem 1rem;
  text-align: center;
}
.metric-card .metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--accent-hover);
}
.metric-card .metric-label {
  font-size: 0.72rem;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-top: 0.15rem;
}

/* Empty */
.empty {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text3);
}
.empty .icon { font-size: 3rem; margin-bottom: 1rem; }

/* Expand all / collapse all */
.traj-controls {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.traj-controls button {
  background: var(--surface);
  color: var(--text2);
  border: 1px solid var(--surface2);
  border-radius: 5px;
  padding: 0.35rem 0.75rem;
  font-size: 0.78rem;
  cursor: pointer;
  transition: background 0.15s;
}
.traj-controls button:hover { background: var(--surface2); color: var(--text); }

/* Nav hint */
.nav-hint {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  background: var(--surface);
  border: 1px solid var(--surface2);
  border-radius: 6px;
  padding: 0.35rem 0.65rem;
  font-size: 0.7rem;
  color: var(--text3);
  z-index: 100;
}
.nav-hint kbd {
  background: var(--surface2);
  border: 1px solid var(--surface3);
  border-radius: 3px;
  padding: 0.08rem 0.3rem;
  font-family: inherit;
  font-size: 0.7rem;
}

@media (max-width: 768px) {
  .layout { flex-direction: column; }
  .sidebar { width: 100%; min-width: 100%; max-height: 35vh; }
  .tab-panel { padding: 1rem; }
}
</style>
</head>
<body>
<div class="layout">
  <div class="sidebar">
    <div class="sidebar-header">
      <h1>Trajectory Viewer</h1>
      <div class="subtitle">SWE-Bench XL Agent Runs</div>
    </div>
    <div class="run-selector">
      <select id="runSelect"></select>
    </div>
    <div class="search-box">
      <input type="text" id="search" placeholder="Filter trials…" autocomplete="off">
    </div>
    <div class="run-summary" id="runSummary"></div>
    <div class="trial-list" id="trialList"></div>
    <div class="sidebar-footer" id="trialCount"></div>
  </div>

  <div class="main" id="mainArea">
    <div class="empty" id="emptyState">
      <div class="icon">🔍</div>
      <div>Select a trial from the sidebar to view the trajectory</div>
    </div>
    <div id="trialView" style="display:none;">
      <div class="trial-header" id="trialHeader"></div>
      <div class="content-tabs" id="contentTabs"></div>
      <div id="tabPanels"></div>
    </div>
  </div>
</div>

<div class="nav-hint">
  <kbd>↑</kbd><kbd>↓</kbd> navigate &nbsp;·&nbsp; <kbd>/</kbd> search &nbsp;·&nbsp; <kbd>e</kbd> expand all
</div>

<script>
const RUNS = """
        + data_json
        + """;

let currentRunIdx = 0;
let currentTrialIdx = -1;
let currentTab = 'trajectory';
let filteredTrialIndices = [];

function escHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function currentRun() { return RUNS[currentRunIdx] || { trials: [] }; }
function currentTrial() {
  const run = currentRun();
  if (currentTrialIdx < 0 || currentTrialIdx >= run.trials.length) return null;
  return run.trials[currentTrialIdx];
}

// === Init ===
function init() {
  const sel = document.getElementById('runSelect');
  sel.innerHTML = RUNS.map((r, i) =>
    `<option value="${i}">${escHtml(r.run_name)} (${r.trials.length} trials)</option>`
  ).join('');
  sel.onchange = () => { currentRunIdx = +sel.value; currentTrialIdx = -1; filterTrials(''); document.getElementById('search').value = ''; renderSidebar(); renderMain(); };
  filterTrials('');
  renderSidebar();
  if (RUNS.length > 0 && currentRun().trials.length > 0) {
    selectTrial(0);
  }
}

// === Sidebar ===
function filterTrials(q) {
  q = q.toLowerCase();
  const run = currentRun();
  if (!q) {
    filteredTrialIndices = run.trials.map((_, i) => i);
  } else {
    filteredTrialIndices = [];
    run.trials.forEach((t, i) => {
      if (t.task_name.toLowerCase().includes(q) || t.trial_name.toLowerCase().includes(q)) {
        filteredTrialIndices.push(i);
      }
    });
  }
}

function renderSidebar() {
  const run = currentRun();

  // Summary
  const passCount = run.trials.filter(t => t.reward === '1' || t.reward === '1.0').length;
  const failCount = run.trials.length - passCount;
  document.getElementById('runSummary').innerHTML = `
    <div class="stat"><span class="dot pass"></span> ${passCount} passed</div>
    <div class="stat"><span class="dot fail"></span> ${failCount} failed</div>
    <div class="stat">${run.trials.length} total</div>
  `;

  // Trial list
  const list = document.getElementById('trialList');
  list.innerHTML = '';
  filteredTrialIndices.forEach(idx => {
    const t = run.trials[idx];
    const el = document.createElement('div');
    el.className = 'trial-item' + (idx === currentTrialIdx ? ' active' : '');

    const isPass = t.reward === '1' || t.reward === '1.0';
    const rewardClass = isPass ? 'pass' : (t.reward === '?' ? 'unknown' : 'fail');
    const shortId = t.task_name.replace('elastic__elasticsearch-', 'ES-');

    el.innerHTML = `
      <div class="reward-badge ${rewardClass}">${isPass ? '✓' : '✗'}</div>
      <div class="trial-info">
        <div class="trial-id">${escHtml(shortId)}</div>
        <div class="trial-meta">${t.step_count} steps · ${t.model_name.split('/').pop()}</div>
      </div>
    `;
    el.onclick = () => selectTrial(idx);
    list.appendChild(el);
  });

  document.getElementById('trialCount').textContent =
    `${filteredTrialIndices.length} of ${run.trials.length} trials`;
}

function selectTrial(idx) {
  currentTrialIdx = idx;
  currentTab = 'trajectory';
  renderSidebar();
  renderMain();
  const active = document.querySelector('.trial-item.active');
  if (active) active.scrollIntoView({ block: 'nearest' });
}

// === Main ===
function renderMain() {
  const trial = currentTrial();
  if (!trial) {
    document.getElementById('emptyState').style.display = '';
    document.getElementById('trialView').style.display = 'none';
    return;
  }
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('trialView').style.display = '';

  renderTrialHeader(trial);
  renderContentTabs(trial);
  renderTabPanel(trial);
}

function renderTrialHeader(trial) {
  const isPass = trial.reward === '1' || trial.reward === '1.0';
  const rewardBadge = isPass ? 'pass' : 'fail';
  const fm = trial.final_metrics || {};
  const cost = fm.total_cost_usd != null ? `$${fm.total_cost_usd.toFixed(4)}` : '';
  const tokens = fm.total_prompt_tokens ? `${(fm.total_prompt_tokens/1000).toFixed(0)}k prompt` : '';

  document.getElementById('trialHeader').innerHTML = `
    <h2>${escHtml(trial.task_name)}</h2>
    <div class="meta-row">
      <span class="badge ${rewardBadge}">Reward: ${trial.reward}</span>
      <span class="badge model">${escHtml(trial.model_name)}</span>
      <span class="badge">${escHtml(trial.agent_name)}</span>
      <span class="badge">${trial.step_count} steps</span>
      ${cost ? `<span class="badge cost">${cost}</span>` : ''}
      ${tokens ? `<span class="badge">${tokens}</span>` : ''}
      ${trial.exit_status ? `<span class="badge">Exit: ${escHtml(trial.exit_status)}</span>` : ''}
    </div>
  `;
}

function renderContentTabs(trial) {
  const tabs = [
    { id: 'trajectory', label: `Trajectory (${trial.step_count})` },
    { id: 'verifier', label: 'Verifier' },
    { id: 'metrics', label: 'Metrics' },
  ];
  const bar = document.getElementById('contentTabs');
  bar.innerHTML = tabs.map(t =>
    `<div class="c-tab${t.id === currentTab ? ' active' : ''}" data-tab="${t.id}">${t.label}</div>`
  ).join('');
  bar.querySelectorAll('.c-tab').forEach(el => {
    el.onclick = () => { currentTab = el.dataset.tab; renderContentTabs(trial); renderTabPanel(trial); };
  });
}

function renderTabPanel(trial) {
  const container = document.getElementById('tabPanels');
  container.innerHTML = '';

  const panel = document.createElement('div');
  panel.className = 'tab-panel active';

  switch(currentTab) {
    case 'trajectory':
      panel.innerHTML = renderTrajectory(trial);
      break;
    case 'verifier':
      panel.innerHTML = renderVerifier(trial);
      break;
    case 'metrics':
      panel.innerHTML = renderMetrics(trial);
      break;
  }

  container.appendChild(panel);

  // Attach step toggle handlers
  if (currentTab === 'trajectory') {
    panel.querySelectorAll('.step-header').forEach(hdr => {
      hdr.onclick = () => {
        hdr.parentElement.classList.toggle('expanded');
      };
    });
    // Expand/collapse all
    const expandBtn = panel.querySelector('#expandAll');
    const collapseBtn = panel.querySelector('#collapseAll');
    if (expandBtn) expandBtn.onclick = () => panel.querySelectorAll('.step').forEach(s => s.classList.add('expanded'));
    if (collapseBtn) collapseBtn.onclick = () => panel.querySelectorAll('.step').forEach(s => s.classList.remove('expanded'));
  }
}

// === Trajectory ===
function renderTrajectory(trial) {
  if (!trial.steps.length) return '<div class="empty"><div class="icon">📝</div><div>No trajectory data available</div></div>';

  const stepsHtml = trial.steps.map((step, i) => {
    const preview = (step.message || '').slice(0, 120).replace(/\\n/g, ' ');
    const costStr = step.metrics && step.metrics.cost_usd != null
      ? `$${step.metrics.cost_usd.toFixed(4)}`
      : '';

    // Tool calls
    let toolCallsHtml = '';
    if (step.tool_calls && step.tool_calls.length) {
      toolCallsHtml = step.tool_calls.map(tc => {
        const name = tc.function_name || (tc.function && tc.function.name) || 'unknown';
        const args = tc.arguments || (tc.function && tc.function.arguments) || {};
        const argsStr = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
        return `<div class="tool-call">
          <div class="tool-call-header">⚡ ${escHtml(name)}</div>
          <div class="tool-call-body">${escHtml(argsStr)}</div>
        </div>`;
      }).join('');
    }

    // Observation
    let obsHtml = '';
    if (step.observation) {
      const obsText = typeof step.observation === 'string'
        ? step.observation
        : JSON.stringify(step.observation, null, 2);
      if (obsText.trim()) {
        const truncated = obsText.length > 5000 ? obsText.slice(0, 5000) + '\\n\\n... [truncated]' : obsText;
        obsHtml = `<div class="observation">
          <div class="obs-header">📋 Observation</div>
          <div class="obs-body">${escHtml(truncated)}</div>
        </div>`;
      }
    }

    // Auto-expand: agent steps with tool calls, first few steps
    const autoExpand = (step.source === 'agent' && step.tool_calls && step.tool_calls.length > 0) || i < 2;

    return `<div class="step${autoExpand ? ' expanded' : ''}">
      <div class="step-header">
        <div class="step-num">${step.step_id}</div>
        <div class="step-source ${step.source}">${step.source}</div>
        <div class="step-preview">${escHtml(preview)}</div>
        ${costStr ? `<div class="step-cost">${costStr}</div>` : ''}
        <div class="step-toggle">▶</div>
      </div>
      <div class="step-body">
        <div class="msg-content">${escHtml(step.message)}</div>
        ${toolCallsHtml}
        ${obsHtml}
      </div>
    </div>`;
  }).join('');

  return `
    <div class="trajectory">
      <div class="traj-controls">
        <button id="expandAll">Expand All</button>
        <button id="collapseAll">Collapse All</button>
      </div>
      ${stepsHtml}
    </div>`;
}

// === Verifier ===
function renderVerifier(trial) {
  const v = trial.verifier || {};
  let html = '';

  if (v.output && v.output.tests) {
    const tests = v.output.tests;
    const passed = tests.filter(t => t.status === 'PASSED').length;
    const failed = tests.filter(t => t.status === 'FAILED').length;

    html += `<div class="verifier-section">
      <h3>Test Results — ${passed} passed, ${failed} failed of ${tests.length}</h3>
      <div style="max-height:400px;overflow-y:auto;">
        ${tests.map(t => `
          <div class="test-result">
            <span class="status-dot ${t.status === 'PASSED' ? 'pass' : 'fail'}"></span>
            <span class="test-name">${escHtml(t.name)}</span>
          </div>
        `).join('')}
      </div>
    </div>`;
  }

  if (v.test_stdout) {
    html += `<div class="verifier-section">
      <h3>Test Output</h3>
      <div class="log-viewer">${escHtml(v.test_stdout)}</div>
    </div>`;
  }

  if (!html) {
    html = '<div class="empty"><div class="icon">🧪</div><div>No verifier data available</div></div>';
  }

  return html;
}

// === Metrics ===
function renderMetrics(trial) {
  const fm = trial.final_metrics || {};
  const cards = [];

  if (fm.total_cost_usd != null) cards.push({ value: `$${fm.total_cost_usd.toFixed(4)}`, label: 'Total Cost' });
  if (fm.total_prompt_tokens) cards.push({ value: fm.total_prompt_tokens.toLocaleString(), label: 'Prompt Tokens' });
  if (fm.total_completion_tokens) cards.push({ value: fm.total_completion_tokens.toLocaleString(), label: 'Completion Tokens' });
  if (fm.total_cached_tokens) cards.push({ value: fm.total_cached_tokens.toLocaleString(), label: 'Cached Tokens' });
  if (fm.api_calls) cards.push({ value: fm.api_calls.toLocaleString(), label: 'API Calls' });
  cards.push({ value: trial.step_count, label: 'Steps' });
  cards.push({ value: trial.reward, label: 'Reward' });

  // Per-step cost breakdown
  let costSteps = trial.steps.filter(s => s.metrics && s.metrics.cost_usd != null);
  let costChart = '';
  if (costSteps.length > 0) {
    const maxCost = Math.max(...costSteps.map(s => s.metrics.cost_usd));
    costChart = `<div class="verifier-section" style="margin-top:1rem;">
      <h3>Cost per Step</h3>
      <div style="max-height:400px;overflow-y:auto;">
        ${costSteps.map(s => {
          const pct = maxCost > 0 ? (s.metrics.cost_usd / maxCost * 100) : 0;
          return `<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.3rem;font-size:0.78rem;">
            <span style="width:40px;color:var(--text3);text-align:right;">#${s.step_id}</span>
            <div style="flex:1;background:var(--surface2);border-radius:3px;height:18px;overflow:hidden;">
              <div style="width:${pct}%;height:100%;background:var(--accent);border-radius:3px;"></div>
            </div>
            <span style="width:65px;color:var(--text2);text-align:right;">$${s.metrics.cost_usd.toFixed(4)}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }

  // Token usage per step
  let tokenSteps = trial.steps.filter(s => s.metrics && s.metrics.prompt_tokens != null);
  let tokenChart = '';
  if (tokenSteps.length > 0) {
    const maxTokens = Math.max(...tokenSteps.map(s => s.metrics.prompt_tokens));
    tokenChart = `<div class="verifier-section" style="margin-top:1rem;">
      <h3>Prompt Tokens per Step</h3>
      <div style="max-height:400px;overflow-y:auto;">
        ${tokenSteps.map(s => {
          const pct = maxTokens > 0 ? (s.metrics.prompt_tokens / maxTokens * 100) : 0;
          return `<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.3rem;font-size:0.78rem;">
            <span style="width:40px;color:var(--text3);text-align:right;">#${s.step_id}</span>
            <div style="flex:1;background:var(--surface2);border-radius:3px;height:18px;overflow:hidden;">
              <div style="width:${pct}%;height:100%;background:var(--cyan);border-radius:3px;"></div>
            </div>
            <span style="width:65px;color:var(--text2);text-align:right;">${(s.metrics.prompt_tokens/1000).toFixed(1)}k</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }

  return `
    <div class="metrics-grid">
      ${cards.map(c => `<div class="metric-card"><div class="metric-value">${c.value}</div><div class="metric-label">${c.label}</div></div>`).join('')}
    </div>
    ${costChart}
    ${tokenChart}
  `;
}

// === Keyboard ===
document.addEventListener('keydown', (e) => {
  if (document.activeElement.id === 'search' && e.key !== 'Escape') return;

  if (e.key === 'ArrowDown' || e.key === 'j') {
    e.preventDefault();
    const pos = filteredTrialIndices.indexOf(currentTrialIdx);
    if (pos < filteredTrialIndices.length - 1) selectTrial(filteredTrialIndices[pos + 1]);
    else if (currentTrialIdx < 0 && filteredTrialIndices.length > 0) selectTrial(filteredTrialIndices[0]);
  } else if (e.key === 'ArrowUp' || e.key === 'k') {
    e.preventDefault();
    const pos = filteredTrialIndices.indexOf(currentTrialIdx);
    if (pos > 0) selectTrial(filteredTrialIndices[pos - 1]);
  } else if (e.key === '/') {
    e.preventDefault();
    document.getElementById('search').focus();
  } else if (e.key === 'Escape') {
    document.getElementById('search').blur();
  } else if (e.key === 'e') {
    document.querySelectorAll('.step').forEach(s => s.classList.add('expanded'));
  } else if (e.key === 'c') {
    document.querySelectorAll('.step').forEach(s => s.classList.remove('expanded'));
  }
});

document.getElementById('search').addEventListener('input', (e) => {
  filterTrials(e.target.value);
  renderSidebar();
});

init();
</script>
</body>
</html>"""
    )


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python generate_trajectory_dashboard.py <run_dir> [<run_dir2> ...]",
            file=sys.stderr,
        )
        print(
            "Example: python generate_trajectory_dashboard.py ./re-run-with-wrapper ./full-trajectories",
            file=sys.stderr,
        )
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    runs = []
    for run_dir in sys.argv[1:]:
        if not os.path.isdir(run_dir):
            print(f"Warning: {run_dir} is not a directory, skipping", file=sys.stderr)
            continue
        print(f"Loading {run_dir}...")
        run = load_run(run_dir)
        print(f"  → {len(run['trials'])} trials loaded")
        runs.append(run)

    if not runs:
        print("Error: No valid run directories found", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.join(repo_root, "dashboards", "trajectory_dashboard.html")
    html = generate_html(runs)
    with open(output_path, "w") as f:
        f.write(html)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    total_trials = sum(len(r["trials"]) for r in runs)
    print(
        f"\nGenerated {output_path}\n  {len(runs)} run(s), {total_trials} trial(s), {size_mb:.1f} MB"
    )


if __name__ == "__main__":
    main()
