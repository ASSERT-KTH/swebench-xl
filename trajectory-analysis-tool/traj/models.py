from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Operation:
    """A single normalised file operation extracted from a trajectory."""
    step: int
    action: str  # Read, Write, Explore, Other
    path: str  # file/directory path or glob pattern
    tool: str  # original tool name (e.g. "view", "bash", "grep")
    detail: str = ""  # original command/args for debugging
    sub_agent: bool = False
    sub_agent_name: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["sub_agent_name"] is None:
            del d["sub_agent_name"]
        return d


@dataclass
class TrajectoryResult:
    """The normalised output for one trajectory file."""
    source_file: str
    agent: str
    session_id: str
    operations: list[Operation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "agent": self.agent,
            "session_id": self.session_id,
            "operations": [op.to_dict() for op in self.operations],
        }
