"""Load trajectory files, detect format, and dispatch to the correct adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
from traj.models import TrajectoryResult
from traj.adapters.copilot import CopilotAdapter
from traj.adapters.codex import CodexAdapter
from traj.adapters.openhands import OpenHandsAdapter


def load_trajectory(path: str) -> TrajectoryResult:
    """Load a single trajectory file and return normalised operations."""
    with open(path) as f:
        data = json.load(f)

    source_file = os.path.basename(path)
    adapter = _detect_adapter(data)
    agent, session_id, ops = adapter.extract(data, source_file)

    return TrajectoryResult(
        source_file=source_file,
        agent=agent,
        session_id=session_id,
        operations=ops,
    )


def load_trajectories(path: str) -> list[TrajectoryResult]:
    """Load one or many trajectory files.

    If path is a file, load that single file.
    If path is a directory, recursively find all .json files and load them.
    """
    p = Path(path)
    if p.is_file():
        return [load_trajectory(str(p))]

    if p.is_dir():
        results = []
        for json_file in sorted(p.rglob("*.json")):
            try:
                results.append(load_trajectory(str(json_file)))
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: skipping {json_file}: {e}")
        return results

    raise FileNotFoundError(f"Path not found: {path}")


def _detect_adapter(data):
    """Detect the trajectory format and return the appropriate adapter."""
    # ATIF format (Copilot CLI): dict with "schema_version" starting with "ATIF"
    if isinstance(data, dict):
        schema = data.get("schema_version", "")
        if isinstance(schema, str) and schema.startswith("ATIF"):
            return CopilotAdapter()
        # Could also be ATIF without explicit schema but with "steps"
        if "steps" in data:
            return CopilotAdapter()

    # Flat array formats: Codex or OpenHands
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            tool = first.get("tool", "")
            # OpenHands uses tool names like "execute_bash", "read", "task_tracking"
            if tool in ("execute_bash", "read", "task_tracking", "think", "message"):
                return OpenHandsAdapter()
            # Codex uses "bash", "file_edit", "Finish"
            if tool in ("bash", "file_edit", "Finish"):
                return CodexAdapter()

            # Fallback: check action structure
            action = first.get("action", "")
            if isinstance(action, dict) and "name" in action:
                return OpenHandsAdapter()
            if isinstance(action, str) and action.startswith("/bin/bash"):
                return CodexAdapter()

    raise ValueError("Could not detect trajectory format")
