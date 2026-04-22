"""Copilot CLI (ATIF format) adapter."""
from __future__ import annotations
import re
from traj.adapters.base import BaseAdapter
from traj.models import Operation
from traj.bash_classifier import classify_bash


# Tools that don't represent file operations
SKIP_TOOLS = {
    "report_intent", "ask_user", "stop_bash", "read_bash", "read_agent",
    "write_bash", "list_bash", "list_agents", "fetch_copilot_cli_documentation",
    "exit_plan_mode", "sql", "web_search", "web_fetch",
}

# Tools on GitHub MCP server — these are API calls, not file ops
SKIP_PREFIXES = ("github-mcp-server-",)


class CopilotAdapter(BaseAdapter):

    def extract(self, data: dict, source_file: str) -> tuple[str, str, list[Operation]]:
        agent_name = data.get("agent", {}).get("name", "copilot")
        session_id = data.get("session_id", "")
        main_model = data.get("agent", {}).get("model_name", "")
        ops: list[Operation] = []

        # Track active sub-agent delegations: agent_id -> name
        active_sub_agents: dict[str, str] = {}

        for step in data.get("steps", []):
            step_id = step.get("step_id", 0)
            step_model = step.get("model_name", "")

            # Determine if this step is from a sub-agent.
            # Sub-agent steps use a different model from the main agent
            # and have turn counters that reset.
            is_sub_agent = (
                main_model and step_model and step_model != main_model
                and step.get("source") == "agent"
            )
            sub_agent_name = None
            if is_sub_agent:
                # Try to find which sub-agent this belongs to
                sub_agent_name = self._guess_sub_agent_name(active_sub_agents, step_model)

            for tc in step.get("tool_calls", []):
                func = tc.get("function_name", "")
                args = tc.get("arguments", {})

                # Track task delegations so we can label sub-agent steps
                if func == "task":
                    agent_id = args.get("name", "")
                    if agent_id:
                        active_sub_agents[agent_id] = agent_id

                ops.extend(self._process_tool_call(
                    tc, step_id,
                    sub_agent=is_sub_agent,
                    sub_agent_name=sub_agent_name,
                ))

            # Process sub-agent results embedded in observations
            obs = step.get("observation", {})
            if isinstance(obs, dict):
                for result in obs.get("results", []):
                    content = result.get("content", "")
                    if isinstance(content, dict) and "steps" in content:
                        self._extract_sub_agent_steps(content, step_id, ops)

        return agent_name, session_id, ops

    def _guess_sub_agent_name(self, active_sub_agents: dict, model: str) -> str | None:
        """Return the most recently registered sub-agent name, if any."""
        if active_sub_agents:
            return list(active_sub_agents.values())[-1]
        return model

    def _process_tool_call(self, tc: dict, step_id: int,
                           sub_agent: bool = False,
                           sub_agent_name: str | None = None) -> list[Operation]:
        func = tc.get("function_name", "")
        args = tc.get("arguments", {})

        if func in SKIP_TOOLS:
            return []
        if any(func.startswith(p) for p in SKIP_PREFIXES):
            return []

        # --- task (sub-agent delegation) ---
        if func == "task":
            # The task tool itself is a delegation; its nested steps are
            # handled separately if the trajectory includes them.
            # We record the delegation itself as an Explore.
            agent_type = args.get("agent_type", "")
            name = args.get("name", "")
            if agent_type in ("explore", "task", "general-purpose"):
                return [Operation(
                    step=step_id, action="Explore", path="",
                    tool=f"task:{agent_type}",
                    detail=f"task agent_type={agent_type} name={name}",
                    sub_agent=sub_agent, sub_agent_name=sub_agent_name,
                )]
            return []

        # --- view (Read) ---
        if func == "view":
            path = args.get("path", "")
            vr = args.get("view_range", "")
            detail = f"view path={path}"
            if vr:
                detail += f" view_range={vr}"
            return [Operation(
                step=step_id, action="Read", path=path, tool="view",
                detail=detail, sub_agent=sub_agent, sub_agent_name=sub_agent_name,
            )]

        # --- edit (Write) ---
        if func == "edit":
            path = args.get("path", "")
            return [Operation(
                step=step_id, action="Write", path=path, tool="edit",
                detail=f"edit path={path} str_replace",
                sub_agent=sub_agent, sub_agent_name=sub_agent_name,
            )]

        # --- create (Write) ---
        if func == "create":
            path = args.get("path", "")
            return [Operation(
                step=step_id, action="Write", path=path, tool="create",
                detail=f"create path={path}",
                sub_agent=sub_agent, sub_agent_name=sub_agent_name,
            )]

        # --- grep / rg (Explore) ---
        if func in ("grep", "rg"):
            pattern = args.get("pattern", "")
            paths = args.get("paths", "") or args.get("path", "")
            glob_pat = args.get("glob", "")
            detail = f"{func} pattern='{pattern}'"
            if paths:
                detail += f" paths={paths}"
            if glob_pat:
                detail += f" glob={glob_pat}"
            search_path = paths if isinstance(paths, str) else (paths[0] if paths else "")
            return [Operation(
                step=step_id, action="Explore", path=search_path or glob_pat,
                tool=func, detail=detail,
                sub_agent=sub_agent, sub_agent_name=sub_agent_name,
            )]

        # --- glob (Explore) ---
        if func == "glob":
            pattern = args.get("pattern", "")
            paths = args.get("paths", "")
            detail = f"glob pattern='{pattern}'"
            if paths:
                detail += f" paths={paths}"
            return [Operation(
                step=step_id, action="Explore", path=pattern,
                tool="glob", detail=detail,
                sub_agent=sub_agent, sub_agent_name=sub_agent_name,
            )]

        # --- bash ---
        if func == "bash":
            command = args.get("command", "")
            return classify_bash(command, step_id, sub_agent, sub_agent_name)

        # --- exec_command (Codex ATIF variant) ---
        if func == "exec_command":
            command = args.get("cmd", "") or args.get("command", "")
            return classify_bash(command, step_id, sub_agent, sub_agent_name)

        # --- apply_patch (Codex ATIF variant — Write) ---
        if func == "apply_patch":
            patch_text = args.get("input", "") or args.get("patch", "") or args.get("raw", "")
            return _extract_patch_files(patch_text, step_id, sub_agent, sub_agent_name)

        # --- update_plan / write_stdin (skip) ---
        if func in ("update_plan", "write_stdin"):
            return []

        # Unknown tool — record as Other
        return [Operation(
            step=step_id, action="Other", path="", tool=func,
            detail=f"{func} {str(args)[:200]}",
            sub_agent=sub_agent, sub_agent_name=sub_agent_name,
        )]

    def _extract_sub_agent_steps(self, sub_data: dict, parent_step_id: int,
                                 ops: list[Operation]) -> None:
        """Recursively extract operations from embedded sub-agent steps."""
        sub_agent_name = sub_data.get("agent", {}).get("name", "sub-agent")
        for step in sub_data.get("steps", []):
            for tc in step.get("tool_calls", []):
                ops.extend(self._process_tool_call(
                    tc, parent_step_id, sub_agent=True,
                    sub_agent_name=sub_agent_name,
                ))


def _extract_patch_files(patch_text: str, step_id: int, sub_agent: bool,
                         sub_agent_name: str | None) -> list[Operation]:
    """Extract Write operations from a patch/diff text.

    Handles formats like:
        *** Update File: /app/src/Main.java
        --- a/src/Main.java
        +++ b/src/Main.java
        *** Add File: /app/src/New.java
    """
    ops = []
    seen = set()
    for match in re.finditer(
        r'(?:Update File:\s*|Add File:\s*|Delete File:\s*|---\s+a/|[+]{3}\s+b/)(.+)',
        patch_text,
    ):
        path = match.group(1).strip()
        if path and path not in seen:
            seen.add(path)
            ops.append(Operation(
                step=step_id, action="Write", path=path, tool="apply_patch",
                detail=f"apply_patch path={path}",
                sub_agent=sub_agent, sub_agent_name=sub_agent_name,
            ))
    return ops
