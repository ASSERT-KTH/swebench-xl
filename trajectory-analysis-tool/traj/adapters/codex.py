"""Codex CLI adapter."""
from __future__ import annotations
from traj.adapters.base import BaseAdapter
from traj.models import Operation
from traj.bash_classifier import classify_bash


SKIP_TOOLS = {"Finish"}


class CodexAdapter(BaseAdapter):

    def extract(self, data: list, source_file: str) -> tuple[str, str, list[Operation]]:
        ops: list[Operation] = []

        for i, entry in enumerate(data):
            tool = entry.get("tool", "")
            step = i + 1

            if tool in SKIP_TOOLS:
                continue

            if tool == "file_edit":
                ops.extend(self._handle_file_edit(entry, step))
            elif tool == "bash":
                ops.extend(self._handle_bash(entry, step))
            else:
                # Unknown tool with no path — skip
                pass

        return "codex", "", ops

    def _handle_file_edit(self, entry: dict, step: int) -> list[Operation]:
        action_str = entry.get("action", "")
        # Codex file_edit action is a JSON string like:
        # "file_change: [{\"path\":\"/app/src/File.java\",\"kind\":\"update\"}]"
        path = ""
        if isinstance(action_str, str) and "path" in action_str:
            import re
            match = re.search(r'"path"\s*:\s*"([^"]+)"', action_str)
            if match:
                path = match.group(1)

        return [Operation(
            step=step, action="Write", path=path, tool="file_edit",
            detail=f"file_edit: {action_str[:200]}",
        )]

    def _handle_bash(self, entry: dict, step: int) -> list[Operation]:
        action = entry.get("action", "")
        if isinstance(action, str):
            return classify_bash(action, step)
        return []
