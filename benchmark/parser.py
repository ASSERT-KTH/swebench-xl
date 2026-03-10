#!/usr/bin/env python3
"""
Parser for Gradle/JUnit test output.
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
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def find_junit_xml_files(base_dir: str) -> list[Path]:
    """Find all JUnit XML test result files under the base directory."""
    xml_files = []
    base_path = Path(base_dir)

    # Look for test-results directories (Gradle standard location)
    for test_results_dir in base_path.rglob("test-results"):
        if test_results_dir.is_dir():
            for xml_file in test_results_dir.rglob("*.xml"):
                if xml_file.is_file():
                    xml_files.append(xml_file)

    return xml_files


def parse_junit_xml(xml_file: Path) -> list[dict]:
    """Parse a JUnit XML file and extract test results."""
    tests = []

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Handle both <testsuite> and <testsuites> root elements
        if root.tag == "testsuites":
            testsuites = root.findall("testsuite")
        elif root.tag == "testsuite":
            testsuites = [root]
        else:
            return tests

        for testsuite in testsuites:
            class_name = testsuite.get("name", "")

            for testcase in testsuite.findall("testcase"):
                method_name = testcase.get("name", "")
                tc_class = testcase.get("classname", class_name)

                # Determine status based on child elements
                if testcase.find("skipped") is not None:
                    status = "SKIPPED"
                elif testcase.find("failure") is not None:
                    status = "FAILED"
                elif testcase.find("error") is not None:
                    status = "FAILED"
                else:
                    status = "PASSED"

                # Build test name using fully-qualified class name to match config.json entries
                test_name = f"{tc_class}::{method_name}"

                tests.append({"name": test_name, "status": status})

    except ET.ParseError as e:
        print(f"Warning: Failed to parse {xml_file}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Error reading {xml_file}: {e}", file=sys.stderr)

    return tests


def parse_gradle_stdout_fallback(stdout: str, stderr: str) -> list[dict]:
    """Fallback parser for Gradle stdout when XML files are not available."""
    tests = []
    seen = set()
    combined = stdout + "\n" + stderr

    # Pattern for Gradle test result lines with explicit status
    # e.g., "org.elasticsearch.foo.BarTest > testMethod PASSED"
    pattern1 = re.compile(
        r"^\s*(\S+)\s+>\s+(.+?)\s+(PASSED|FAILED|SKIPPED)\s*$", re.MULTILINE
    )
    for match in pattern1.finditer(combined):
        class_name = match.group(1)
        method_name = match.group(2).strip()
        status = match.group(3)
        test_name = f"{class_name}::{method_name}"
        if test_name not in seen:
            seen.add(test_name)
            tests.append({"name": test_name, "status": status})

    # Pattern for Gradle --info mode: tests that output STANDARD_OUT ran successfully
    # unless there's an explicit FAILED. This is a heuristic fallback.
    if not tests:
        # Find tests that have STANDARD_OUT (they ran)
        pattern_ran = re.compile(
            r"^\s*(\S+)\s+>\s+(.+?)\s+STANDARD_OUT\s*$", re.MULTILINE
        )
        ran_tests = set()
        for match in pattern_ran.finditer(combined):
            class_name = match.group(1)
            method_name = match.group(2).strip()
            test_name = f"{class_name}::{method_name}"
            ran_tests.add(test_name)

        # Find tests that are explicitly SKIPPED
        pattern_skipped = re.compile(
            r"^\s*(\S+)\s+>\s+(.+?)\s+SKIPPED\s*$", re.MULTILINE
        )
        for match in pattern_skipped.finditer(combined):
            class_name = match.group(1)
            method_name = match.group(2).strip()
            test_name = f"{class_name}::{method_name}"
            if test_name not in seen:
                seen.add(test_name)
                tests.append({"name": test_name, "status": "SKIPPED"})

        # Tests that ran (STANDARD_OUT) but weren't marked SKIPPED are considered PASSED
        # if the build succeeded
        for test_name in ran_tests:
            if test_name not in seen:
                seen.add(test_name)
                tests.append({"name": test_name, "status": "PASSED"})

    return tests


def determine_build_result(stdout: str, stderr: str) -> str | None:
    """Determine overall build result from stdout/stderr."""
    combined = stdout + "\n" + stderr
    if "BUILD FAILED" in combined:
        return "FAILED"
    elif "BUILD SUCCESSFUL" in combined:
        return "PASSED"
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: parser.py <app_dir> [stdout_file] [stderr_file]", file=sys.stderr)
        print("  app_dir: Base directory to search for JUnit XML files (e.g., /app)", file=sys.stderr)
        print("  stdout_file: Optional stdout log for fallback parsing", file=sys.stderr)
        print("  stderr_file: Optional stderr log for fallback parsing", file=sys.stderr)
        sys.exit(1)

    app_dir = sys.argv[1]
    stdout_file = sys.argv[2] if len(sys.argv) > 2 else None
    stderr_file = sys.argv[3] if len(sys.argv) > 3 else None

    # Read stdout/stderr for build result detection and fallback parsing
    stdout = ""
    stderr = ""
    if stdout_file and os.path.exists(stdout_file):
        with open(stdout_file) as f:
            stdout = f.read()
    if stderr_file and os.path.exists(stderr_file):
        with open(stderr_file) as f:
            stderr = f.read()

    # Try to find and parse JUnit XML files first
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
        print("No JUnit XML files found, falling back to stdout parsing")
        tests = parse_gradle_stdout_fallback(stdout, stderr)
        print(f"Parsed {len(tests)} tests from stdout")

    # Determine build result
    build_result = determine_build_result(stdout, stderr)

    result = {"tests": tests, "build_result": build_result}

    output_path = "output.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {len(tests)} test results -> {output_path}")

    # Print summary
    passed = sum(1 for t in tests if t["status"] == "PASSED")
    failed = sum(1 for t in tests if t["status"] == "FAILED")
    skipped = sum(1 for t in tests if t["status"] == "SKIPPED")
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")


if __name__ == "__main__":
    main()
