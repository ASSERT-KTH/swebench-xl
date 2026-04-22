# Trajectory Analysis Tool

Normalise agent trajectories (Copilot CLI, Codex CLI, OpenHands) into a simple `Read`/`Write`/`Explore` format.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Extract operations from a single trajectory
traj extract trajectory.json

# Extract from a directory of trajectories
traj extract ./trajectories/

# Save output to a file
traj extract ./trajectories/ -o output.json

# Run an analysis script
traj analyse summary ./trajectories/
```

## Output Format

Each trajectory produces a JSON object with:
- `source_file` — input filename
- `agent` — detected agent name
- `session_id` — session identifier
- `operations` — list of normalised operations, each with:
  - `step` — step number in the trajectory
  - `action` — `Read`, `Write`, `Explore`, or `Other`
  - `path` — file or directory path (or pattern)
  - `tool` — original tool name
  - `detail` — original command/arguments for debugging
  - `sub_agent` — whether this came from a sub-agent
  - `sub_agent_name` — name of the sub-agent (if applicable)

## Adding a New Agent Adapter

To support a new agent, you need two things: an adapter class and a detection rule.

### 1. Create the adapter

Add a new file in `traj/adapters/`, e.g. `traj/adapters/my_agent.py`:

```python
from __future__ import annotations
from traj.adapters.base import BaseAdapter
from traj.models import Operation
from traj.bash_classifier import classify_bash


class MyAgentAdapter(BaseAdapter):

    def extract(self, data: dict | list, source_file: str) -> tuple[str, str, list[Operation]]:
        """Parse the raw trajectory JSON and return normalised operations.

        Returns:
            (agent_name, session_id, list_of_operations)
        """
        ops: list[Operation] = []

        # Iterate over your trajectory's steps/entries
        for i, entry in enumerate(data):
            step = i + 1
            tool = entry.get("tool", "")

            # Map known tools to Read/Write/Explore
            if tool == "read_file":
                path = entry.get("path", "")
                ops.append(Operation(
                    step=step, action="Read", path=path, tool=tool,
                    detail=f"read_file path={path}",
                ))
            elif tool == "write_file":
                path = entry.get("path", "")
                ops.append(Operation(
                    step=step, action="Write", path=path, tool=tool,
                    detail=f"write_file path={path}",
                ))
            elif tool == "bash":
                # Delegate bash commands to the classifier —
                # it handles cat, grep, sed, find, etc. automatically
                command = entry.get("command", "")
                ops.extend(classify_bash(command, step))

        return "my_agent", data.get("session_id", ""), ops
```

Key points:
- Implement `extract()` returning `(agent_name, session_id, operations)`
- Use `classify_bash()` for any bash/shell commands — it handles Read/Write/Explore detection and path extraction
- Set `detail` to include the original tool + arguments so you can debug the classification later
- For sub-agent operations, set `sub_agent=True` and `sub_agent_name="..."` on the `Operation`

### 2. Register format detection

Edit `traj/loader.py` and update `_detect_adapter()` to recognise your format:

```python
from traj.adapters.my_agent import MyAgentAdapter

def _detect_adapter(data):
    # ... existing checks ...

    # Add detection for your format
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if first.get("tool") in ("read_file", "write_file", "my_tool"):
            return MyAgentAdapter()

    raise ValueError("Could not detect trajectory format")
```

That's it — `traj extract` and `traj analyse` will now auto-detect and process your agent's trajectories.

## Adding an Analysis Script

Analysis scripts consume normalised trajectories and produce a JSON result. You can add them in two ways:

### Option A: Built-in script (in `traj/scripts/`)

Create a Python file in `traj/scripts/`, e.g. `traj/scripts/files_touched.py`:

```python
"""List all unique files read and written across trajectories."""
from __future__ import annotations
from traj.models import TrajectoryResult


def run(trajectories: list[TrajectoryResult]) -> dict:
    """Entry point — receives normalised trajectories, returns a JSON-serialisable dict."""
    read_files = set()
    written_files = set()

    for traj in trajectories:
        for op in traj.operations:
            if op.action == "Read" and op.path:
                read_files.add(op.path)
            elif op.action == "Write" and op.path:
                written_files.add(op.path)

    return {
        "files_read": sorted(read_files),
        "files_written": sorted(written_files),
        "read_count": len(read_files),
        "write_count": len(written_files),
    }
```

Then run it by name:
```bash
traj analyse files_touched ./trajectories/
```

### Option B: External script (any `.py` file)

You can also pass a path to any Python file:
```bash
traj analyse ./my_scripts/custom_analysis.py ./trajectories/
```

The file just needs the same `run(trajectories) -> dict` signature.

### What you get in `trajectories`

Each `TrajectoryResult` has:
- `source_file` — the input filename
- `agent` — `"copilot"`, `"codex"`, `"openhands"`, etc.
- `session_id` — session identifier
- `operations` — list of `Operation` objects, each with:
  - `step` (int) — step number
  - `action` (str) — `"Read"`, `"Write"`, `"Explore"`, or `"Other"`
  - `path` (str) — file/directory path or glob pattern
  - `tool` (str) — original tool name
  - `detail` (str) — original command/arguments
  - `sub_agent` (bool) — whether from a sub-agent
  - `sub_agent_name` (str | None) — sub-agent name if applicable

See `traj/scripts/summary.py` for a full working example.
