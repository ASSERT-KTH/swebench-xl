"""
Instance type detection: bug-fix vs feature-addition.

After applying the test patch at the base commit:
  - If tests compile and fail  → Bug Fix
  - If tests don't compile due to missing methods → Feature Addition
  - Other compile errors → Error (skip)
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from gradle_runner import (
    build_test_commands,
    compile_tests,
    extract_missing_symbols,
    extract_test_fqn,
    run_tests,
)
from test_parser import find_report_xmls, parse_results, parse_test_methods_from_source


@dataclass
class DetectionResult:
    instance_type: str  # "bug_fix", "feature_addition", "invalid", "error"
    fail_to_pass: List[str] = field(default_factory=list)
    pass_to_pass: List[str] = field(default_factory=list)
    missing_symbols: List[dict] = field(default_factory=list)
    compile_output: str = ""
    fail_phase_output: str = ""
    pass_phase_output: str = ""
    details: str = ""


def _read_test_methods_from_repo(
    test_files: List[str], repo_dir: str
) -> List[str]:
    """
    Read test source files from the repo and extract @Test method names.
    Returns list of 'classname::methodName'.
    """
    test_ids: list[str] = []
    for filepath in test_files:
        if not filepath.endswith(".java"):
            continue
        fqn = extract_test_fqn(filepath)
        if not fqn:
            continue
        full_path = os.path.join(repo_dir, filepath)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path) as f:
                source = f.read()
            methods = parse_test_methods_from_source(source)
            for method in methods:
                test_ids.append(f"{fqn}::{method}")
        except OSError:
            continue
    return test_ids


def detect_instance_type(
    java_test_files: List[str],
    repo_dir: str,
    timeout: int = 600,
) -> DetectionResult:
    """
    Determine if the current state represents a bug fix or feature addition.

    Assumes:
      - Repo is checked out at the base commit
      - Test patch has already been applied (test files exist at merge-commit versions)

    Steps:
      1. Try compileTestJava
      2. If compiles → run tests → if they fail → bug fix
      3. If doesn't compile → parse errors → if missing methods → feature addition
    """
    result = DetectionResult(instance_type="error")

    # Step 1: Try to compile tests
    print("    [detect] Compiling test files...")
    compiles, compile_output = compile_tests(java_test_files, repo_dir, timeout)
    # Parse errors from full output before truncating for storage
    missing = extract_missing_symbols(compile_output)
    result.compile_output = compile_output[-3000:]

    if compiles:
        # Tests compile — this is a standard bug-fix candidate
        print("    [detect] Tests compile. Running tests (expecting FAIL)...")
        gradle_cmds = build_test_commands(java_test_files)
        passed, test_output = run_tests(java_test_files, repo_dir, timeout)
        result.fail_phase_output = test_output[-3000:]

        if passed:
            result.instance_type = "invalid"
            result.details = "Tests pass without fix — not a valid candidate"
            return result

        # Parse method-level failures from JUnit XML
        xml_files = find_report_xmls(gradle_cmds, repo_dir)
        failed, passed_tests = parse_results(xml_files)

        if not failed:
            result.instance_type = "error"
            result.details = "Tests failed but no JUnit XML results found"
            return result

        result.instance_type = "bug_fix"
        result.fail_to_pass = failed
        result.details = f"Bug fix: {len(failed)} failing test(s)"
        return result

    # Tests don't compile — check if it's a feature addition
    print("    [detect] Tests don't compile. Analyzing errors...")

    if missing:
        result.instance_type = "feature_addition"
        result.missing_symbols = missing
        # Tests can't run (don't compile), so derive FAIL_TO_PASS from @Test methods in source
        test_ids = _read_test_methods_from_repo(java_test_files, repo_dir)
        if not test_ids:
            result.instance_type = "error"
            result.details = "Feature addition detected but could not extract test methods from source"
            return result
        result.fail_to_pass = test_ids
        result.details = (
            f"Feature addition: {len(missing)} missing symbol(s), "
            f"{len(result.fail_to_pass)} test(s)"
        )
    else:
        result.instance_type = "error"
        result.details = "Compilation failed for unknown reasons"

    return result


def format_symbol_hints(missing_symbols: List[dict]) -> str:
    """
    Format missing symbol info for inclusion in the task instruction.
    Handles methods, classes, variables, and constructors.
    """
    if not missing_symbols:
        return ""

    lines = ["## Hint: Symbols to Implement", ""]
    lines.append(
        "The following symbols need to be created as part of this task:"
    )
    lines.append("")
    for s in missing_symbols:
        cls = s.get("class", "Unknown")
        name = s.get("name", s.get("method", "unknown"))
        kind = s.get("kind", "method")
        params = s.get("params", "")
        if kind == "method":
            lines.append(f"- Method `{name}({params})` in `{cls}`")
        elif kind == "constructor":
            lines.append(f"- Constructor `{name}({params})` in `{cls}`")
        elif kind == "class":
            lines.append(f"- Class `{name}`")
        elif kind == "variable":
            lines.append(f"- Variable/field `{name}` in `{cls}`")
        else:
            lines.append(f"- `{name}` in `{cls}`")
    return "\n".join(lines)


# Backward-compatible alias
format_method_signatures = format_symbol_hints
