"""Transformers adapter — Python + pytest (huggingface/transformers)."""

from __future__ import annotations

import os
import re
import subprocess
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from adapters.base import CompileError, LanguageAdapter, MissingSymbol

if TYPE_CHECKING:
    from repo_config import RepoConfig


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 600  # 10 minutes

DEFAULT_PYTEST_FLAGS = [
    "--tb=short",
    "--no-header",
    "-rN",
    "--junitxml=test-results/junit.xml",
]

# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_python_file(filename: str) -> bool:
    return filename.endswith(".py")


def _is_test_pattern(filename: str) -> bool:
    """Check if the filename matches pytest naming conventions."""
    basename = filename.rsplit("/", 1)[-1]
    return basename.startswith("test_") or basename.endswith("_test.py")


def _in_tests_dir(filename: str) -> bool:
    """Check if the file is inside the ``tests/`` directory."""
    return filename.startswith("tests/") or "/tests/" in filename


# ── Adapter ───────────────────────────────────────────────────────────────────


class TransformersAdapter(LanguageAdapter):
    """Adapter for huggingface/transformers (Python + pytest)."""

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def language_name(self) -> str:
        return "Python"

    @property
    def build_tool_name(self) -> str:
        return "pytest"

    @property
    def source_file_extensions(self) -> Tuple[str, ...]:
        return (".py",)

    # ── File classification ───────────────────────────────────────────

    def is_test_file(self, filename: str, config: RepoConfig) -> bool:
        if not _is_python_file(filename):
            return False
        if not _in_tests_dir(filename):
            return False
        if self.is_test_support_file(filename, config):
            return False
        if _is_test_pattern(filename):
            return True
        return False

    def is_source_file(self, filename: str, config: RepoConfig) -> bool:
        if not _is_python_file(filename):
            return False
        return not self.is_test_file(filename, config) and not self.is_test_support_file(filename, config)

    def is_test_support_file(self, filename: str, config: RepoConfig) -> bool:
        basename = filename.rsplit("/", 1)[-1]
        cfg_files = config.test_config_files if config else set()
        if basename in cfg_files:
            return True
        # conftest.py, fixtures, test utilities
        if basename == "conftest.py":
            return True
        if "/fixtures/" in filename or "/testing_utils" in filename:
            return True
        # tests/ helpers that are not test files themselves
        if _in_tests_dir(filename) and _is_python_file(filename) and not _is_test_pattern(filename):
            return True
        return False

    # ── PR pre-filtering ──────────────────────────────────────────────

    def has_test_and_source_files(self, patches: List[Dict[str, str]]) -> bool:
        has_test = False
        has_source = False
        for p in patches:
            fn = p["filename"]
            if not _is_python_file(fn):
                continue
            if _in_tests_dir(fn) and _is_test_pattern(fn):
                has_test = True
            elif fn.startswith("src/"):
                has_source = True
            if has_test and has_source:
                return True
        return has_test and has_source

    def has_test_files_in_pr(self, pr: Dict[str, Any]) -> bool:
        for p in pr.get("patches", []):
            fn = p.get("filename", "")
            if _is_python_file(fn) and _in_tests_dir(fn) and _is_test_pattern(fn):
                return True
        return False

    # ── Test identity extraction ──────────────────────────────────────

    def extract_test_fqn(self, filepath: str) -> Optional[str]:
        """
        Convert a test file path to a pytest-style module path.

        ``tests/models/bert/test_modeling_bert.py``
            → ``tests/models/bert/test_modeling_bert.py``

        pytest identifies tests by file path, so we return as-is.
        """
        if not _is_python_file(filepath):
            return None
        return filepath

    def extract_module(self, filepath: str) -> Optional[str]:
        """
        Extract the package/model area from a file path.

        ``src/transformers/models/bert/modeling_bert.py`` → ``models/bert``
        ``tests/models/bert/test_modeling_bert.py`` → ``models/bert``
        """
        parts = filepath.split("/")
        # Look for models/<name> pattern
        for i, part in enumerate(parts):
            if part == "models" and i + 1 < len(parts):
                return f"models/{parts[i + 1]}"
        # Fallback: first two path components under src/transformers/ or tests/
        if filepath.startswith("src/transformers/") and len(parts) >= 3:
            return parts[2]
        if filepath.startswith("tests/") and len(parts) >= 2:
            return parts[1]
        return filepath

    # ── Build & test commands ─────────────────────────────────────────

    def _get_pytest_flags(self, config: RepoConfig) -> List[str]:
        if config and config.extra.get("pytest_flags"):
            return config.extra["pytest_flags"]
        return DEFAULT_PYTEST_FLAGS

    def build_test_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        flags = " ".join(self._get_pytest_flags(config))
        # Group all test files into a single pytest invocation
        files_str = " ".join(f for f in test_files if _is_python_file(f))
        if not files_str:
            return []
        return [f"python -m pytest {files_str} {flags}"]

    def build_compile_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        """
        Python has no separate compile step.
        Use ``--collect-only`` to verify tests can be imported without running them.
        """
        files_str = " ".join(f for f in test_files if _is_python_file(f))
        if not files_str:
            return []
        return [f"python -m pytest --collect-only -q {files_str}"]

    def compile_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """
        Python has no compile step. Use ``--collect-only`` to check imports.

        Returns ``(True, output)`` if collection succeeds (tests are importable).
        Returns ``(False, output)`` on ImportError / SyntaxError.
        """
        commands = self.build_compile_commands(test_files, config)
        if not commands:
            return False, "No compile commands could be built"

        passed, output, _ = self.run_commands(commands, cwd, timeout, config)

        if passed:
            return True, output

        # Check if the failure is due to import/syntax errors vs test collection issues
        import_error_re = re.compile(
            r"(ImportError|ModuleNotFoundError|SyntaxError|NameError|AttributeError)"
        )
        if import_error_re.search(output):
            return False, output

        # Collection might report "no tests found" for some files — that's OK
        if "no tests ran" in output.lower() or "no tests collected" in output.lower():
            return True, output

        return False, output

    # ── Command runner hooks ─────────────────────────────────────────

    def _error_line_patterns(self) -> List[str]:
        return [
            "ImportError",
            "ModuleNotFoundError",
            "SyntaxError",
            "NameError",
            "AttributeError",
            "FAILED",
            "ERROR",
        ]

    def _build_env(self, config: RepoConfig) -> Dict[str, str]:
        return {
            "HF_HUB_DOWNLOAD_TIMEOUT": "60",
            # Disable tokenizers parallelism to avoid forking issues in tests
            "TOKENIZERS_PARALLELISM": "false",
        }

    # ── Test result parsing ───────────────────────────────────────────

    def find_test_reports(
        self, commands: List[str], repo_dir: str,
    ) -> List[str]:
        report_path = os.path.join(repo_dir, "test-results", "junit.xml")
        if os.path.isfile(report_path):
            return [report_path]
        return []

    def parse_test_results(
        self, report_files: List[str],
    ) -> Tuple[List[str], List[str]]:
        failed: list[str] = []
        passed: list[str] = []

        for xml_path in report_files:
            try:
                from junitparser import JUnitXml, TestCase, TestSuite
                xml = JUnitXml.fromfile(xml_path)
            except Exception:
                continue

            suites: list = []
            if isinstance(xml, TestSuite):
                suites = [xml]
            else:
                for item in xml:
                    if isinstance(item, TestSuite):
                        suites.append(item)

            for suite in suites:
                for case in suite:
                    if not isinstance(case, TestCase):
                        continue
                    classname = case.classname or ""
                    name = case.name or ""
                    if not name:
                        continue

                    # pytest JUnit: classname is dotted module, name is test method
                    test_id = f"{classname}::{name}" if classname else name

                    if case.result is None:
                        passed.append(test_id)
                    else:
                        result_types = case.result if isinstance(case.result, list) else [case.result]
                        is_failure = False
                        is_skipped = False
                        for r in result_types:
                            rtype = type(r).__name__.lower()
                            if "skip" in rtype:
                                is_skipped = True
                            elif "fail" in rtype or "error" in rtype:
                                is_failure = True

                        if is_skipped:
                            continue
                        elif is_failure:
                            failed.append(test_id)
                        else:
                            passed.append(test_id)

        return failed, passed

    def extract_test_methods_from_source(self, source_code: str) -> List[str]:
        """Extract ``def test_*`` method names from Python test source."""
        methods: list[str] = []
        pattern = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.MULTILINE)
        for m in pattern.finditer(source_code):
            methods.append(m.group(1))
        return methods

    # ── Compile error analysis ────────────────────────────────────────

    def parse_compile_errors(self, output: str) -> List[CompileError]:
        errors: list[CompileError] = []
        lines = output.splitlines()

        import_error_re = re.compile(
            r"(ImportError|ModuleNotFoundError):\s*(.*)"
        )
        syntax_error_re = re.compile(
            r'File "([^"]+)", line (\d+)'
        )
        name_error_re = re.compile(
            r"(NameError|AttributeError):\s*(.*)"
        )

        for line in lines:
            m = import_error_re.search(line)
            if m:
                errors.append(CompileError(raw=line.strip(), symbol=m.group(2), location=""))
                continue
            m = name_error_re.search(line)
            if m:
                errors.append(CompileError(raw=line.strip(), symbol=m.group(2), location=""))
                continue

        # Also extract file/line from tracebacks
        for i, line in enumerate(lines):
            m = syntax_error_re.search(line)
            if m and i + 1 < len(lines) and "SyntaxError" in lines[i + 1]:
                errors.append(CompileError(
                    raw=lines[i + 1].strip(),
                    symbol=lines[i + 1].strip(),
                    location=f"{m.group(1)}:{m.group(2)}",
                ))

        return errors

    def extract_missing_symbols(self, output: str) -> List[MissingSymbol]:
        symbols: list[MissingSymbol] = []

        # cannot import name 'Foo' from 'transformers'
        import_name_re = re.compile(r"cannot import name '(\w+)' from '([^']+)'")
        for m in import_name_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="class", name=m.group(1), params="", class_name=m.group(2),
            ))

        # No module named 'transformers.models.foo'
        no_module_re = re.compile(r"No module named '([^']+)'")
        for m in no_module_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="class", name=m.group(1), params="", class_name="",
            ))

        # AttributeError: type object 'FooModel' has no attribute 'bar'
        attr_re = re.compile(r"has no attribute '(\w+)'")
        for m in attr_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="method", name=m.group(1), params="", class_name="",
            ))

        # NameError: name 'FooClass' is not defined
        name_re = re.compile(r"name '(\w+)' is not defined")
        for m in name_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="variable", name=m.group(1), params="", class_name="",
            ))

        # Deduplicate
        seen: set[str] = set()
        unique: list[MissingSymbol] = []
        for s in symbols:
            key = f"{s.kind}:{s.class_name}.{s.name}({s.params})"
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    # ── Environment / Docker ──────────────────────────────────────────

    def check_build_tool_exists(self, clone_dir: str, config: RepoConfig) -> bool:
        return os.path.isfile(os.path.join(clone_dir, "setup.py")) or \
               os.path.isfile(os.path.join(clone_dir, "pyproject.toml"))

    def check_prerequisites(self, config: RepoConfig) -> bool:
        try:
            result = subprocess.run(["python3", "--version"], capture_output=True, timeout=10)
            version_output = result.stdout.decode().strip()
            print(f"  Python: {version_output}")
            m = re.match(r"Python (\d+)\.(\d+)", version_output)
            if m and (int(m.group(1)), int(m.group(2))) >= (3, 10):
                return True
            print(f"  ERROR: Python 3.10+ required, found {version_output}")
            return False
        except Exception as e:
            print(f"  ERROR: Could not determine Python version: {e}")
        return False

    def detect_runtime_version(
        self, clone_dir: str, config: RepoConfig,
    ) -> Optional[str]:
        python_version_file = os.path.join(clone_dir, ".python-version")
        if os.path.isfile(python_version_file):
            try:
                with open(python_version_file) as f:
                    version = f.read().strip()
                if version:
                    return version
            except OSError:
                pass
        return None

    def resolve_base_image(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> str:
        if runtime_version:
            ver = runtime_version.strip()
            return f"python:{ver}-bookworm"
        return config.base_image

    def _dockerfile_install_deps_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Create venv to avoid Ubuntu's externally-managed Python restriction",
            "RUN python3 -m venv /opt/venv",
            'ENV PATH="/opt/venv/bin:$PATH"',
            "",
            "# Install junitparser for test result parsing inside the container",
            "RUN pip install --no-cache-dir junitparser",
            "",
        ]

    def _dockerfile_base_env_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Transformers environment",
            'ENV PATH="/opt/venv/bin:$PATH"',
            'ENV HF_HUB_DOWNLOAD_TIMEOUT="60"',
            'ENV TOKENIZERS_PARALLELISM="false"',
            "",
        ]

    def _dockerfile_post_checkout_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Install transformers in editable mode with testing dependencies",
            'RUN pip install -e ".[testing]" 2>&1 | tail -20',
            "",
            "# Write rebuild script for dependency metadata changes",
            "RUN echo '#!/bin/bash' > /app/rebuild.sh && \\",
            '    echo \'pip install -e .\' >> /app/rebuild.sh && \\',
            "    chmod +x /app/rebuild.sh",
            "",
        ]

    def _dockerfile_final_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Verify pytest is available",
            "RUN python -m pytest --version",
            "",
        ]

    def generate_test_parser_script(self) -> Optional[str]:
        """Return a pytest JUnit XML parser script."""
        return '''#!/usr/bin/env python3
"""Parser for pytest JUnit XML test results (transformers)."""
import argparse
import json
import os
import sys
from pathlib import Path
from junitparser import JUnitXml, TestCase, TestSuite


def parse_junit_file(xml_path: str):
    passed, failed = [], []
    try:
        xml = JUnitXml.fromfile(xml_path)
    except Exception as e:
        print(f"Failed to parse {xml_path}: {e}", file=sys.stderr)
        return passed, failed

    suites = [xml] if isinstance(xml, TestSuite) else [s for s in xml if isinstance(s, TestSuite)]
    for suite in suites:
        for case in suite:
            if not isinstance(case, TestCase):
                continue
            classname = case.classname or ""
            name = case.name or ""
            if not name:
                continue
            test_id = f"{classname}::{name}" if classname else name
            if case.result is None:
                passed.append(test_id)
            else:
                results = case.result if isinstance(case.result, list) else [case.result]
                is_skip = any("skip" in type(r).__name__.lower() for r in results)
                is_fail = any(
                    "fail" in type(r).__name__.lower() or "error" in type(r).__name__.lower()
                    for r in results
                )
                if is_skip:
                    continue
                elif is_fail:
                    failed.append(test_id)
                else:
                    passed.append(test_id)
    return passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True,
                    help="Directory containing junit.xml")
    ap.add_argument("--output", required=True,
                    help="Output JSON file path")
    args = ap.parse_args()

    xml_path = os.path.join(args.report_dir, "junit.xml")
    if not os.path.isfile(xml_path):
        print(f"JUnit XML not found: {xml_path}", file=sys.stderr)
        json.dump({"passed": [], "failed": []}, open(args.output, "w"))
        return

    passed, failed = parse_junit_file(xml_path)
    print(f"Parsed {len(passed)} passed, {len(failed)} failed")
    with open(args.output, "w") as f:
        json.dump({"passed": passed, "failed": failed}, f, indent=2)


if __name__ == "__main__":
    main()
'''

    def git_clean_excludes(self) -> List[str]:
        # Keep the venv and egg-info to avoid full reinstall
        return ["/opt/venv/"]

    def bootstrap_repo(self, clone_dir: str, config: RepoConfig, timeout: int = 1800) -> Tuple[bool, str]:
        """Run ``pip install -e ".[testing]"`` after checkout."""
        cmd = 'pip install -e ".[testing]" 2>&1'
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=clone_dir,
                capture_output=True,
                timeout=timeout,
                env={
                    **os.environ,
                    "PATH": f"/opt/venv/bin:{os.environ.get('PATH', '')}",
                },
            )
            output = result.stdout.decode(errors="replace")
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")
                return False, f"Bootstrap failed (exit {result.returncode}):\n{output}\n{stderr}"
            return True, output
        except subprocess.TimeoutExpired:
            return False, f"Bootstrap timed out after {timeout}s"

    def generate_run_script(
        self,
        instance_id: str,
        commands: List[str],
        config: RepoConfig,
    ) -> str:
        commands_block = ""
        for i, cmd in enumerate(commands):
            commands_block += f"""
echo "=== Running pytest command {i + 1}/{len(commands)} ==="
{cmd}
CMD_EXIT=$?
if [ $CMD_EXIT -ne 0 ]; then
    echo "pytest command {i + 1} failed with exit code $CMD_EXIT"
    OVERALL_EXIT=1
fi
"""

        pytest_flags = " ".join(self._get_pytest_flags(config))

        return f"""#!/bin/bash
set -uo pipefail

# Run script for {instance_id}
# Auto-generated by the benchmark pipeline

cd /app
export PATH="/opt/venv/bin:$PATH"
export HF_HUB_DOWNLOAD_TIMEOUT=60
export TOKENIZERS_PARALLELISM=false

REPORT_DIR="/app/test-results"
mkdir -p "$REPORT_DIR"
OVERALL_EXIT=0

if [ $# -gt 0 ]; then
    TEST_FILES="$@"
    echo "Running with custom test files: $TEST_FILES"
    for tf in $(echo "$TEST_FILES" | tr ',' ' '); do
        python -m pytest "$tf" {pytest_flags}
        CMD_EXIT=$?
        if [ $CMD_EXIT -ne 0 ]; then
            OVERALL_EXIT=1
        fi
    done
else
    echo "Running pre-configured pytest commands..."
{commands_block}
fi

echo "=== Test execution complete ==="
exit $OVERALL_EXIT
"""

    def generate_test_script(self, config: RepoConfig) -> Optional[str]:
        """Return a pytest-specific ``test.sh`` for the Harbor container."""
        no_root_user = config.no_root_user

        return f"""#!/bin/bash
set -euo pipefail

# ── Harbor test.sh for transformers (pytest) ──────────────────────────────────
#
# This script is called by the harbor verifier. Steps:
#   1. Apply the test_patch (new / modified tests)
#   2. Run the tests via run_script.sh
#   3. Parse JUnit XML results → output.json
#   4. Evaluate pass / fail against fail_to_pass + pass_to_pass lists
#   5. Write reward (0 or 1) to /logs/verifier/reward.txt

CONFIG_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="/app"
LOG_DIR="/logs/verifier"
REPORT_DIR="/app/test-results"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# ── 1. Apply the test patch ──────────────────────────────────────────────────
cd "$REPO_DIR"
python3 -c "
import json, subprocess, sys, tempfile, os
with open('$CONFIG_DIR/config.json') as f:
    config = json.load(f)
test_patch = config.get('test_patch', '').strip()
if not test_patch:
    sys.exit(0)
if not test_patch.endswith(chr(10)):
    test_patch += chr(10)
with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tmp:
    tmp.write(test_patch)
    tmp_path = tmp.name
result = subprocess.run(['git', 'apply', '--verbose', tmp_path], capture_output=True, text=True)
os.unlink(tmp_path)
if result.returncode != 0:
    print('WARNING: git apply for test_patch failed, trying patch --fuzz=5', file=sys.stderr)
    print(result.stderr, file=sys.stderr)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tmp:
        tmp.write(test_patch)
        tmp_path = tmp.name
    subprocess.run(['patch', '--batch', '--fuzz=5', '-p1', '-i', tmp_path])
    os.unlink(tmp_path)
else:
    print('test_patch applied successfully')
    print(result.stdout)
"

# ── 2. Run the tests ────────────────────────────────────────────────────────
echo "Running tests..."

# Fix ownership for non-root user
chown -R {no_root_user}:{no_root_user} /app 2>/dev/null || true

export PATH="/opt/venv/bin:$PATH"
export HF_HUB_DOWNLOAD_TIMEOUT=60
export TOKENIZERS_PARALLELISM=false

su -s /bin/bash -c 'cd /app && export PATH="/opt/venv/bin:$PATH" && bash '"$CONFIG_DIR"'/run_script.sh' {no_root_user} \\
    > "$LOG_DIR/test_output.log" 2>&1 || true

# ── 3. Parse results ────────────────────────────────────────────────────────
echo "Parsing test results..."
python3 "$CONFIG_DIR/parser.py" \\
    --report-dir "$REPORT_DIR" \\
    --output "$LOG_DIR/output.json" 2>&1 || {{
    echo '{{"passed": [], "failed": []}}' > "$LOG_DIR/output.json"
}}

# ── 4. Evaluate ─────────────────────────────────────────────────────────────
echo "Evaluating results..."
python3 -c "
import json, sys

config = json.load(open('$CONFIG_DIR/config.json'))
results = json.load(open('$LOG_DIR/output.json'))

f2p = set(config.get('fail_to_pass', []))
p2p = set(config.get('pass_to_pass', []))
passed = set(results.get('passed', []))
failed = set(results.get('failed', []))

# All fail_to_pass tests must now pass
f2p_ok = f2p.issubset(passed)
# No pass_to_pass test should fail
p2p_ok = len(p2p & failed) == 0

reward = 1 if (f2p_ok and p2p_ok and len(f2p) > 0) else 0

f2p_label = 'PASS' if f2p_ok else 'FAIL'
p2p_label = 'PASS' if p2p_ok else 'FAIL'
print(f'fail_to_pass ({{len(f2p)}}): {{f2p_label}}')
print(f'  expected pass: {{sorted(f2p)}}')
print(f'  actually passed: {{sorted(f2p & passed)}}')
print(f'  still failing: {{sorted(f2p - passed)}}')
print(f'pass_to_pass ({{len(p2p)}}): {{p2p_label}}')
print(f'  newly broken: {{sorted(p2p & failed)}}')
print(f'reward: {{reward}}')

if reward == 1:
    print('\\nRESULT: PASSED')
else:
    print('\\nRESULT: FAILED')
    if f2p - passed:
        print(f'  fail_to_pass not satisfied: {{sorted(f2p - passed)}}')
    if p2p & failed:
        print(f'  pass_to_pass broken: {{sorted(p2p & failed)}}')

with open('$LOG_DIR/reward.txt', 'w') as f:
    f.write(str(reward))
sys.exit(0 if reward == 1 else 1)
"
"""
