"""VS Code adapter — TypeScript + Mocha (microsoft/vscode)."""

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

# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_ts_js_file(filename: str) -> bool:
    """Check if the file is a TypeScript or JavaScript source file."""
    return filename.endswith((".ts", ".tsx", ".js", ".jsx"))


def _is_test_pattern(filename: str) -> bool:
    """Check if the filename matches VS Code test naming conventions."""
    basename = filename.rsplit("/", 1)[-1]
    return basename.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx"))


def _in_test_dir(filename: str) -> bool:
    """Check if the file is inside a ``test/`` directory under ``src/vs/``."""
    return "/test/" in filename


_SNAPSHOT_RE = re.compile(r"__snapshots__/.*\.snap$")
_MOCK_FILE_RE = re.compile(r".*\.mock\.(ts|tsx|js|jsx)$")
_TEST_FIXTURE_RE = re.compile(
    r".*(fixtures?|__fixtures__|__mocks__|testUtils)/.*\.(ts|tsx|js|jsx)$"
)


# ── Adapter ───────────────────────────────────────────────────────────────────


class VSCodeAdapter(LanguageAdapter):
    """Adapter for microsoft/vscode (TypeScript + Mocha)."""

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def language_name(self) -> str:
        return "TypeScript"

    @property
    def build_tool_name(self) -> str:
        return "Mocha"

    @property
    def source_file_extensions(self) -> Tuple[str, ...]:
        return (".ts", ".tsx", ".js", ".jsx")

    # ── File classification ───────────────────────────────────────────

    def is_test_file(self, filename: str, config: RepoConfig) -> bool:
        if not _is_ts_js_file(filename):
            return False
        if _is_test_pattern(filename):
            return True
        if _in_test_dir(filename) and _is_ts_js_file(filename):
            basename = filename.rsplit("/", 1)[-1]
            # Files directly in test/ that are actual test files
            if basename.startswith("test") or basename.endswith((".test.ts", ".test.js")):
                return True
        extra_segments = config.extra_test_path_segments if config else []
        for segment in (extra_segments or []):
            if segment in filename:
                return True
        return False

    def is_source_file(self, filename: str, config: RepoConfig) -> bool:
        if not _is_ts_js_file(filename):
            return False
        return (
            not self.is_test_file(filename, config)
            and not self.is_test_support_file(filename, config)
        )

    def is_test_support_file(self, filename: str, config: RepoConfig) -> bool:
        basename = filename.rsplit("/", 1)[-1]
        cfg_files = config.test_config_files if config else set()
        if basename in cfg_files:
            return True
        if _SNAPSHOT_RE.search(filename):
            return True
        if _MOCK_FILE_RE.match(basename):
            return True
        if _TEST_FIXTURE_RE.search(filename):
            return True
        # Common VS Code test utilities
        if "/test/" in filename and basename.startswith("utils"):
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
            elif fn.startswith("src/") and not _SNAPSHOT_RE.search(fn):
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
        """Return the relative file path — Mocha identifies tests by path."""
        if not _is_ts_js_file(filepath):
            return None
        return filepath

    def extract_module(self, filepath: str) -> Optional[str]:
        """
        Extract the VS Code module/area from a file path.

        ``src/vs/editor/contrib/hover/browser/hover.ts``
            → ``vs/editor/contrib/hover``
        ``src/vs/workbench/services/search/common/search.ts``
            → ``vs/workbench/services/search``
        ``extensions/git/src/git.ts``
            → ``extensions/git``
        """
        parts = filepath.split("/")

        # Extension path: extensions/<name>/...
        if filepath.startswith("extensions/") and len(parts) >= 2:
            return f"extensions/{parts[1]}"

        # Main source: src/vs/<area>/...
        if filepath.startswith("src/vs/") and len(parts) >= 4:
            # Return up to 4 levels: vs/<area>/<sub>/<component>
            depth = min(len(parts) - 1, 5)  # skip 'src' prefix, cap at 5
            return "/".join(parts[1:depth])

        # Fallback
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return filepath

    # ── Build & test commands ─────────────────────────────────────────

    def build_test_commands(
        self,
        test_files: List[str],
        config: RepoConfig,
    ) -> List[str]:
        """
        Build commands to run VS Code unit tests.

        VS Code uses ``./scripts/test.sh`` to run Mocha-based unit tests
        inside Electron.  Passing ``--tfs unittest`` activates the built-in
        ``MochaJUnitReporter`` which writes JUnit XML to
        ``$BUILD_ARTIFACTSTAGINGDIRECTORY/test-results/``.
        """
        commands = []
        for filepath in test_files:
            if not _is_ts_js_file(filepath):
                continue
            cmd = f"./scripts/test.sh --run {filepath} --tfs unittest"
            commands.append(cmd)
        return commands

    def build_compile_commands(
        self,
        test_files: List[str],
        config: RepoConfig,
    ) -> List[str]:
        """
        Build compilation check commands.

        VS Code compiles via ``npm run compile`` (gulp). We run a full compile
        to verify TypeScript compiles cleanly.
        """
        return ["npm run compile"]

    def compile_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """
        Compile TypeScript and check for errors.

        Returns ``(True, output)`` when compilation succeeds.
        Returns ``(False, output)`` on TypeScript compile errors.
        """
        commands = self.build_compile_commands(test_files, config)
        if not commands:
            return False, "No compile commands could be built"

        passed, output, _ = self.run_commands(commands, cwd, timeout, config)

        if passed:
            return True, output

        # Check for actual TS compile errors vs other issues
        ts_error_re = re.compile(r"error TS\d+:")
        if ts_error_re.search(output):
            return False, output

        # Build script failures that aren't TS errors might be environment issues
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
            "TS2307",
            "TS2345",
            "SyntaxError",
            "Module not found",
            "error TS",
        ]

    def _build_env(self, config: RepoConfig) -> Dict[str, str]:
        return {
            "NODE_OPTIONS": "--max-old-space-size=8192",
            # Skip strict Node.js version check in preinstall.ts
            "VSCODE_SKIP_NODE_VERSION_CHECK": "1",
        }

    def run_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """Recompile, clean stale reports, and run tests.

        VS Code's test runner loads compiled ``.js`` from the ``out/``
        directory, **not** TypeScript sources.  Any change to ``.ts`` files
        (source fix, test patch) must be recompiled before tests will
        reflect those changes.  Without this step every instance would
        report ``invalid_tests_fail_with_fix`` because the runner would
        still execute the old compiled output.
        """
        import shutil

        # 1. Recompile so out/ reflects the latest .ts changes
        print("    [vscode] Recompiling before running tests...")
        compile_ok, compile_out = self.compile_tests(test_files, cwd, timeout, config)
        if not compile_ok:
            return False, f"Recompile failed before test run:\n{compile_out}"

        # 2. Clean stale JUnit reports
        report_dir = os.path.join(cwd, "test-results")
        if os.path.isdir(report_dir):
            shutil.rmtree(report_dir)

        # 3. Set BUILD_ARTIFACTSTAGINGDIRECTORY so the MochaJUnitReporter
        #    writes XML to <cwd>/test-results/
        os.environ["BUILD_ARTIFACTSTAGINGDIRECTORY"] = cwd

        return super().run_tests(test_files, cwd, timeout, config)

    # ── Test result parsing ───────────────────────────────────────────

    def find_test_reports(
        self,
        commands: List[str],
        repo_dir: str,
    ) -> List[str]:
        # VS Code test runner can produce JUnit XML via mocha-junit-reporter
        report_dir = os.path.join(repo_dir, "test-results")
        xml_files: list[str] = []
        if os.path.isdir(report_dir):
            for dirpath, _dirs, files in os.walk(report_dir):
                for fname in files:
                    if fname.endswith(".xml"):
                        xml_files.append(os.path.join(dirpath, fname))
        return xml_files

    def parse_test_results(
        self,
        report_files: List[str],
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

                    test_id = f"{classname}::{name}" if classname else name

                    if case.result is None:
                        passed.append(test_id)
                    else:
                        result_types = (
                            case.result
                            if isinstance(case.result, list)
                            else [case.result]
                        )
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
        """Extract test names from ``test()`` / ``it()`` / ``suite()`` calls."""
        methods: list[str] = []
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

        # TypeScript errors: path/file.ts(line,col): error TS2xxx: message
        ts_error_re = re.compile(
            r"(.+\.tsx?)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.*)"
        )
        cannot_find_re = re.compile(
            r"(Cannot find (?:module|name) '[^']+'"
            r"|Module not found.*"
            r"|Property '(\w+)' does not exist on type '([^']+)'"
            r"|has no exported member '(\w+)')"
        )

        for line in lines:
            m = ts_error_re.match(line.strip())
            if m:
                errors.append(
                    CompileError(
                        raw=line.strip(),
                        symbol=m.group(5),
                        location=f"{m.group(1)}:{m.group(2)}",
                    )
                )
                continue

            m = cannot_find_re.search(line)
            if m:
                errors.append(
                    CompileError(raw=line.strip(), symbol=m.group(0), location="")
                )
        return errors

    def extract_missing_symbols(self, output: str) -> List[MissingSymbol]:
        symbols: list[MissingSymbol] = []

        # Property 'foo' does not exist on type 'Bar'
        prop_re = re.compile(r"Property '(\w+)' does not exist on type '([^']+)'")
        for m in prop_re.finditer(output):
            symbols.append(
                MissingSymbol(
                    kind="method", name=m.group(1), params="", class_name=m.group(2)
                )
            )

        # Cannot find name 'SomeName'
        name_re = re.compile(r"Cannot find name '(\w+)'")
        for m in name_re.finditer(output):
            symbols.append(
                MissingSymbol(kind="variable", name=m.group(1), params="", class_name="")
            )

        # has no exported member 'SomeName'
        export_re = re.compile(r"has no exported member '(\w+)'")
        for m in export_re.finditer(output):
            symbols.append(
                MissingSymbol(kind="class", name=m.group(1), params="", class_name="")
            )

        # Cannot find module 'some/module'
        mod_re = re.compile(r"Cannot find module '([^']+)'")
        for m in mod_re.finditer(output):
            symbols.append(
                MissingSymbol(kind="class", name=m.group(1), params="", class_name="")
            )

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
            result = subprocess.run(
                ["node", "--version"], capture_output=True, timeout=10
            )
            version_output = result.stdout.decode().strip()
            print(f"  Node.js: {version_output}")
            m = re.match(r"v(\d+)", version_output)
            if not m or int(m.group(1)) < 20:
                print(f"  ERROR: Node.js 20+ required, found {version_output}")
                return False
        except Exception as e:
            print(f"  ERROR: Could not determine Node.js version: {e}")
            return False

        # Also check that npm is available (VS Code rejects yarn)
        try:
            result = subprocess.run(
                ["npm", "--version"], capture_output=True, timeout=10
            )
            npm_version = result.stdout.decode().strip()
            print(f"  npm: {npm_version}")
        except Exception as e:
            print(f"  WARNING: npm not found: {e}")

        return True

    def detect_runtime_version(
        self,
        clone_dir: str,
        config: RepoConfig,
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
        # Also check .nvmrc
        nvmrc_file = os.path.join(clone_dir, ".nvmrc")
        if os.path.isfile(nvmrc_file):
            try:
                with open(nvmrc_file) as f:
                    version = f.read().strip()
                if version:
                    return version
            except OSError:
                pass
        return None

    def resolve_base_image(
        self,
        config: RepoConfig,
        runtime_version: Optional[str],
    ) -> str:
        if runtime_version:
            ver = runtime_version.lstrip("v")
            return f"node:{ver}-bookworm"
        return config.base_image

    def _dockerfile_install_deps_lines(
        self,
        config: RepoConfig,
        runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Install native build dependencies for VS Code",
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "    libx11-dev libxkbfile-dev libsecret-1-dev \\",
            "    pkg-config make g++ \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
            "# Install junitparser for test result parsing inside the container",
            "RUN pip3 install --no-cache-dir --break-system-packages junitparser",
            "",
        ]

    def _dockerfile_base_env_lines(
        self,
        config: RepoConfig,
        runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Set Node.js memory limit for build",
            'ENV NODE_OPTIONS="--max-old-space-size=8192"',
            "",
        ]

    def _dockerfile_post_checkout_lines(
        self,
        config: RepoConfig,
        runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# VS Code requires npm (yarn is explicitly rejected)",
            "# Skip preinstall version gates, then run postinstall for sub-packages",
            'ENV VSCODE_SKIP_NODE_VERSION_CHECK="1"',
            "RUN npm install --ignore-scripts 2>&1 | tail -40",
            "RUN node build/npm/postinstall.ts 2>&1 | tail -40",
            "",
        ]

    def _dockerfile_final_lines(
        self,
        config: RepoConfig,
        runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Verify TypeScript compiler is available",
            "RUN npx tsc --version || true",
            "",
        ]

    def generate_test_parser_script(self) -> Optional[str]:
        """Return a Mocha/JUnit XML parser script."""
        return '''#!/usr/bin/env python3
"""Parser for Mocha JUnit XML test results (VS Code)."""
import argparse
import json
import os
import sys
from pathlib import Path
from junitparser import JUnitXml, TestCase, TestSuite


def parse_junit_dir(report_dir: str):
    passed, failed = [], []
    for xml_path in sorted(Path(report_dir).rglob("*.xml")):
        try:
            xml = JUnitXml.fromfile(str(xml_path))
        except Exception:
            continue
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
                    is_fail = any("fail" in type(r).__name__.lower() or "error" in type(r).__name__.lower() for r in results)
                    if is_skip:
                        continue
                    elif is_fail:
                        failed.append(test_id)
                    else:
                        passed.append(test_id)
    return passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    if not os.path.isdir(args.report_dir):
        print(f"Report dir not found: {args.report_dir}", file=sys.stderr)
        json.dump({"passed": [], "failed": []}, open(args.output, "w"))
        return

    passed, failed = parse_junit_dir(args.report_dir)
    print(f"Parsed {len(passed)} passed, {len(failed)} failed")
    with open(args.output, "w") as f:
        json.dump({"passed": passed, "failed": failed}, f, indent=2)


if __name__ == "__main__":
    main()
'''

    def git_clean_excludes(self) -> List[str]:
        return ["node_modules/", ".build/", "out/"]

    def bootstrap_repo(
        self, clone_dir: str, config: RepoConfig, timeout: int = 1800
    ) -> Tuple[bool, str]:
        """Run ``npm install`` to install dependencies after checkout.

        VS Code's ``preinstall.ts`` enforces strict Node.js and npm version
        gates that don't match the host environment.  We bypass the
        preinstall entirely with ``--ignore-scripts``, then run the
        postinstall manually (it installs sub-package dependencies in
        ~60 extension/build directories).

        The postinstall step may fail due to native module issues (e.g.
        ``@parcel/watcher`` lacking prebuilt binaries for the host Node
        version).  We treat postinstall failures as non-fatal — the
        subsequent compile step will catch any real missing-dependency
        problems.
        """
        env = {
            **os.environ,
            "NODE_OPTIONS": "--max-old-space-size=8192",
            "VSCODE_SKIP_NODE_VERSION_CHECK": "1",
        }
        try:
            # Step 1: Install root dependencies, skipping pre/postinstall
            # to bypass the Node.js and npm version gates.
            result = subprocess.run(
                "npm install --ignore-scripts 2>&1",
                shell=True,
                cwd=clone_dir,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
            output = result.stdout.decode(errors="replace")
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")
                return False, (
                    f"npm install --ignore-scripts failed (exit {result.returncode}):\n"
                    f"{output}\n{stderr}"
                )

            # Step 2: Run postinstall manually to install sub-package deps.
            # This may fail on native modules (e.g. @parcel/watcher) that
            # lack prebuilds for the host Node version.  That's OK — those
            # modules are optional file-watching optimisations, not needed
            # for compiling or running unit tests.
            result = subprocess.run(
                "node build/npm/postinstall.ts 2>&1",
                shell=True,
                cwd=clone_dir,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
            post_output = result.stdout.decode(errors="replace")
            output += "\n" + post_output
            if result.returncode != 0:
                print(f"  [vscode] postinstall exited with code {result.returncode} "
                      f"(non-fatal, will retry critical dirs)")
                # Fallback: install just the critical subdirectories that
                # the compile/test steps actually need.  Skip native module
                # postinstall scripts to avoid @parcel/watcher-type failures.
                for subdir in ("build", "test/unit"):
                    subdir_path = os.path.join(clone_dir, subdir)
                    if os.path.isfile(os.path.join(subdir_path, "package.json")):
                        subprocess.run(
                            "npm install --ignore-scripts 2>&1",
                            shell=True,
                            cwd=subdir_path,
                            capture_output=True,
                            timeout=300,
                            env=env,
                        )

            return True, output
        except subprocess.TimeoutExpired:
            return False, f"npm install timed out after {timeout}s"

    def generate_run_script(
        self,
        instance_id: str,
        commands: List[str],
        config: RepoConfig,
    ) -> str:
        commands_block = ""
        for i, cmd in enumerate(commands):
            commands_block += f"""
echo "=== Running test command {i + 1}/{len(commands)} ==="
{cmd}
CMD_EXIT=$?
if [ $CMD_EXIT -ne 0 ]; then
    echo "Test command {i + 1} failed with exit code $CMD_EXIT"
    OVERALL_EXIT=1
fi
"""

        return f"""#!/bin/bash
set -uo pipefail

# Run script for {instance_id}
# Auto-generated by the benchmark pipeline

cd /app
export NODE_OPTIONS="--max-old-space-size=8192"
export BUILD_ARTIFACTSTAGINGDIRECTORY="/app"
export VSCODE_SKIP_NODE_VERSION_CHECK=1
OVERALL_EXIT=0

# VS Code tests run from compiled out/ — must recompile after any .ts change
echo "=== Compiling TypeScript ==="
npm run compile
if [ $? -ne 0 ]; then
    echo "ERROR: TypeScript compilation failed"
    exit 1
fi

if [ $# -gt 0 ]; then
    TEST_FILES="$@"
    echo "Running with custom test files: $TEST_FILES"
    for tf in $(echo "$TEST_FILES" | tr ',' ' '); do
        ./scripts/test.sh --run "$tf" --tfs unittest
        CMD_EXIT=$?
        if [ $CMD_EXIT -ne 0 ]; then
            OVERALL_EXIT=1
        fi
    done
else
    echo "Running pre-configured test commands..."
{commands_block}
fi

echo "=== Test execution complete ==="
exit $OVERALL_EXIT
"""

    def generate_test_script(self, config: RepoConfig) -> Optional[str]:
        """Return a VS Code-specific ``test.sh`` for the Harbor container."""
        no_root_user = config.no_root_user

        return f"""#!/bin/bash
set -euo pipefail

# ── Harbor test.sh for VS Code (Mocha) ───────────────────────────────────────
#
# This script is called by the harbor verifier. Steps:
#   1. Apply the test_patch (new / modified tests)
#   2. Run the tests via run_script.sh
#   3. Parse test results → output.json
#   4. Evaluate pass / fail against fail_to_pass + pass_to_pass lists
#   5. Write reward (0 or 1) to /logs/verifier/reward.txt

CONFIG_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="/app"
LOG_DIR="/logs/verifier"
mkdir -p "$LOG_DIR"

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
"

# ── 2. Run the tests ─────────────────────────────────────────────────────────
echo "Running tests..."
chmod +x "$CONFIG_DIR/run_script.sh"
"$CONFIG_DIR/run_script.sh" 2>&1 | tee "$LOG_DIR/test_output.txt"
TEST_EXIT=${{PIPESTATUS[0]}}

# ── 3. Parse results ─────────────────────────────────────────────────────────
python3 "$CONFIG_DIR/parser.py" \\
    --report-dir "$REPO_DIR/test-results" \\
    --output "$LOG_DIR/output.json" || true

# ── 4. Evaluate ──────────────────────────────────────────────────────────────
python3 -c "
import json, sys
config = json.load(open('$CONFIG_DIR/config.json'))
try:
    results = json.load(open('$LOG_DIR/output.json'))
except Exception:
    results = {{'passed': [], 'failed': []}}

f2p = set(config.get('fail_to_pass', []))
p2p = set(config.get('pass_to_pass', []))
passed_set = set(results.get('passed', []))
failed_set = set(results.get('failed', []))

f2p_ok = f2p.issubset(passed_set) if f2p else True
p2p_ok = p2p.issubset(passed_set) if p2p else True

reward = 1 if (f2p_ok and p2p_ok) else 0
print(f'fail_to_pass resolved: {{f2p_ok}} ({{len(f2p & passed_set)}}/{{len(f2p)}})')
print(f'pass_to_pass intact:   {{p2p_ok}} ({{len(p2p & passed_set)}}/{{len(p2p)}})')
print(f'Reward: {{reward}}')

with open('$LOG_DIR/reward.txt', 'w') as f:
    f.write(str(reward))
"

echo "=== Evaluation complete ==="
"""
