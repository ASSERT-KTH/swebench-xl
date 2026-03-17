"""
Java + Gradle adapter.

Implements ``LanguageAdapter`` for repositories that use Java source code
and the Gradle build system.  This is a direct extraction of the logic that
was previously spread across ``gradle_runner.py``, ``test_parser.py``,
``file_classifier.py``, and ``harbor_packager.py``.
"""

from __future__ import annotations

import os
import re
import subprocess
import stat
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from junitparser import JUnitXml, TestCase, TestSuite

from adapters.base import CompileError, LanguageAdapter, MissingSymbol

if TYPE_CHECKING:
    from repo_config import RepoConfig


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 600  # 10 minutes

# Default gradle flags (used when RepoConfig doesn't specify any)
DEFAULT_GRADLE_FLAGS = [
    "--no-daemon", "--stacktrace", "-x", "javadoc",
    "--no-configuration-cache", "--max-workers=2",
]

DEFAULT_GRADLE_ENV = {"GRADLE_OPTS": "-Xmx2g"}

# Default test-config filenames
_DEFAULT_TEST_CONFIG_FILES: Set[str] = {"muted-tests.yml", "muted-tests.yaml"}

# Filename patterns for test helper/utility files
_TEST_UTIL_PATTERNS = [
    re.compile(r".*TestUtils?\.java$"),
    re.compile(r".*TestHelper\.java$"),
    re.compile(r".*TestFixture\.java$"),
    re.compile(r".*Mock\w+\.java$"),
    re.compile(r".*Fake\w+\.java$"),
    re.compile(r".*TestCase\.java$"),
    re.compile(r".*Abstract\w*Test\w*\.java$"),
]


# ── Helpers (private) ─────────────────────────────────────────────────────────

def _in_path(segment: str, filename: str) -> bool:
    """Check if a path segment appears in the filename."""
    return segment in filename or filename.startswith(segment.lstrip("/"))


def _looks_like_test_util(filename: str) -> bool:
    """Heuristic: does the filename look like a test utility class?"""
    basename = filename.rsplit("/", 1)[-1]
    return any(pat.match(basename) for pat in _TEST_UTIL_PATTERNS)


# ── Adapter ───────────────────────────────────────────────────────────────────

