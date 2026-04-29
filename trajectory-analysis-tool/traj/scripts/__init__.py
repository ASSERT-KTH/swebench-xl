"""Shared utilities for analysis scripts."""
from __future__ import annotations

import re


def extract_repo(instance_id: str) -> str:
    """Extract the repository identifier (owner__repo) from an instance_id.

    Examples:
        elastic__elasticsearch-135899 -> elastic__elasticsearch
        instance_ansible__ansible-0fd88717c9-vba6da65a -> ansible__ansible
        instance_element-hq__element-web-107772 -> element-hq__element-web
    """
    # Strip instance_ prefix used by SWE-bench Pro / Harbor
    iid = instance_id.removeprefix("instance_")
    parts = iid.split("__", 1)
    if len(parts) != 2:
        return iid
    owner = parts[0]
    rest = parts[1]
    # Build up the repo name by consuming hyphenated segments that don't
    # look like a commit hash, version tag, or issue number.
    segments = rest.split("-")
    repo_parts = [segments[0]]
    for seg in segments[1:]:
        if re.fullmatch(r'[0-9a-fA-F]{5,}', seg) or re.fullmatch(r'[0-9]+', seg) or re.fullmatch(r'v[0-9a-fA-F]+', seg) or seg == "vnan":
            break
        repo_parts.append(seg)
    return f"{owner}__{'-'.join(repo_parts)}"
    return f"{owner}__{'-'.join(repo_parts)}"
