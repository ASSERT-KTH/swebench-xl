# Benchmark Pipeline Adapters

The adapter system makes the benchmark pipeline language-agnostic. Instead of
hardcoding Java/Gradle assumptions, all language- and build-tool-specific logic
lives in **adapter classes** under `benchmark-pipeline/adapters/`.

## How It Works

```
RepoConfig(slug="elastic/elasticsearch", adapter_name="java-gradle")
                                              │
                                              ▼
                                    adapters/__init__.py
                                     get_adapter("java-gradle")
                                              │
                                              ▼
                                    JavaGradleAdapter
                                   (adapters/java_gradle.py)
```

Every pipeline stage — PR fetching, instance verification, and Harbor packaging —
calls adapter methods instead of using hardcoded Gradle/Java logic.

## Adding a New Language/Build-Tool

### 1. Create the adapter

Create a new file `adapters/my_language.py` and subclass `LanguageAdapter`:

```python
from adapters.base import LanguageAdapter, CompileError, MissingSymbol

class PythonPytestAdapter(LanguageAdapter):

    @property
    def language_name(self) -> str:
        return "Python"

    @property
    def build_tool_name(self) -> str:
        return "pytest"

    @property
    def source_file_extensions(self) -> tuple[str, ...]:
        return (".py",)

    def is_test_file(self, filename, config):
        basename = filename.rsplit("/", 1)[-1]
        return basename.startswith("test_") or basename.endswith("_test.py")

    def is_source_file(self, filename, config):
        return filename.endswith(".py") and not self.is_test_file(filename, config)

    def is_test_support_file(self, filename, config):
        basename = filename.rsplit("/", 1)[-1]
        return basename == "conftest.py"

    # ... implement all abstract methods
```

### 2. Register the adapter

In `adapters/__init__.py`, add:

```python
from adapters.my_language import PythonPytestAdapter
register_adapter("python-pytest", PythonPytestAdapter())
```

### 3. Create repo configs

In `repo_config.py`, register repos that use your adapter:

```python
register_repo(RepoConfig(
    slug="pallets/flask",
    adapter_name="python-pytest",
    base_image="python:3.12-slim",
    system_packages="git curl",
    # Java/Gradle-specific fields can be left at defaults (they're ignored)
))
```

### 4. That's it

The pipeline (`fetch_prs.py`, `verify_instances.py`, `package_instances.py`) will
automatically use your adapter for repos with `adapter_name="python-pytest"`.

## Abstract Methods to Implement

See `adapters/base.py` for the full interface. Key method groups:

| Category | Methods | Purpose |
|----------|---------|---------|
| **Identity** | `language_name`, `build_tool_name`, `source_file_extensions` | Display and filtering |
| **File classification** | `is_test_file`, `is_source_file`, `is_test_support_file`, `classify_files` | Split PR patches into test/source/support |
| **PR filtering** | `has_test_and_source_files`, `has_test_files_in_pr` | Quick pre-filter during PR fetching |
| **Test IDs** | `extract_test_fqn`, `extract_module` | Map file paths to test identifiers |
| **Build commands** | `build_test_commands`, `build_compile_commands`, `run_commands` | Run tests and compilation |
| **Results** | `find_test_reports`, `parse_test_results`, `extract_test_methods_from_source` | Parse test output |
| **Compile errors** | `parse_compile_errors`, `extract_missing_symbols` | Feature-addition detection |
| **Environment** | `check_build_tool_exists`, `check_prerequisites`, `detect_runtime_version` | Pre-flight checks |
| **Docker** | `generate_dockerfile_lines`, `generate_run_script` | Harbor task packaging |

## Existing Adapters

- **`java-gradle`** — Java + Gradle (default). Handles JUnit XML parsing,
  `./gradlew` commands, `@Test` annotation extraction, and Gradle module paths.

## Architecture Notes

- `adapters/base.py` provides default implementations for `classify_files`,
  `compile_tests`, `run_tests`, and `format_symbol_hints` — you only need to
  override them if your language needs different logic.
- The `generate_test_parser_script()` method can return a custom `parser.py`
  for the Harbor container. Return `None` to use the default JUnit XML parser.
- `RepoConfig` fields like `gradle_flags` and `gradle_env_overrides` are only
  used by `JavaGradleAdapter` — other adapters can ignore them or use the
  `extra` dict for their own settings.
