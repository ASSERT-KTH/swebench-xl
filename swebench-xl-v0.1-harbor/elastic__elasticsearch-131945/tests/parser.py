#!/usr/bin/env python3
"""
Parser for Gradle/JUnit test output using junitparser.
Reads JUnit XML test result files and produces structured JSON with test results.

Output format:
{
    "tests": [
        {"name": "org.elasticsearch.foo.BarTest::testMethod", "status": "PASSED"},
        {"name": "org.elasticsearch.foo.BazTest::testOther", "status": "FAILED"}
    ],
    "build_result": "PASSED"
}
"""

import json
import os
import sys
from pathlib import Path

from junitparser import JUnitXml, TestCase, TestSuite


def find_junit_xml_files(base_dir: str) -> list[Path]:
    """Find all JUnit XML test result files under the base directory."""
    xml_files = []
    base_path = Path(base_dir)

    for test_results_dir in base_path.rglob("test-results"):
        if test_results_dir.is_dir():
            for xml_file in test_results_dir.rglob("*.xml"):
                if xml_file.is_file():
                    xml_files.append(xml_file)

    return xml_files


def parse_junit_xml(xml_file: Path) -> list[dict]:
    """Parse a JUnit XML file using junitparser and extract test results."""
    tests = []

    try:
        xml = JUnitXml.fromfile(str(xml_file))
    except Exception as e:
        print(f"Warning: Failed to parse {xml_file}: {e}", file=sys.stderr)
        return tests

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

            test_name = f"{classname}::{name}"

            if case.result is None:
                status = "PASSED"
            else:
                result_items = case.result if isinstance(case.result, list) else [case.result]
                is_failure = False
                is_skipped = False
                for r in result_items:
                    rtype = type(r).__name__.lower()
                    if "skip" in rtype:
                        is_skipped = True
                    elif "fail" in rtype or "error" in rtype:
                        is_failure = True

                if is_skipped:
                    status = "SKIPPED"
                elif is_failure:
                    status = "FAILED"
                else:
                    status = "PASSED"

            tests.append({"name": test_name, "status": status})

    return tests


def determine_build_result(stdout: str, stderr: str) -> str | None:
    """Determine overall build result from Gradle stdout/stderr."""
    combined = stdout + "\n" + stderr
    if "BUILD SUCCESSFUL" in combined:
        return "PASSED"
    elif "BUILD FAILED" in combined:
        return "FAILED"
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: parser.py <app_dir> [stdout_file] [stderr_file]", file=sys.stderr)
        sys.exit(1)

    app_dir = sys.argv[1]
    stdout_file = sys.argv[2] if len(sys.argv) > 2 else None
    stderr_file = sys.argv[3] if len(sys.argv) > 3 else None

    stdout = ""
    stderr = ""
    if stdout_file and os.path.exists(stdout_file):
        with open(stdout_file) as f:
            stdout = f.read()
    if stderr_file and os.path.exists(stderr_file):
        with open(stderr_file) as f:
            stderr = f.read()

    # Parse JUnit XML files (the only reliable source of test results)
    tests = []
    xml_files = find_junit_xml_files(app_dir)

    if xml_files:
        print(f"Found {len(xml_files)} JUnit XML file(s)")
        seen = set()
        for xml_file in xml_files:
            for test in parse_junit_xml(xml_file):
                if test["name"] not in seen:
                    seen.add(test["name"])
                    tests.append(test)
        print(f"Parsed {len(tests)} tests from XML files")
    else:
        print("No JUnit XML files found (build likely failed before tests ran)")

    build_result = determine_build_result(stdout, stderr)

    result = {"tests": tests, "build_result": build_result}

    output_path = "output.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    passed = sum(1 for t in tests if t["status"] == "PASSED")
    failed = sum(1 for t in tests if t["status"] == "FAILED")
    skipped = sum(1 for t in tests if t["status"] == "SKIPPED")
    print(f"Wrote {len(tests)} test results -> {output_path}")
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped, build={build_result}")


if __name__ == "__main__":
    main()
