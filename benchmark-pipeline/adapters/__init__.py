"""
Adapter registry — maps adapter names to LanguageAdapter instances.

Usage::

    from adapters import get_adapter
    adapter = get_adapter("java-gradle")
"""

from __future__ import annotations

from typing import Dict, Type

from adapters.base import LanguageAdapter

_REGISTRY: Dict[str, LanguageAdapter] = {}


def register_adapter(name: str, adapter: LanguageAdapter) -> None:
    """Register a ``LanguageAdapter`` instance under *name*."""
    _REGISTRY[name] = adapter


def get_adapter(name: str) -> LanguageAdapter:
    """
    Return the adapter registered under *name*.

    Raises ``ValueError`` with a helpful message if unknown.
    """
    if name in _REGISTRY:
        return _REGISTRY[name]
    registered = ", ".join(sorted(_REGISTRY)) or "(none)"
    raise ValueError(
        f"Unknown adapter: {name!r}. "
        f"Register it in adapters/__init__.py.  Currently registered: {registered}"
    )


def registered_adapters() -> list[str]:
    """Return the sorted list of registered adapter names."""
    return sorted(_REGISTRY)


# ── Built-in adapters ────────────────────────────────────────────────────────

from adapters.java_gradle import JavaGradleAdapter  # noqa: E402
from adapters.kibana import KibanaAdapter  # noqa: E402
from adapters.babylon import BabylonAdapter  # noqa: E402
from adapters.transformers import TransformersAdapter  # noqa: E402
from adapters.vscode import VSCodeAdapter  # noqa: E402

register_adapter("java-gradle", JavaGradleAdapter())
register_adapter("kibana", KibanaAdapter())
register_adapter("babylon", BabylonAdapter())
register_adapter("transformers", TransformersAdapter())
register_adapter("vscode", VSCodeAdapter())
