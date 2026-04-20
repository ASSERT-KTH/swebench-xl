#!/usr/bin/env python3
"""Parser for pytest JUnit XML test results (transformers)."""
import argparse
import json
import os
import sys
from pathlib import Path
from junitparser import JUnitXml, TestCase, TestSuite


def parse_junit_file(xml_path: str):
    passed, failed = [], []
    try:
        xml = JUnitXml.fromfile(xml_path)
    except Exception as e:
        print(f"Failed to parse {xml_path}: {e}", file=sys.stderr)
        return passed, failed

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
                is_fail = any(
                    "fail" in type(r).__name__.lower() or "error" in type(r).__name__.lower()
                    for r in results
                )
                if is_skip:
                    continue
                elif is_fail:
                    failed.append(test_id)
                else:
                    passed.append(test_id)
    return passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True,
                    help="Directory containing junit.xml")
    ap.add_argument("--output", required=True,
                    help="Output JSON file path")
    args = ap.parse_args()

    xml_path = os.path.join(args.report_dir, "junit.xml")
    if not os.path.isfile(xml_path):
        print(f"JUnit XML not found: {xml_path}", file=sys.stderr)
        json.dump({"passed": [], "failed": []}, open(args.output, "w"))
        return

    passed, failed = parse_junit_file(xml_path)
    print(f"Parsed {len(passed)} passed, {len(failed)} failed")
    with open(args.output, "w") as f:
        json.dump({"passed": passed, "failed": failed}, f, indent=2)


if __name__ == "__main__":
    main()
