"""
Unified diff / patch construction from GitHub patch data.

Builds git-apply-compatible patches split into:
  - test_patch: test files + test-support files (utils, muted-tests.yml, etc.)
  - gold_patch: source files only
"""

from typing import Callable, Dict, List


def build_unified_patch(
    patches: List[Dict],
    file_filter: Callable[[str], bool],
) -> str:
    """
    Reconstruct a unified diff from GitHub's hunk-only patches.

    file_filter: returns True for files to include.
    """
    diff_parts: list[str] = []
    for p in patches:
        filename = p["filename"]
        if not file_filter(filename):
            continue
        raw_patch = p.get("patch", "")
        if not raw_patch:
            continue
        status = p.get("status", "modified")
        if status == "added":
            git_header = f"diff --git a/{filename} b/{filename}\nnew file mode 100644"
            header = f"--- /dev/null\n+++ b/{filename}"
        elif status == "removed":
            git_header = f"diff --git a/{filename} b/{filename}\ndeleted file mode 100644"
            header = f"--- a/{filename}\n+++ /dev/null"
        else:
            git_header = f"diff --git a/{filename} b/{filename}"
            header = f"--- a/{filename}\n+++ b/{filename}"
        diff_parts.append(f"{git_header}\n{header}\n{raw_patch}")
    return "\n".join(diff_parts)


def build_test_patch(
    patches: List[Dict],
    test_files: List[str],
    test_support_files: List[str],
) -> str:
    """Build a patch containing test files and test-support files."""
    included = set(test_files) | set(test_support_files)
    return build_unified_patch(patches, lambda f: f in included)


def build_gold_patch(
    patches: List[Dict],
    source_files: List[str],
) -> str:
    """Build a patch containing only source (non-test) files."""
    included = set(source_files)
    return build_unified_patch(patches, lambda f: f in included)
