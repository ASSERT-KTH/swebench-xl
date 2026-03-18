"""Kibana adapter — TypeScript + Jest (via ``node scripts/jest``)."""

from __future__ import annotations

import os
import re
import subprocess
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from junitparser import JUnitXml, TestCase, TestSuite

from adapters.base import CompileError, LanguageAdapter, MissingSymbol

if TYPE_CHECKING:
    from repo_config import RepoConfig


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 600  # 10 minutes

DEFAULT_JEST_FLAGS = ["--ci", "--no-cache", "--forceExit"]

# Common test-support patterns in Kibana
_SNAPSHOT_RE = re.compile(r"__snapshots__/.*\.snap$")
_MOCK_FILE_RE = re.compile(r".*\.mock\.(ts|tsx|js|jsx)$")
_TEST_HELPER_RE = re.compile(r".*(test_helpers?|testing|__fixtures__|fixtures|__mocks__)/.*\.(ts|tsx|js|jsx)$")
_JEST_CONFIG_RE = re.compile(r"jest\.(config|setup|integration\.config)\.(js|ts|mjs)$")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_ts_js_file(filename: str) -> bool:
    """Check if the file is a TypeScript or JavaScript source file."""
    return filename.endswith((".ts", ".tsx", ".js", ".jsx"))


def _is_test_pattern(filename: str) -> bool:
    """Check if the filename matches test naming conventions."""
    basename = filename.rsplit("/", 1)[-1]
    return bool(
        basename.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx"))
        or basename.endswith((".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx"))
    )


def _in_test_dir(filename: str) -> bool:
    """Check if the file is inside a ``__tests__`` directory."""
    return "/__tests__/" in filename or filename.startswith("__tests__/")


# ── Adapter ───────────────────────────────────────────────────────────────────

