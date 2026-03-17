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

    @abstractmethod
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
        """

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

    @abstractmethod
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
        Generate Dockerfile lines for the build environment.

        Returns a list of Dockerfile instruction strings. The caller handles
        the common parts (git clone, history cleanup, Harbor additions).
        """

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
