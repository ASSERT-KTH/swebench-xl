"""Java + Gradle adapter."""

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
        if config and config.extra.get("gradle_flags"):
            return config.extra["gradle_flags"]
        return DEFAULT_GRADLE_FLAGS

    def _get_gradle_env(self, config: RepoConfig) -> Dict[str, str]:
        if config and config.extra.get("gradle_env_overrides"):
            return config.extra["gradle_env_overrides"]
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

    # ── Command runner hooks ─────────────────────────────────────────

    def _error_line_patterns(self) -> List[str]:
        return ["cannot find symbol"]

    def _build_env(self, config: RepoConfig) -> Dict[str, str]:
        return self._get_gradle_env(config)

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
        min_version = config.extra.get("min_jdk_version", 17) if config else 17
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
            config.extra.get("java_version_file", ".java-version") if config else ".java-version",
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

    # ── Dockerfile hooks ────────────────────────────────────────────

    def resolve_base_image(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> str:
        if runtime_version:
            return f"eclipse-temurin:{runtime_version}-jdk-jammy"
        return config.base_image

    def _dockerfile_install_deps_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Install junitparser for test result parsing inside the container",
            "RUN pip3 install --no-cache-dir junitparser",
            "",
        ]

    def _dockerfile_base_env_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        return [
            "# Cap Gradle JVM heap for memory-constrained hosts",
            'ENV GRADLE_OPTS="-Xmx512m"',
            "",
        ]

    def _dockerfile_post_checkout_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        no_root_user = config.no_root_user
        repo_dir = config.repo_dir
        lines = [
            "# Cap Gradle JVM heap and parallelism for memory-constrained hosts",
            f'RUN echo "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m" >> {repo_dir}/gradle.properties',
            "",
            "# Gradlew wrapper: auto-drops to non-root user when invoked as root",
            f"RUN mv {repo_dir}/gradlew {repo_dir}/.gradlew-bin",
            f"RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' {repo_dir}/.gradlew-bin",
            f"RUN cat > {repo_dir}/gradlew << 'GRADLEW_WRAPPER_EOF'",
            "#!/bin/sh",
            'if [ "$(id -u)" = "0" ]; then',
            f'    chown -R {no_root_user}:{no_root_user} {repo_dir} 2>/dev/null || true',
            f"    exec su -s /bin/bash -c 'exec {repo_dir}/.gradlew-bin \"$@\"' -- {no_root_user} _ \"$@\"",
            "fi",
            f'exec {repo_dir}/.gradlew-bin "$@"',
            "GRADLEW_WRAPPER_EOF",
            f"RUN chmod +x {repo_dir}/gradlew",
            "",
        ]
        return lines

    def _dockerfile_final_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        repo_dir = config.repo_dir
        return [
            "# Pre-warm Gradle distribution",
            f"RUN cd {repo_dir} && ./gradlew --version --no-daemon || true",
        ]

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

        repo_dir = config.repo_dir
        return f"""#!/bin/bash
set -uo pipefail

# Run script for {instance_id}
# Auto-generated by the benchmark pipeline
#
# NOTE: set -e is intentionally NOT used. All gradle commands must run so that
# JUnit XML is produced for every module, even if an earlier module fails.

cd {repo_dir}
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
