"""
Instance type detection: bug-fix vs feature-addition.

After applying the test patch at the base commit:
  - If tests compile and fail  → Bug Fix
  - If tests don't compile due to missing methods → Feature Addition
  - Other compile errors → Error (skip)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from adapters.base import LanguageAdapter
    from repo_config import RepoConfig


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
    test_files: List[str],
    repo_dir: str,
    adapter: LanguageAdapter,
) -> List[str]:
    """
    Read test source files from the repo and extract test method names.
    Returns list of 'classname::methodName'.
    """
    test_ids: list[str] = []
    for filepath in test_files:
        if not any(filepath.endswith(ext) for ext in adapter.source_file_extensions):
            continue
        fqn = adapter.extract_test_fqn(filepath)
        if not fqn:
            continue
        full_path = os.path.join(repo_dir, filepath)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path) as f:
                source = f.read()
            methods = adapter.extract_test_methods_from_source(source)
            for method in methods:
                test_ids.append(f"{fqn}::{method}")
        except OSError:
            continue
    return test_ids


def detect_instance_type(
    test_files: List[str],
    repo_dir: str,
    timeout: int,
    adapter: LanguageAdapter,
    config: RepoConfig,
) -> DetectionResult:
    """
    Determine if the current state represents a bug fix or feature addition.

    Assumes:
      - Repo is checked out at the base commit
      - Test patch has already been applied (test files exist at merge-commit versions)

    Steps:
      1. Try compiling tests
      2. If compiles → run tests → if they fail → bug fix
      3. If doesn't compile → parse errors → if missing symbols → feature addition
    """
    result = DetectionResult(instance_type="error")

    # Step 1: Try to compile tests
    print("    [detect] Compiling test files...")
    compiles, compile_output = adapter.compile_tests(test_files, repo_dir, timeout, config)
    missing = adapter.extract_missing_symbols(compile_output)
    result.compile_output = compile_output[-3000:]

    if compiles:
        # Tests compile — this is a standard bug-fix candidate
        print("    [detect] Tests compile. Running tests (expecting FAIL)...")
        test_cmds = adapter.build_test_commands(test_files, config)
        passed, test_output = adapter.run_tests(test_files, repo_dir, timeout, config)
        result.fail_phase_output = test_output[-3000:]

        if passed:
            result.instance_type = "invalid"
            result.details = "Tests pass without fix — not a valid candidate"
            return result

        # Parse method-level failures from test reports
        report_files = adapter.find_test_reports(test_cmds, repo_dir)
        failed, passed_tests = adapter.parse_test_results(report_files)

        if not failed:
            # No test report results — could be a feature addition where
            # tests crashed at runtime (missing module/export/function).
            # Check test output for missing symbols before giving up.
            runtime_missing = adapter.extract_missing_symbols(test_output)
            if runtime_missing:
                result.instance_type = "feature_addition"
                result.missing_symbols = [s.to_dict() for s in runtime_missing]
                test_ids = _read_test_methods_from_repo(test_files, repo_dir, adapter)
                if not test_ids:
                    result.instance_type = "error"
                    result.details = "Feature addition detected but could not extract test methods from source"
                    return result
                result.fail_to_pass = test_ids
                result.details = (
                    f"Feature addition (runtime): {len(runtime_missing)} missing symbol(s), "
                    f"{len(result.fail_to_pass)} test(s)"
                )
                return result

            result.instance_type = "error"
            result.details = "Tests failed but no test report results found"
            return result

        result.instance_type = "bug_fix"
        result.fail_to_pass = failed
        result.details = f"Bug fix: {len(failed)} failing test(s)"
        return result

    # Tests don't compile — check if it's a feature addition
    print("    [detect] Tests don't compile. Analyzing errors...")

    if missing:
        result.instance_type = "feature_addition"
        result.missing_symbols = [s.to_dict() for s in missing]
        # Tests can't run (don't compile), so derive FAIL_TO_PASS from test methods in source
        test_ids = _read_test_methods_from_repo(test_files, repo_dir, adapter)
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
        error_lines = [
            ln for ln in compile_output.splitlines()
            if "error:" in ln.lower() or "error " in ln.lower()
        ]
        if error_lines:
            snippet = "; ".join(error_lines[:5])
            result.details = f"Compilation failed (no missing symbols found). Errors: {snippet[:500]}"
            print(f"    [detect] Compile errors found but no missing symbols:")
            for el in error_lines[:10]:
                print(f"      {el.strip()}")
        else:
            result.details = "Compilation failed for unknown reasons"
            tail = compile_output.strip().splitlines()[-10:]
            print(f"    [detect] No error lines found in compile output. Tail:")
            for tl in tail:
                print(f"      {tl.strip()}")

    return result
