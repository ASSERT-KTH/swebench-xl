"""
JUnit XML test result parsing using junitparser.

Parses Gradle's test report XML files and returns method-level results.
"""

import os
import re
from typing import Dict, List, Tuple

from junitparser import JUnitXml, TestCase, TestSuite


def find_report_xmls(gradle_cmds: List[str], repo_dir: str) -> List[str]:
    """
    Find JUnit XML report files for modules referenced by Gradle commands.
    Reports live at <module>/build/test-results/test/TEST-*.xml
    """
    xml_files: list[str] = []
    for cmd in gradle_cmds:
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


def parse_results(xml_files: List[str]) -> Tuple[List[str], List[str]]:
    """
    Parse JUnit XML reports and return (failed_tests, passed_tests).

    Each entry is 'classname::testName' (method-level).
    """
    failed: list[str] = []
    passed: list[str] = []

    for xml_path in xml_files:
        try:
            xml = JUnitXml.fromfile(xml_path)
        except Exception:
            continue

        # JUnitXml can be a TestSuite or contain multiple suites
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
                    # No result element means passed
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


def parse_test_methods_from_source(java_source: str) -> List[str]:
    """
    Extract @Test-annotated method names from Java source code.

    Returns list of method names (not FQNs — caller must prepend classname).
    """
    methods: list[str] = []
    lines = java_source.splitlines()
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
