"""Base adapter interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from traj.models import Operation


class BaseAdapter(ABC):
    """All agent adapters implement this interface."""

    @abstractmethod
    def extract(self, data: dict | list, source_file: str) -> tuple[str, str, list[Operation]]:
        """Extract operations from raw trajectory data.

        Returns:
            (agent_name, session_id, operations)
        """
        ...
