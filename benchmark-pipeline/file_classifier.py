"""
File classification for PR patches.

Classifies files into three categories:
  - test files: test source code
  - source files: production source code (gold patch)
  - test-support files: utilities/configs that should ship with the test patch
    (test helpers, muted-tests.yml changes, etc.)
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from repo_config import RepoConfig


# Default test config filenames (used when no RepoConfig is provided)
_DEFAULT_TEST_CONFIG_FILES: Set[str] = {
    "muted-tests.yml",
    "muted-tests.yaml",
}

# Filename patterns for test helper/utility files
TEST_UTIL_PATTERNS = [
    re.compile(r".*TestUtils?\.java$"),
    re.compile(r".*TestHelper\.java$"),
    re.compile(r".*TestFixture\.java$"),
    re.compile(r".*Mock\w+\.java$"),
    re.compile(r".*Fake\w+\.java$"),
    re.compile(r".*TestCase\.java$"),
    re.compile(r".*Abstract\w*Test\w*\.java$"),
]


def _in_path(segment: str, filename: str) -> bool:
    """Check if a path segment appears in the filename (handles root-level paths)."""
    return segment in filename or filename.startswith(segment.lstrip("/"))


def is_test_file(
    filename: str,
    extra_test_path_segments: Optional[List[str]] = None,
) -> bool:
    """Check if a file lives in a test source tree."""
    if _in_path("/src/test/java/", filename):
        return True
    if _in_path("/src/test/resources/", filename):
        return True
    # Repo-specific extra test paths
    for segment in (extra_test_path_segments or []):
        if segment in filename:
            return True
    # Basename heuristic, but NOT for files in production source trees.
    # Without this guard, a file like src/main/java/.../ConnectionTest.java
    # would be misclassified as a test file and excluded from the gold patch.
    if _in_path("/src/main/", filename):
        return False
    basename = filename.rsplit("/", 1)[-1]
    if basename.endswith(("Test.java", "Tests.java", "IT.java", "TestCase.java")):
        return True
    return False


def is_test_config_file(
    filename: str,
    test_config_files: Optional[Set[str]] = None,
) -> bool:
    """Check if a file is a test-execution config (e.g. muted-tests.yml)."""
    basename = filename.rsplit("/", 1)[-1]
    cfgfiles = test_config_files if test_config_files is not None else _DEFAULT_TEST_CONFIG_FILES
    return basename in cfgfiles


def _looks_like_test_util(filename: str) -> bool:
    """Heuristic: does the filename look like a test utility class?"""
    basename = filename.rsplit("/", 1)[-1]
    return any(pat.match(basename) for pat in TEST_UTIL_PATTERNS)



def classify_files(
    patches: List[Dict],
    config: Optional[RepoConfig] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Split patch files into (test_files, source_files, test_support_files).

    test_support_files includes:
      - muted-tests.yml and similar test config files
      - Test utility classes whose filenames match known patterns
        (e.g. MockFoo.java, TestUtils.java)

    Only includes files that exist in the merge commit (skips 'removed').
    """
    extra_segments = config.extra_test_path_segments if config else None
    cfg_files = config.test_config_files if config else None

    test_files: list[str] = []
    source_files: list[str] = []
    test_support_files: list[str] = []

    for patch in patches:
        filename = patch["filename"]
        status = patch.get("status", "modified")
        if status == "removed":
            continue

        if is_test_config_file(filename, cfg_files):
            test_support_files.append(filename)
        elif is_test_file(filename, extra_segments):
            test_files.append(filename)
        else:
            source_files.append(filename)

    # Second pass: reclassify source files whose names match test-util patterns
    # (e.g. MockFoo.java, TestUtils.java) as test-support.
    if test_files and source_files:
        reclassified = [f for f in source_files if _looks_like_test_util(f)]
        for filename in reclassified:
            source_files.remove(filename)
            test_support_files.append(filename)

    return test_files, source_files, test_support_files
