#!/usr/bin/env python3
"""
package_instances.py — Step 2: Package verified instances as Harbor tasks.

Reads verified_instances.json (output of verify_instances.py) and generates
complete Harbor task directories.

Usage:
    python package_instances.py
    python package_instances.py --input verified_instances.json --output-dir ../harbor_tasks_new
    python package_instances.py --instance-id elastic__elasticsearch-129503
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harbor_packager import generate_harbor_task

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "benchmark-pipeline" / "verified_instances.json"
DEFAULT_OUTPUT = ROOT / "harbor_tasks_new"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package verified instances as Harbor task directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Input: verified_instances.json (from verify_instances.py)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input JSON file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory for Harbor tasks (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--instance-id",
        type=str,
        default=None,
        help="Package a single instance only",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Agent/verifier timeout in seconds (default: 3600)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing task directories",
    )
    parser.add_argument(
        "--no-gradlew-wrapper",
        action="store_true",
        help="Don't install gradlew wrapper (agent must handle root user)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of instances to package",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  Step 2: Package Instances")
    print("=" * 70)

    if not args.input.exists():
        print(f"Error: {args.input} not found")
        print("Run verify_instances.py first to generate this file.")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        all_results = json.load(f)

    # Filter to verified instances only
    verified = [r for r in all_results if r["status"] == "verified"]
    print(f"\n  {len(all_results)} total results, {len(verified)} verified")

    if args.instance_id:
        verified = [r for r in verified if r["instance_id"] == args.instance_id]
        if not verified:
            print(f"Error: Instance {args.instance_id} not found or not verified")
            sys.exit(1)

    if args.limit:
        verified = verified[: args.limit]

    if not verified:
        print("No verified instances to package.")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    gradlew_wrapper = not args.no_gradlew_wrapper

    print(f"  Packaging {len(verified)} instances into: {args.output_dir}")
    print(f"  Gradlew wrapper: {'enabled' if gradlew_wrapper else 'disabled'}\n")

    success, failures = [], []
    for i, instance in enumerate(verified, 1):
        instance_id = instance["instance_id"]
        jdk_version = instance.get("jdk_version")

        try:
            task_dir = generate_harbor_task(
                instance,
                args.output_dir,
                overwrite=args.overwrite,
                timeout_sec=args.timeout,
                gradlew_wrapper=gradlew_wrapper,
                jdk_version=jdk_version,
            )
            itype = instance.get("instance_type", "?")
            ftp = len(instance.get("fail_to_pass", []))
            print(f"  [{i:3d}/{len(verified)}] OK   {instance_id} ({itype}, {ftp} fail_to_pass)")
            success.append(instance_id)
        except Exception as e:
            print(f"  [{i:3d}/{len(verified)}] FAIL {instance_id}: {e}")
            failures.append((instance_id, str(e)))

    print(f"\n{'=' * 60}")
    print(f"Done. Success: {len(success)}  Failures: {len(failures)}")
    print(f"Output: {args.output_dir}")
    if failures:
        print("\nFailed instances:")
        for iid, reason in failures:
            print(f"  - {iid}: {reason}")


if __name__ == "__main__":
    main()
