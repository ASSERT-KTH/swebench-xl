"""
Abstract base class for language/build-tool adapters.

Each adapter encapsulates all language-specific and build-tool-specific logic
the pipeline needs: file classification, build commands, test result parsing,
compile error analysis, and environment (Docker) generation.

To add support for a new language/build-tool combination:
  1. Subclass ``LanguageAdapter`` in a new file under ``adapters/``.
  2. Implement all abstract methods.
  3. Register the adapter in ``adapters/__init__.py`` with ``register_adapter()``.
  4. Set ``adapter_name`` in your ``RepoConfig`` to match the registered name.
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from repo_config import RepoConfig


@dataclass
class CompileError:
    """A single compile error extracted from build output."""
    raw: str = ""
    symbol: str = ""
    location: str = ""


@dataclass
class MissingSymbol:
    """A symbol (method, class, variable, constructor) that doesn't exist yet."""
    kind: str = ""       # "method", "class", "variable", "constructor"
    name: str = ""
    params: str = ""
    class_name: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "kind": self.kind,
            "name": self.name,
            "params": self.params,
            "class": self.class_name,
        }


class LanguageAdapter(ABC):
    """
    Abstract base for language/build-tool specific pipeline behavior.

    The benchmark pipeline calls these methods at every stage — PR filtering,
    instance verification, and Harbor task packaging. A concrete adapter
    (e.g. ``JavaGradleAdapter``) implements them for a specific ecosystem.
    """

    # ── Identity ──────────────────────────────────────────────────────

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Human-readable language name, e.g. ``'Java'``, ``'Python'``."""

    @property
    @abstractmethod
    def build_tool_name(self) -> str:
        """Human-readable build tool name, e.g. ``'Gradle'``, ``'pytest'``."""

    @property
    @abstractmethod
    def source_file_extensions(self) -> Tuple[str, ...]:
        """File extensions for this language, e.g. ``('.java',)``, ``('.py',)``."""

    # ── File classification ───────────────────────────────────────────

    @abstractmethod
    def is_test_file(self, filename: str, config: RepoConfig) -> bool:
        """Return True if *filename* is a test source file."""

    @abstractmethod
    def is_source_file(self, filename: str, config: RepoConfig) -> bool:
        """Return True if *filename* is a production source file (not test)."""

    @abstractmethod
    def is_test_support_file(self, filename: str, config: RepoConfig) -> bool:
        """Return True if *filename* is a test helper/utility/config file."""

    def classify_files(
        self,
        patches: List[Dict[str, Any]],
        config: RepoConfig,
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Split patch files into ``(test_files, source_files, test_support_files)``.

        Only includes files that exist in the merge commit (skips 'removed').
        The default implementation calls ``is_test_file``, ``is_source_file``,
        and ``is_test_support_file`` for each file. Override for custom logic.
        """
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

        return test_files, source_files, test_support_files

    # ── PR pre-filtering ──────────────────────────────────────────────

    @abstractmethod
    def has_test_and_source_files(self, patches: List[Dict[str, str]]) -> bool:
        """Quick check: does this PR touch both test and non-test source files?"""

    @abstractmethod
    def has_test_files_in_pr(self, pr: Dict[str, Any]) -> bool:
        """Does this PR contain any test files for this language?"""

    # ── Test identity extraction ──────────────────────────────────────

    @abstractmethod
    def extract_test_fqn(self, filepath: str) -> Optional[str]:
        """
        Extract a fully-qualified test identifier from a file path.

        For Java: ``'org.elasticsearch.FooTests'``
        For Python: ``'tests.test_foo'``
        """

    @abstractmethod
    def extract_module(self, filepath: str) -> Optional[str]:
        """
        Extract the build module/package from a file path.

        For Gradle: ``':server'`` or ``':x-pack:plugin:esql'``
        For Python: the package directory
        """

    # ── Build & test commands ─────────────────────────────────────────

    @abstractmethod
    def build_test_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        """Build commands to run the given test files."""

    @abstractmethod
    def build_compile_commands(
        self, test_files: List[str], config: RepoConfig,
    ) -> List[str]:
        """Build commands to compile tests without running them."""

    def compile_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """Compile test files without running them. Returns ``(ok, output)``."""
        commands = self.build_compile_commands(test_files, config)
        if not commands:
            return False, "No compile commands could be built"
        passed, output, _ = self.run_commands(commands, cwd, timeout, config)
        return passed, output

    def run_tests(
        self,
        test_files: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str]:
        """Run tests and return ``(passed, output)``."""
        commands = self.build_test_commands(test_files, config)
        if not commands:
            return False, "No test commands could be built"
        passed, output, _ = self.run_commands(commands, cwd, timeout, config)
        return passed, output

    # ── Test result parsing ───────────────────────────────────────────

    @abstractmethod
    def find_test_reports(
        self, commands: List[str], repo_dir: str,
    ) -> List[str]:
        """Locate test report files (e.g. JUnit XML, pytest JSON)."""

    @abstractmethod
    def parse_test_results(
        self, report_files: List[str],
    ) -> Tuple[List[str], List[str]]:
        """
        Parse test reports and return ``(failed_tests, passed_tests)``.

        Each entry is a unique test identifier (e.g. ``'classname::method'``).
        """

    @abstractmethod
    def extract_test_methods_from_source(self, source_code: str) -> List[str]:
        """
        Extract test method names from source code (not compiled output).

        Used for feature-addition detection when tests don't compile.
        For Java: parse ``@Test`` annotations.
        For Python: find ``def test_*`` functions.
        """

    # ── Compile error analysis ────────────────────────────────────────

    @abstractmethod
    def parse_compile_errors(self, output: str) -> List[CompileError]:
        """Parse compile errors from build output."""

    @abstractmethod
    def extract_missing_symbols(self, output: str) -> List[MissingSymbol]:
        """
        Extract missing symbols from compile errors.

        Used to detect feature additions (tests reference symbols that
        don't exist yet at the base commit).
        """

    # ── Environment / Docker ──────────────────────────────────────────

    @abstractmethod
    def check_build_tool_exists(self, clone_dir: str, config: RepoConfig) -> bool:
        """Check that the build tool exists in the repo (e.g. ``./gradlew``)."""

    @abstractmethod
    def check_prerequisites(self, config: RepoConfig) -> bool:
        """
        Verify that system prerequisites are met (e.g. JDK version).

        Returns True if OK, False otherwise.
        """

    @abstractmethod
    def detect_runtime_version(
        self, clone_dir: str, config: RepoConfig,
    ) -> Optional[str]:
        """
        Detect the required runtime version from the repo checkout.

        For Java: read ``.java-version`` file.
        For Python: read ``.python-version``.
        """

    # ── Environment / Docker ──────────────────────────────────────────
    #
    # ``generate_dockerfile_lines()`` is a concrete method that builds the
    # full Dockerfile from a shared skeleton.  Adapters customise behavior
    # by overriding three small hooks:
    #
    #   _dockerfile_install_deps_lines  – install language tooling / libs
    #   _dockerfile_post_checkout_lines – wrapper scripts, dep install, etc.
    #   _dockerfile_final_lines         – pre-warm caches, verify tooling
    #
    # This avoids duplicating the ~60 lines of git-clone / history-cleanup /
    # Harbor boilerplate in every adapter.

    @abstractmethod
    def resolve_base_image(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> str:
        """Return the Docker base image tag for this runtime version."""

    def _dockerfile_install_deps_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        """Extra RUN lines after system packages (e.g. pip install, yarn)."""
        return []

    def _dockerfile_post_checkout_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        """Extra lines after git checkout/reset (e.g. yarn install, gradlew wrapper)."""
        return []

    def _dockerfile_final_lines(
        self, config: RepoConfig, runtime_version: Optional[str],
    ) -> List[str]:
        """Extra lines at the very end (e.g. pre-warm Gradle, verify node)."""
        return []

    def generate_dockerfile_lines(
        self,
        config: RepoConfig,
        repo_url: str,
        base_commit: str,
        instance_id: str,
        *,
        runtime_version: Optional[str] = None,
    ) -> List[str]:
        """
        Generate a complete Dockerfile for the build environment.

        Shared skeleton handles: base image, system packages, git clone,
        checkout, history cleanup, verification, and Harbor additions.
        Adapter-specific parts are injected via the three hooks above.
        """
        base_image = self.resolve_base_image(config, runtime_version)
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
        ]

        # ── Adapter: language-specific dependency installation ────────
        lines.extend(self._dockerfile_install_deps_lines(config, runtime_version))

        lines.extend([
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
        ])

        # ── Adapter: post-checkout lines (deps, wrapper scripts) ─────
        lines.extend(self._dockerfile_post_checkout_lines(config, runtime_version))

        # ── Git-history cleanup (shared) ─────────────────────────────
        lines.extend([
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
        ])

        # ── Extra Dockerfile lines from config ───────────────────────
        if config.dockerfile_extra_lines:
            lines.extend(config.dockerfile_extra_lines)
            lines.append("")

        # ── Harbor additions (shared) ────────────────────────────────
        lines.extend([
            "# ── Harbor additions ──────────────────────────────────────",
            "ENTRYPOINT []",
            "WORKDIR /app",
            "ENV PYTHONPATH=/app/lib:/app",
            "RUN mkdir -p /logs",
            "",
            f"RUN userdel -r ubuntu 2>/dev/null || true",
            f"RUN useradd -m -u 1000 {no_root_user} 2>/dev/null || true",
            f"RUN chown -R {no_root_user}:{no_root_user} /app",
            "",
        ])

        # ── Adapter: final lines ─────────────────────────────────────
        lines.extend(self._dockerfile_final_lines(config, runtime_version))

        return lines

    @abstractmethod
    def generate_run_script(
        self,
        instance_id: str,
        commands: List[str],
        config: RepoConfig,
    ) -> str:
        """Generate the ``run_script.sh`` content for running tests."""

    def generate_test_parser_script(self) -> Optional[str]:
        """
        Return the content of a ``parser.py`` script for parsing test results
        inside the container. Return None to use the default template.
        """
        return None

    def generate_test_script(self, config: RepoConfig) -> Optional[str]:
        """
        Return the content of ``test.sh`` for the Harbor container.

        Return None to use the default template from ``harbor_templates/test.sh``.
        Override this when the default Gradle-centric test.sh doesn't apply
        (e.g. for Node.js/Jest projects).
        """
        return None

    def git_clean_excludes(self) -> List[str]:
        """
        Return paths to exclude from ``git clean -fdx`` when resetting between PRs.

        For example, Node.js projects should exclude ``node_modules`` and
        yarn caches so that ``yarn install`` is fast on subsequent resets.
        The default returns an empty list (no exclusions).
        """
        return []

    def bootstrap_repo(self, clone_dir: str, config: RepoConfig, timeout: int = 1800) -> Tuple[bool, str]:
        """
        Run one-time or per-reset setup after ``git checkout`` (install deps, etc.).

        Called by ``verify_instances.py`` after resetting to a base commit.
        The default is a no-op that returns ``(True, "")``.
        Override for ecosystems that need explicit dependency installation
        (e.g. ``yarn install`` for Node.js).
        """
        return True, ""

    # ── Shared command runner ─────────────────────────────────────────

    def _error_line_patterns(self) -> List[str]:
        """
        Substrings that mark error lines to preserve in truncated output.

        Override in subclasses. Default: empty (only keep the tail).
        """
        return []

    def _build_env(self, config: RepoConfig) -> Dict[str, str]:
        """
        Return environment variable overrides for subprocess calls.

        Override in subclasses to add language-specific env vars.
        The default returns an empty dict.
        """
        return {}

    def run_commands(
        self,
        commands: List[str],
        cwd: str,
        timeout: int,
        config: RepoConfig,
    ) -> Tuple[bool, str, int]:
        """
        Run build/test commands sequentially.

        Returns ``(all_passed, combined_output, last_exit_code)``.
        Error lines matching ``_error_line_patterns()`` are preserved even
        when the output is truncated to the last 100 lines.
        """
        all_output: list[str] = []
        env = os.environ.copy()
        for k, v in self._build_env(config).items():
            env.setdefault(k, v)

        error_patterns = self._error_line_patterns()
        tail_size = 100

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

                # Preserve error-pattern blocks even when truncating
                error_indices: set[int] = set()
                if error_patterns:
                    for idx, ln in enumerate(lines):
                        ln_lower = ln.lower()
                        if any(pat.lower() in ln_lower for pat in error_patterns):
                            for ei in range(max(0, idx - 1), min(len(lines), idx + 5)):
                                error_indices.add(ei)
                tail_start = max(0, len(lines) - tail_size)
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

    # ── Symbol hint formatting ────────────────────────────────────────

    def format_symbol_hints(self, missing_symbols: List[Dict[str, str]]) -> str:
        """Format missing symbol info for inclusion in the task instruction."""
        if not missing_symbols:
            return ""

        lines = ["## Hint: Symbols to Implement", ""]
        lines.append("The following symbols need to be created as part of this task:")
        lines.append("")
        for s in missing_symbols:
            cls = s.get("class", "Unknown")
            name = s.get("name", "unknown")
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