class JavaGradleAdapter(LanguageAdapter):
    """Adapter for Java projects built with Gradle."""

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def language_name(self) -> str:
        return "Java"

    @property
    def build_tool_name(self) -> str:
        return "Gradle"

    @property
    def source_file_extensions(self) -> Tuple[str, ...]:
        return (".java",)

    # ── File classification ───────────────────────────────────────────

    def is_test_file(self, filename: str, config: RepoConfig) -> bool:
        if _in_path("/src/test/java/", filename):
            return True
        if _in_path("/src/test/resources/", filename):
            return True
        extra_segments = config.extra_test_path_segments if config else []
        for segment in (extra_segments or []):
            if segment in filename:
                return True
        # Basename heuristic, but NOT for files in production source trees.
        if _in_path("/src/main/", filename):
            return False
        basename = filename.rsplit("/", 1)[-1]
        if basename.endswith(("Test.java", "Tests.java", "IT.java", "TestCase.java")):
            return True
        return False

    def is_source_file(self, filename: str, config: RepoConfig) -> bool:
        return not self.is_test_file(filename, config) and not self.is_test_support_file(filename, config)

    def is_test_support_file(self, filename: str, config: RepoConfig) -> bool:
        basename = filename.rsplit("/", 1)[-1]
        cfg_files = config.test_config_files if config else _DEFAULT_TEST_CONFIG_FILES
        if basename in cfg_files:
            return True
        return False

    def classify_files(
        self,
        patches: List[Dict[str, Any]],
        config: RepoConfig,
    ) -> Tuple[List[str], List[str], List[str]]:
        test_files: list[str] = []
        source_files: list[str] = []
        test_support_files: list[str] = []

        for patch in patches:
            filename = patch["filename"]
            status = patch.get("status", "modified")
            if status == "removed":
                continue

            if self.is_test_support_file(filename, config):
                test_support_files.append(filename)
            elif self.is_test_file(filename, config):
                test_files.append(filename)
            else:
                source_files.append(filename)

        # Second pass: reclassify source files whose names match test-util patterns
        if test_files and source_files:
            reclassified = [f for f in source_files if _looks_like_test_util(f)]
            for filename in reclassified:
                source_files.remove(filename)
                test_support_files.append(filename)

        return test_files, source_files, test_support_files

    # ── PR pre-filtering ──────────────────────────────────────────────

    def has_test_and_source_files(self, patches: List[Dict[str, str]]) -> bool:
        has_test = False
        has_source = False
        for p in patches:
            fn = p["filename"]
            if not fn.endswith(".java"):
                continue
            if "/src/test/" in fn or "src/test/" in fn or fn.endswith(("Test.java", "Tests.java", "IT.java")):
                has_test = True
            if "/src/main/" in fn or "src/main/" in fn:
                has_source = True
            if has_test and has_source:
                return True
        return has_test and has_source

    def has_test_files_in_pr(self, pr: Dict[str, Any]) -> bool:
        for p in pr.get("patches", []):
            fn = p.get("filename", "")
            if not fn.endswith(".java"):
                continue
            if "src/test/" in fn or fn.endswith(("Test.java", "Tests.java", "IT.java")):
                return True
        return False

    # ── Test identity extraction ──────────────────────────────────────

    def extract_test_fqn(self, filepath: str) -> Optional[str]:
        """
        Extract fully-qualified class name from a test file path.

        Example: ``'x-pack/.../src/test/java/org/elasticsearch/xpack/FooTests.java'``
                 → ``'org.elasticsearch.xpack.FooTests'``
        """
        parts = filepath.split("/")
        try:
            java_idx = parts.index("java")
            fqn = ".".join(parts[java_idx + 1:])
            return fqn.replace(".java", "")
        except ValueError:
            return None

    def extract_module(self, filepath: str) -> Optional[str]:
        """
        Extract the Gradle module path from a file path.

        Examples:
            ``'x-pack/plugin/esql/src/test/java/...'`` → ``':x-pack:plugin:esql'``
            ``'server/src/test/java/...'``              → ``':server'``
        """
        parts = filepath.split("/")
        try:
            src_idx = parts.index("src")
            module_path = "/".join(parts[:src_idx])
            return ":" + module_path.replace("/", ":")
        except ValueError:
            return None

    # ── Build & test commands ─────────────────────────────────────────

    def _get_gradle_flags(self, config: RepoConfig) -> List[str]:
        if config and config.gradle_flags:
            return config.gradle_flags
        return DEFAULT_GRADLE_FLAGS

    def _get_gradle_env(self, config: RepoConfig) -> Dict[str, str]:
        if config and config.gradle_env_overrides:
            return config.gradle_env_overrides
        return DEFAULT_GRADLE_ENV

    def build_test_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        module_tests: Dict[str, List[str]] = {}
        for filepath in test_files:
            if not filepath.endswith(".java"):
                continue
            module = self.extract_module(filepath)
            fqn = self.extract_test_fqn(filepath)
            if not module or not fqn:
                continue
            module_tests.setdefault(module, []).append(fqn)

        flags = " ".join(self._get_gradle_flags(config))
        commands = []
        for module, fqns in module_tests.items():
            test_filters = " ".join(f"--tests {fqn}" for fqn in fqns)
            cmd = f"./gradlew {module}:test {test_filters} {flags}"
            commands.append(cmd)
        return commands

    def build_compile_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        modules = set()
        for filepath in test_files:
            if not filepath.endswith(".java"):
                continue
            module = self.extract_module(filepath)
            if module:
                modules.add(module)

        flags = " ".join(self._get_gradle_flags(config))
        return [f"./gradlew {module}:compileTestJava {flags}" for module in sorted(modules)]

    def run_commands(
        self,
        commands: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str, int]:
        all_output: list[str] = []
        env = os.environ.copy()
        for k, v in self._get_gradle_env(config).items():
            env.setdefault(k, v)

        for cmd in commands:
            print(f"    Running: {cmd[:120]}...")
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    timeout=timeout,
                    env=env,
                )
                stdout = result.stdout.decode(errors="replace")
                stderr = result.stderr.decode(errors="replace")
                combined = (stdout + "\n" + stderr).strip()
                lines = combined.split("\n")

                # Preserve "cannot find symbol" error blocks
                error_indices: set[int] = set()
                for idx, ln in enumerate(lines):
                    if "cannot find symbol" in ln.lower():
                        for ei in range(max(0, idx - 1), min(len(lines), idx + 5)):
                            error_indices.add(ei)
                tail_start = max(0, len(lines) - 80)
                merged: list[str] = []
                for idx in sorted(error_indices):
                    if idx < tail_start:
                        merged.append(lines[idx])
                if merged and tail_start > 0:
                    merged.append("...")
                merged.extend(lines[tail_start:])
                all_output.append("\n".join(merged))

                if result.returncode != 0:
                    print(f"    FAILED (exit code {result.returncode})")
                    return False, "\n---\n".join(all_output), result.returncode
                print(f"    PASSED")

            except subprocess.TimeoutExpired:
                all_output.append(f"TIMEOUT after {timeout}s")
                print(f"    TIMEOUT")
                return False, "\n---\n".join(all_output), -1

        return True, "\n---\n".join(all_output), 0

    # ── Test result parsing ───────────────────────────────────────────

    def find_test_reports(
        self, commands: List[str], repo_dir: str,
    ) -> List[str]:
        xml_files: list[str] = []
        for cmd in commands:
            match = re.search(r"\s(:\S+):test\s", cmd)
            if not match:
                continue
            gradle_module = match.group(1)
            module_dir = gradle_module.lstrip(":").replace(":", "/")
            report_dir = os.path.join(repo_dir, module_dir, "build", "test-results", "test")
            if os.path.isdir(report_dir):
                for fname in os.listdir(report_dir):
                    if fname.startswith("TEST-") and fname.endswith(".xml"):
                        xml_files.append(os.path.join(report_dir, fname))
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
                    if not classname or not name:
                        continue

                    test_id = f"{classname}::{name}"

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
        methods: list[str] = []
        lines = source_code.splitlines()
        in_test_annotation = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("@Test"):
                in_test_annotation = True
                continue
            if in_test_annotation:
                m = re.match(r"(?:public|protected|private)?\s*void\s+(\w+)\s*\(", stripped)
                if m:
                    methods.append(m.group(1))
                in_test_annotation = False
        return methods

    # ── Compile error analysis ────────────────────────────────────────

    def parse_compile_errors(self, output: str) -> List[CompileError]:
        errors: list[CompileError] = []
        lines = output.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if "cannot find symbol" in line.lower():
                error = CompileError(raw=line.strip())
                for j in range(i + 1, min(i + 5, len(lines))):
                    stripped = lines[j].strip()
                    if stripped.startswith("symbol:") and not error.symbol:
                        error.symbol = stripped.replace("symbol:", "").strip()
                    elif stripped.startswith("location:") and not error.location:
                        error.location = stripped.replace("location:", "").strip()
                    if error.symbol and error.location:
                        break
                errors.append(error)
            i += 1
        return errors

    def extract_missing_symbols(self, output: str) -> List[MissingSymbol]:
        symbols: list[MissingSymbol] = []
        errors = self.parse_compile_errors(output)
        for err in errors:
            symbol = err.symbol
            location = err.location

            loc_class = ""
            loc_match = re.search(r"class\s+([\w.]+)", location)
            if loc_match:
                loc_class = loc_match.group(1)

            # method someMethod(ParamType, OtherType)
            m = re.match(r"method\s+(\w+)\s*\(([^)]*)\)", symbol)
            if m:
                symbols.append(MissingSymbol(kind="method", name=m.group(1), params=m.group(2), class_name=loc_class))
                continue

            # constructor ClassName(ParamType)
            m = re.match(r"constructor\s+(\w+)\s*\(([^)]*)\)", symbol)
            if m:
                symbols.append(MissingSymbol(kind="constructor", name=m.group(1), params=m.group(2), class_name=loc_class))
                continue

            # class ClassName
            m = re.match(r"class\s+([\w.]+)", symbol)
            if m:
                symbols.append(MissingSymbol(kind="class", name=m.group(1), params="", class_name=loc_class))
                continue

            # variable SOME_NAME
            m = re.match(r"variable\s+(\w+)", symbol)
            if m:
                symbols.append(MissingSymbol(kind="variable", name=m.group(1), params="", class_name=loc_class))
                continue

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
        return os.path.isfile(os.path.join(clone_dir, "gradlew"))

    def check_prerequisites(self, config: RepoConfig) -> bool:
        min_version = config.min_jdk_version if config else 17
        try:
            result = subprocess.run(["java", "-version"], capture_output=True, timeout=10)
            version_output = result.stderr.decode() + result.stdout.decode()
            print(f"  Java: {version_output.strip().split(chr(10))[0]}")
            for token in version_output.split():
                token = token.strip('"')
                if token[0:1].isdigit():
                    major = int(token.split(".")[0])
                    if major >= min_version:
                        return True
                    print(f"  ERROR: JDK {min_version}+ required, found JDK {major}")
                    return False
        except Exception as e:
            print(f"  ERROR: Could not determine Java version: {e}")
        return False

    def detect_runtime_version(
        self, clone_dir: str, config: RepoConfig,
    ) -> Optional[str]:
        java_version_file = os.path.join(
            clone_dir,
            config.java_version_file if config else ".java-version",
        )
        if os.path.isfile(java_version_file):
            try:
                with open(java_version_file) as f:
                    version = f.read().strip()
                if version:
                    return version
            except OSError:
                pass
        return None

    def generate_dockerfile_lines(
        self,
        config: RepoConfig,
        repo_url: str,
        base_commit: str,
        instance_id: str,
        *,
        runtime_version: Optional[str] = None,
    ) -> List[str]:
        base_image = config.base_image
        if runtime_version:
            base_image = f"eclipse-temurin:{runtime_version}-jdk-jammy"

        packages = config.system_packages
        no_root_user = config.no_root_user

        lines = [
            f"# Auto-generated Dockerfile for {instance_id}",
            f"FROM {base_image}",
            "",
            "ENV DEBIAN_FRONTEND=noninteractive",
            "",
            "# System dependencies",
            f"RUN apt-get update && apt-get install -y --no-install-recommends \\",
            f"    {packages} \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
            "# Install junitparser for test result parsing inside the container",
            "RUN pip3 install --no-cache-dir junitparser",
            "",
            "# Clone repository",
            f"RUN mkdir /app && \\",
            f"    git clone -o origin {repo_url} /app",
            "",
            "WORKDIR /app",
            'SHELL ["/bin/bash", "-c"]',
            "",
            f"# Reset to base commit (before the fix)",
            f"RUN git checkout {base_commit} && \\",
            f"    git reset --hard {base_commit} && \\",
            f"    git clean -fdx",
            "",
            "# === Git History Cleanup ===",
            "# Prevents agents from seeing future commits/tags.",
            f"RUN git remote remove origin && \\",
            f"    git branch -a | grep -v '\\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \\",
            f"    BASE_TIMESTAMP=$(git show -s --format=%ci {base_commit}) && \\",
            f"    git tag -l | while read tag; do \\",
            f"        TAG_COMMIT=$(git rev-list -n 1 \"$tag\" 2>/dev/null) || continue; \\",
            f"        TAG_TIME=$(git show -s --format=%ci \"$TAG_COMMIT\" 2>/dev/null) || continue; \\",
            f"        if [[ \"$TAG_TIME\" > \"$BASE_TIMESTAMP\" ]]; then \\",
            f"            git tag -d \"$tag\" > /dev/null 2>&1; \\",
            f"        fi; \\",
            f"    done && \\",
            f"    git reflog expire --expire=now --all && \\",
            f"    git gc --prune=now",
            "",
            "# Verify no future commits accessible",
            f"RUN FUTURE_COMMITS=$(git log --oneline --all "
            f"--after=\"$(git show -s --format=%ci {base_commit})\" "
            f"--not {base_commit} 2>/dev/null | wc -l | tr -d ' ') && \\",
            f"    if [ \"$FUTURE_COMMITS\" -gt 0 ]; then \\",
            f"        echo \"ERROR: $FUTURE_COMMITS future commits still accessible!\" && exit 1; \\",
            f"    fi",
            "",
            f"# Verify HEAD at correct commit",
            f"RUN CURRENT=$(git rev-parse HEAD) && \\",
            f"    if [ \"$CURRENT\" != \"{base_commit}\" ]; then \\",
            f"        echo \"ERROR: HEAD is $CURRENT, expected {base_commit}\" && exit 1; \\",
            f"    fi",
            "",
            "# ── Harbor additions ──────────────────────────────────────",
            "ENTRYPOINT []",
            "WORKDIR /app",
            "ENV PYTHONPATH=/app/lib:/app",
            "# Cap Gradle JVM heap and parallelism for memory-constrained hosts",
            'ENV GRADLE_OPTS="-Xmx512m"',
            'RUN echo "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m" >> /app/gradle.properties',
            "RUN mkdir -p /logs",
            "RUN mkdir -p /installed-agent",
            "",
        ]

        # Create non-root users
        lines.append(f"RUN userdel -r ubuntu 2>/dev/null || true")
        lines.append(f"RUN useradd -m -u 1000 {no_root_user} 2>/dev/null || true")

        # Gradlew wrapper: auto-drops to non-root user when invoked as root
        lines.extend([
            "",
            "# Gradlew wrapper: auto-drops to non-root user when invoked as root",
            "RUN useradd -m -u 1001 agent 2>/dev/null || true",
            "RUN chown -R agent:agent /app",
            "",
            "RUN mv /app/gradlew /app/.gradlew-bin",
            "RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' /app/.gradlew-bin",
            "RUN cat > /app/gradlew << 'GRADLEW_WRAPPER_EOF'",
            "#!/bin/sh",
            'if [ "$(id -u)" = "0" ]; then',
            '    chown -R agent:agent /app 2>/dev/null || true',
            '    exec su -s /bin/bash -c \'exec /app/.gradlew-bin "$@"\' -- agent _ "$@"',
            "fi",
            'exec /app/.gradlew-bin "$@"',
            "GRADLEW_WRAPPER_EOF",
            "RUN chmod +x /app/gradlew",
            "RUN cp /app/gradlew /app/gradlew.real",
            "RUN cp /app/gradlew /app/.gradlew-real",
            "",
        ])

        lines.extend([
            "# Agent config",
            "COPY mini-swe-agent-config.yaml /root/mini-swe-agent-config.yaml",
            "ENV MSWEA_MINI_CONFIG_PATH=/root/mini-swe-agent-config.yaml",
            "",
            "# Pre-warm Gradle distribution",
            "RUN cd /app && ./gradlew --version --no-daemon || true",
        ])

        return lines

    def generate_run_script(
        self,
        instance_id: str,
        commands: List[str],
        config: RepoConfig,
    ) -> str:
        flags = self._get_gradle_flags(config)
        flags_str = " ".join(flags) if flags else "--no-daemon --stacktrace --max-workers=2"

        commands_block = ""
        for i, cmd in enumerate(commands):
            if "--no-configuration-cache" not in cmd:
                cmd = cmd + " --no-configuration-cache"
            if "--max-workers" not in cmd:
                cmd = cmd + " --max-workers=2"
            commands_block += f"""
echo "=== Running gradle command {i + 1}/{len(commands)} ==="
{cmd}
CMD_EXIT=$?
if [ $CMD_EXIT -ne 0 ]; then
    echo "Gradle command {i + 1} failed with exit code $CMD_EXIT"
    OVERALL_EXIT=1
fi
"""

        return f"""#!/bin/bash
set -uo pipefail

# Run script for {instance_id}
# Auto-generated by the benchmark pipeline
#
# NOTE: set -e is intentionally NOT used. All gradle commands must run so that
# JUnit XML is produced for every module, even if an earlier module fails.

cd /app
OVERALL_EXIT=0

if [ $# -gt 0 ]; then
    TEST_FILES="$@"
    echo "Running with custom test files: $TEST_FILES"
    for tf in $(echo "$TEST_FILES" | tr ',' ' '); do
        ./gradlew test --tests "$tf" {flags_str}
        CMD_EXIT=$?
        if [ $CMD_EXIT -ne 0 ]; then
            OVERALL_EXIT=1
        fi
    done
else
    echo "Running pre-configured gradle commands..."
{commands_block}
fi

echo "=== Test execution complete ==="
exit $OVERALL_EXIT
"""