class KibanaAdapter(LanguageAdapter):
    """Adapter for Kibana (TypeScript + Jest via ``node scripts/jest``)."""

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def language_name(self) -> str:
        return "TypeScript"

    @property
    def build_tool_name(self) -> str:
        return "Jest"

    @property
    def source_file_extensions(self) -> Tuple[str, ...]:
        return (".ts", ".tsx", ".js", ".jsx")

    # ── File classification ───────────────────────────────────────────

    def is_test_file(self, filename: str, config: RepoConfig) -> bool:
        if not _is_ts_js_file(filename):
            return False
        if _is_test_pattern(filename):
            return True
        if _in_test_dir(filename):
            return True
        extra_segments = config.extra_test_path_segments if config else []
        for segment in (extra_segments or []):
            if segment in filename:
                return True
        return False

    def is_source_file(self, filename: str, config: RepoConfig) -> bool:
        if not _is_ts_js_file(filename):
            return False
        return not self.is_test_file(filename, config) and not self.is_test_support_file(filename, config)

    def is_test_support_file(self, filename: str, config: RepoConfig) -> bool:
        basename = filename.rsplit("/", 1)[-1]
        cfg_files = config.test_config_files if config else set()
        if basename in cfg_files:
            return True
        if _SNAPSHOT_RE.search(filename):
            return True
        if _MOCK_FILE_RE.match(basename):
            return True
        if _TEST_HELPER_RE.search(filename):
            return True
        if _JEST_CONFIG_RE.match(basename):
            return True
        return False

    # ── PR pre-filtering ──────────────────────────────────────────────

    def has_test_and_source_files(self, patches: List[Dict[str, str]]) -> bool:
        has_test = False
        has_source = False
        for p in patches:
            fn = p["filename"]
            if not _is_ts_js_file(fn):
                continue
            if _is_test_pattern(fn) or _in_test_dir(fn):
                has_test = True
            elif not _SNAPSHOT_RE.search(fn) and not _MOCK_FILE_RE.match(fn.rsplit("/", 1)[-1]):
                has_source = True
            if has_test and has_source:
                return True
        return has_test and has_source

    def has_test_files_in_pr(self, pr: Dict[str, Any]) -> bool:
        for p in pr.get("patches", []):
            fn = p.get("filename", "")
            if _is_test_pattern(fn) or (_is_ts_js_file(fn) and _in_test_dir(fn)):
                return True
        return False

    # ── Test identity extraction ──────────────────────────────────────

    def extract_test_fqn(self, filepath: str) -> Optional[str]:
        """Return the relative file path — Jest identifies tests by path."""
        if not _is_ts_js_file(filepath):
            return None
        return filepath

    def extract_module(self, filepath: str) -> Optional[str]:
        """
        Extract the Kibana plugin/package path from a file path.

        Examples:
            ``'x-pack/platform/plugins/shared/fleet/server/...'``
                → ``'x-pack/platform/plugins/shared/fleet'``
            ``'src/platform/packages/shared/kbn-lens-embeddable-utils/...'``
                → ``'src/platform/packages/shared/kbn-lens-embeddable-utils'``
        """
        parts = filepath.split("/")

        # Walk down to find the plugin/package boundary.
        # Kibana plugins live under .../plugins/... and packages under .../packages/...
        for i, part in enumerate(parts):
            if part in ("plugins", "packages") and i + 2 < len(parts):
                # plugins/<scope>/<name> or packages/<scope>/<name>
                # Sometimes "shared" is the scope: plugins/shared/fleet
                # Or directly: plugins/fleet
                candidate = "/".join(parts[: i + 3])
                return candidate

        # Fallback: first two directory components
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return filepath

    # ── Build & test commands ─────────────────────────────────────────

    def _get_jest_flags(self, config: RepoConfig) -> List[str]:
        if config and config.extra.get("jest_flags"):
            return config.extra["jest_flags"]
        return DEFAULT_JEST_FLAGS

    def build_test_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        flags = " ".join(self._get_jest_flags(config))
        commands = []
        for filepath in test_files:
            if not _is_ts_js_file(filepath):
                continue
            cmd = f"node scripts/jest {filepath} {flags}"
            commands.append(cmd)
        return commands

    def run_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """Clean stale JUnit reports before running tests."""
        # Kibana's built-in JUnit reporter writes to <repo>/target/junit/
        report_dir = os.path.join(cwd, "target", "junit")
        if os.path.isdir(report_dir):
            import shutil
            shutil.rmtree(report_dir)
        return super().run_tests(test_files, cwd, timeout, config)

    def build_compile_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        # Same as test commands — Jest compiles and runs in one step
        return self.build_test_commands(test_files, config)

    def compile_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """
        Override: Jest has no separate compile step — compilation and test
        execution happen together.  We run the tests and then inspect the
        output to distinguish genuine compile/import errors from normal
        test-assertion failures.

        Returns ``(True, output)`` when tests actually **ran** (even if some
        failed), because that means compilation succeeded and the instance
        detector should proceed to the run-tests / bug-fix detection path.

        Returns ``(False, output)`` only when the tests could not run due to
        actual compilation errors (missing modules, syntax errors, etc.).
        """
        commands = self.build_compile_commands(test_files, config)
        if not commands:
            return False, "No compile commands could be built"

        passed, output, _ = self.run_commands(commands, cwd, timeout, config)

        if passed:
            # All tests passed — compilation obviously succeeded
            return True, output

        # Tests failed (exit code != 0).  Distinguish between:
        #   (a) Tests ran but some assertions failed → compilation OK
        #   (b) Tests could not run due to compile/import errors → compilation failed
        #
        # Jest prints a summary line like "Tests: 4 failed, 42 passed, 46 total"
        # or "Test Suites: 1 failed, 1 total" when tests actually executed.
        _ran_re = re.compile(r"Test Suites:\s+.*\d+ total|Tests:\s+.*\d+ total")
        if _ran_re.search(output):
            # Tests ran (some failed) → compilation succeeded
            return True, output

        # No test summary → likely a genuine compile/import error
        return False, output

    # ── Command runner hooks ─────────────────────────────────────────

    def _error_line_patterns(self) -> List[str]:
        return [
            "Cannot find module",
            "Cannot find name",
            "Property",
            "does not exist on type",
            "TS2339",
            "TS2304",
            "TS2305",
            "SyntaxError",
            "Module not found",
        ]

    def _build_env(self, config: RepoConfig) -> Dict[str, str]:
        return {
            "NODE_OPTIONS": "--max-old-space-size=4096",
            # Kibana's built-in JUnit reporter only writes when CI is set
            "CI": "true",
        }

    # ── Test result parsing ───────────────────────────────────────────

    def find_test_reports(
        self, commands: List[str], repo_dir: str,
    ) -> List[str]:
        # Kibana's built-in JUnit reporter writes to <repo>/target/junit/
        report_dir = os.path.join(repo_dir, "target", "junit")
        xml_files: list[str] = []
        if os.path.isdir(report_dir):
            for dirpath, _dirs, files in os.walk(report_dir):
                for fname in files:
                    if fname.endswith(".xml"):
                        xml_files.append(os.path.join(dirpath, fname))
        return xml_files

    def parse_test_results(
        self, report_files: List[str],
    ) -> Tuple[List[str], List[str]]:
        failed: list[str] = []
        passed: list[str] = []

        for xml_path in report_files:
            try:
                xml = JUnitXml.fromfile(xml_path)
            except Exception:
                continue

            suites: list[TestSuite] = []
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

                    # Jest JUnit: classname is the filepath, name is the test title
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
        """Extract test names from ``it()`` / ``test()`` calls."""
        methods: list[str] = []
        # Match: it('name', ...) / it("name", ...) / it(`name`, ...)
        # Also: test('name', ...) / test("name", ...)
        pattern = re.compile(
            r"""(?:^|\W)(?:it|test)\s*\(\s*(?:"""
            r"""'([^']*)'|"([^"]*)"|`([^`]*)`)""",
            re.MULTILINE,
        )
        for m in pattern.finditer(source_code):
            name = m.group(1) or m.group(2) or m.group(3)
            if name:
                methods.append(name)
        return methods

    # ── Compile error analysis ────────────────────────────────────────

    def parse_compile_errors(self, output: str) -> List[CompileError]:
        errors: list[CompileError] = []
        lines = output.splitlines()
        # TypeScript errors: path/to/file.ts(line,col): error TS2xxx: message
        ts_error_re = re.compile(
            r"(.+\.tsx?)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.*)"
        )
        # Jest-reported errors: common patterns
        cannot_find_re = re.compile(
            r"(Cannot find (?:module|name) '[^']+'"
            r"|Module not found.*"
            r"|Property '(\w+)' does not exist on type '([^']+)'"
            r"|has no exported member '(\w+)')"
        )

        for line in lines:
            m = ts_error_re.match(line.strip())
            if m:
                errors.append(CompileError(
                    raw=line.strip(),
                    symbol=m.group(5),
                    location=f"{m.group(1)}:{m.group(2)}",
                ))
                continue

            m = cannot_find_re.search(line)
            if m:
                errors.append(CompileError(raw=line.strip(), symbol=m.group(0), location=""))
        return errors

    def extract_missing_symbols(self, output: str) -> List[MissingSymbol]:
        symbols: list[MissingSymbol] = []

        # Property 'foo' does not exist on type 'Bar'
        prop_re = re.compile(r"Property '(\w+)' does not exist on type '([^']+)'")
        for m in prop_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="method", name=m.group(1), params="", class_name=m.group(2),
            ))

        # Cannot find name 'SomeName'
        name_re = re.compile(r"Cannot find name '(\w+)'")
        for m in name_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="variable", name=m.group(1), params="", class_name="",
            ))

        # has no exported member 'SomeName'
        export_re = re.compile(r"has no exported member '(\w+)'")
        for m in export_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="class", name=m.group(1), params="", class_name="",
            ))

        # Cannot find module 'some/module'
        mod_re = re.compile(r"Cannot find module '([^']+)'")
        for m in mod_re.finditer(output):
            symbols.append(MissingSymbol(
                kind="class", name=m.group(1), params="", class_name="",
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
        return os.path.isfile(os.path.join(clone_dir, "package.json"))

    def check_prerequisites(self, config: RepoConfig) -> bool:
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, timeout=10)
            version_output = result.stdout.decode().strip()
            print(f"  Node.js: {version_output}")
            # Expect v18+ or v20+
            m = re.match(r"v(\d+)", version_output)
            if m and int(m.group(1)) >= 18:
                return True
            print(f"  ERROR: Node.js 18+ required, found {version_output}")
            return False
        except Exception as e:
            print(f"  ERROR: Could not determine Node.js version: {e}")
        return False

    def detect_runtime_version(
        self, clone_dir: str, config: RepoConfig,
    ) -> Optional[str]:
        node_version_file = os.path.join(clone_dir, ".node-version")
        if os.path.isfile(node_version_file):
            try:
                with open(node_version_file) as f:
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
            # Strip leading 'v' if present
            ver = runtime_version.lstrip("v")
            return f"node:{ver}-bookworm"
        return config.base_image

    def _dockerfile_install_deps_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Install junitparser for test result parsing inside the container",
            "RUN pip3 install --no-cache-dir junitparser",
            "",
            "# Install yarn globally",
            "RUN corepack enable && corepack prepare yarn@stable --activate || npm install -g yarn",
            "",
        ]

    def _dockerfile_post_checkout_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        no_root_user = config.no_root_user
        return [
            "# Set Node.js memory limit for build",
            'ENV NODE_OPTIONS="--max-old-space-size=4096"',
            "",
            "# Install dependencies",
            "RUN yarn kbn bootstrap 2>&1 | tail -20 || yarn install --frozen-lockfile 2>&1 | tail -20",
            "",
        ]

    def _dockerfile_final_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Verify Jest is available",
            "RUN node scripts/jest --listTests 2>/dev/null | head -5 || echo 'Jest pre-warm skipped'",
            "",
        ]

    def git_clean_excludes(self) -> List[str]:
        return ["node_modules/", ".yarn/", ".pnp.*"]

    def bootstrap_repo(self, clone_dir: str, config: RepoConfig, timeout: int = 1800) -> Tuple[bool, str]:
        """Run ``yarn kbn bootstrap`` to install dependencies after checkout."""
        cmd = "yarn kbn bootstrap 2>&1 || yarn install --frozen-lockfile 2>&1"
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=clone_dir,
                capture_output=True,
                timeout=timeout,
                env={**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096"},
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
        flags = self._get_jest_flags(config)
        flags_str = " ".join(flags) if flags else "--ci --no-cache --forceExit"

        commands_block = ""
        for i, cmd in enumerate(commands):
            commands_block += f"""
echo "=== Running Jest command {i + 1}/{len(commands)} ==="
{cmd}
CMD_EXIT=$?
if [ $CMD_EXIT -ne 0 ]; then
    echo "Jest command {i + 1} failed with exit code $CMD_EXIT"
    OVERALL_EXIT=1
fi
"""

        return f"""#!/bin/bash
set -uo pipefail

# Run script for {instance_id}
# Auto-generated by the benchmark pipeline

cd /app
# Kibana's built-in JUnit reporter writes when CI is set
export CI=true
export JEST_REPORT_DIR="/app/target/junit"
mkdir -p "$JEST_REPORT_DIR"
OVERALL_EXIT=0

if [ $# -gt 0 ]; then
    TEST_FILES="$@"
    echo "Running with custom test files: $TEST_FILES"
    for tf in $(echo "$TEST_FILES" | tr ',' ' '); do
        node scripts/jest "$tf" {flags_str}
        CMD_EXIT=$?
        if [ $CMD_EXIT -ne 0 ]; then
            OVERALL_EXIT=1
        fi
    done
else
    echo "Running pre-configured Jest commands..."
{commands_block}
fi

echo "=== Test execution complete ==="
exit $OVERALL_EXIT
"""

    def generate_test_script(self, config: RepoConfig) -> Optional[str]:
        """
        Return a Jest-specific ``test.sh`` for the Harbor container.

        The default template is Gradle-centric, so we override it for Jest.
        """
        no_root_user = config.no_root_user

        return f"""#!/bin/bash
set -euo pipefail

# ── Harbor test.sh for Kibana (Jest) ──────────────────────────────────────────
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
mkdir -p "$LOG_DIR"

# ── 1. Apply the test patch ──────────────────────────────────────────────────
cd "$REPO_DIR"
TEST_PATCH="$CONFIG_DIR/test_patch.diff"
if [ -f "$TEST_PATCH" ] && [ -s "$TEST_PATCH" ]; then
    echo "Applying test patch..."
    git apply --allow-empty "$TEST_PATCH" 2>&1 | tee "$LOG_DIR/patch.log" || {{
        echo "WARNING: git apply failed, trying patch -p1..."
        patch -p1 < "$TEST_PATCH" 2>&1 | tee -a "$LOG_DIR/patch.log" || true
    }}
fi

# ── 2. Run the tests ────────────────────────────────────────────────────────
echo "Running tests..."
# Kill any stale node processes
pkill -f 'node scripts/jest' 2>/dev/null || true

# Fix ownership for non-root user
chown -R {no_root_user}:{no_root_user} /app 2>/dev/null || true

export CI=true
export JEST_REPORT_DIR="/app/target/junit"
mkdir -p "$JEST_REPORT_DIR"

su -s /bin/bash -c 'cd /app && bash '"$CONFIG_DIR"'/run_script.sh' {no_root_user} \\
    > "$LOG_DIR/test_output.log" 2>&1 || true

# ── 3. Parse results ────────────────────────────────────────────────────────
echo "Parsing test results..."
python3 "$CONFIG_DIR/parser.py" \\
    --report-dir "$JEST_REPORT_DIR" \\
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

print(f'fail_to_pass ({{len(f2p)}}): {{\"PASS\" if f2p_ok else \"FAIL\"}}')
print(f'  expected pass: {{sorted(f2p)}}')
print(f'  actually passed: {{sorted(f2p & passed)}}')
print(f'  still failing: {{sorted(f2p - passed)}}')
print(f'pass_to_pass ({{len(p2p)}}): {{\"PASS\" if p2p_ok else \"FAIL\"}}')
print(f'  newly broken: {{sorted(p2p & failed)}}')
print(f'reward: {{reward}}')

with open('$LOG_DIR/reward.txt', 'w') as f:
    f.write(str(reward))
sys.exit(0 if reward == 1 else 1)
"
"""
