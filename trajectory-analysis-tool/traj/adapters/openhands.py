"""OpenHands adapter."""
from __future__ import annotations
from traj.adapters.base import BaseAdapter
from traj.models import Operation
from traj.bash_classifier import classify_bash


SKIP_TOOLS = {"task_tracking", "finish", "think", "message"}


class OpenHandsAdapter(BaseAdapter):

    def extract(self, data: list, source_file: str) -> tuple[str, str, list[Operation]]:
        ops: list[Operation] = []

        for i, entry in enumerate(data):
            tool = entry.get("tool", "")
            step = i + 1

            if tool in SKIP_TOOLS:
                continue

            if tool == "read":
                ops.extend(self._handle_read(entry, step))
            elif tool == "edit":
                ops.extend(self._handle_edit(entry, step))
            elif tool == "execute_bash":
                ops.extend(self._handle_bash(entry, step))
            else:
                # Unknown tool with no path — skip
                pass

        return "openhands", "", ops

    def _handle_read(self, entry: dict, step: int) -> list[Operation]:
        action = entry.get("action", {})
        path = action.get("path", "") if isinstance(action, dict) else ""
        vr = action.get("view_range", "") if isinstance(action, dict) else ""
        detail = f"read path={path}"
        if vr:
            detail += f" view_range={vr}"
        return [Operation(step=step, action="Read", path=path, tool="read", detail=detail)]

    def _handle_edit(self, entry: dict, step: int) -> list[Operation]:
        action = entry.get("action", {})
        path = action.get("path", "") if isinstance(action, dict) else ""
        cmd = action.get("command", "") if isinstance(action, dict) else ""
        detail = f"edit path={path} command={cmd}"
        return [Operation(step=step, action="Write", path=path, tool="edit", detail=detail)]

    def _handle_bash(self, entry: dict, step: int) -> list[Operation]:
        action = entry.get("action", {})
        if isinstance(action, dict):
            command = action.get("command", "")
        elif isinstance(action, str):
            command = action
        else:
            return []
        return classify_bash(command, step)
