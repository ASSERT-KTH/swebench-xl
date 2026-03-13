"""
Gradle command building and test execution.

Handles:
  - Extracting Gradle module paths from file paths
  - Extracting fully-qualified class names from test file paths
  - Building ./gradlew test and compileTestJava commands
  - Running Gradle with timeout and output capture
"""

import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

GRADLE_FLAGS = ["--no-daemon", "--stacktrace", "-x", "javadoc", "--no-configuration-cache", "--max-workers=2"]
DEFAULT_TIMEOUT = 600  # 10 minutes

# Limit Gradle JVM heap so it fits in memory-constrained environments (e.g. 8 GB).
GRADLE_ENV_OVERRIDES = {
    "GRADLE_OPTS": "-Xmx2g",
}


def extract_gradle_module(filepath: str) -> Optional[str]:
    """
    Extract the Gradle module path from a file path.

    Examples:
        'x-pack/plugin/esql/src/test/java/...' -> ':x-pack:plugin:esql'
        'server/src/test/java/...'              -> ':server'
    """
    parts = filepath.split("/")
    try:
        src_idx = parts.index("src")
        module_path = "/".join(parts[:src_idx])
        return ":" + module_path.replace("/", ":")
    except ValueError:
        return None


def extract_test_fqn(filepath: str) -> Optional[str]:
    """
    Extract the fully-qualified class name from a test file path.

    Example:
        'x-pack/.../src/test/java/org/elasticsearch/xpack/FooTests.java'
        -> 'org.elasticsearch.xpack.FooTests'
    """
    parts = filepath.split("/")
    try:
        java_idx = parts.index("java")
        fqn = ".".join(parts[java_idx + 1 :])
        return fqn.replace(".java", "")
    except ValueError:
        return None


def build_test_commands(test_files: List[str]) -> List[str]:
    """
    Build ./gradlew test commands grouped by module.
    """
    module_tests: Dict[str, List[str]] = {}
    for filepath in test_files:
        if not filepath.endswith(".java"):
            continue
        module = extract_gradle_module(filepath)
        fqn = extract_test_fqn(filepath)
        if not module or not fqn:
            continue
        module_tests.setdefault(module, []).append(fqn)

    commands = []
    for module, fqns in module_tests.items():
        test_filters = " ".join(f"--tests {fqn}" for fqn in fqns)
        flags = " ".join(GRADLE_FLAGS)
        cmd = f"./gradlew {module}:test {test_filters} {flags}"
        commands.append(cmd)
    return commands


def build_compile_commands(test_files: List[str]) -> List[str]:
    """
    Build ./gradlew compileTestJava commands to check if tests compile
    without running them. Used to detect feature additions.
    """
    modules = set()
    for filepath in test_files:
        if not filepath.endswith(".java"):
            continue
        module = extract_gradle_module(filepath)
        if module:
            modules.add(module)

    flags = " ".join(GRADLE_FLAGS)
    return [f"./gradlew {module}:compileTestJava {flags}" for module in sorted(modules)]


def run_gradle(
    commands: List[str],
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[bool, str, int]:
    """
    Run Gradle commands sequentially.

    Returns: (all_passed, combined_output, last_exit_code)
    """
    all_output: list[str] = []
    env = os.environ.copy()
    for k, v in GRADLE_ENV_OVERRIDES.items():
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
            # Keep last 80 lines for diagnostics
            lines = combined.split("\n")
            all_output.append("\n".join(lines[-80:]))

            if result.returncode != 0:
                print(f"    FAILED (exit code {result.returncode})")
                return False, "\n---\n".join(all_output), result.returncode
            print(f"    PASSED")

        except subprocess.TimeoutExpired:
            all_output.append(f"TIMEOUT after {timeout}s")
            print(f"    TIMEOUT")
            return False, "\n---\n".join(all_output), -1

    return True, "\n---\n".join(all_output), 0


def compile_tests(
    test_files: List[str],
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[bool, str]:
    """
    Compile test files without running them.

    Returns: (compiles_ok, output)
    """
    commands = build_compile_commands(test_files)
    if not commands:
        return False, "No compile commands could be built"
    passed, output, _ = run_gradle(commands, cwd, timeout)
    return passed, output


def run_tests(
    test_files: List[str],
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[bool, str]:
    """
    Run tests and return (passed, output).
    """
    commands = build_test_commands(test_files)
    if not commands:
        return False, "No test commands could be built"
    passed, output, _ = run_gradle(commands, cwd, timeout)
    return passed, output


def parse_compile_errors(output: str) -> List[Dict[str, str]]:
    """
    Parse 'cannot find symbol' errors from javac output.

    Returns list of dicts with keys: class_name, symbol, location
    """
    errors: list[dict[str, str]] = []
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if "cannot find symbol" in line.lower():
            error: dict[str, str] = {"raw": line.strip()}
            # Look ahead for symbol and location lines
            for j in range(i + 1, min(i + 5, len(lines))):
                stripped = lines[j].strip()
                if stripped.startswith("symbol:"):
                    error["symbol"] = stripped.replace("symbol:", "").strip()
                elif stripped.startswith("location:"):
                    error["location"] = stripped.replace("location:", "").strip()
            errors.append(error)
        i += 1
    return errors


def extract_missing_methods(compile_output: str) -> List[Dict[str, str]]:
    """
    From compile errors, extract method signatures that don't exist yet.

    Returns list of dicts: {method: str, class: str}
    """
    methods: list[dict[str, str]] = []
    errors = parse_compile_errors(compile_output)
    for err in errors:
        symbol = err.get("symbol", "")
        location = err.get("location", "")
        # symbol looks like: "method someMethod(ParamType)"
        m = re.match(r"method\s+(\w+)\s*\(([^)]*)\)", symbol)
        if m:
            method_name = m.group(1)
            params = m.group(2)
            loc_class = ""
            loc_match = re.search(r"class\s+([\w.]+)", location)
            if loc_match:
                loc_class = loc_match.group(1)
            methods.append({
                "method": method_name,
                "params": params,
                "class": loc_class,
            })
    # Deduplicate
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for m in methods:
        key = f"{m['class']}.{m['method']}({m['params']})"
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique
