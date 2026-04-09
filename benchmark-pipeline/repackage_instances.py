#!/usr/bin/env python3
"""Re-package validated instances into harbor task directories.

Usage:
    python repackage_instances.py /path/to/validated_instances.json /path/to/output_dir

Reads already-validated instance records and runs them through
harbor_packager.generate_harbor_task() to produce fresh task directories
(with the current pipeline config, including noise repos in the base image).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harbor_packager import generate_harbor_task


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances_json", type=Path, help="Path to validated instances JSON")
    parser.add_argument("output_dir", type=Path, help="Output directory for harbor tasks")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing task dirs")
    parser.add_argument("--no-base-image", action="store_true", help="Generate self-contained Dockerfiles")
    args = parser.parse_args()

    with open(args.instances_json) as f:
        instances = json.load(f)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Packaging {len(instances)} instances into {args.output_dir}/")
    ok, failed = 0, 0

    for instance in instances:
        iid = instance["instance_id"]
        try:
            generate_harbor_task(
                instance,
                args.output_dir,
                overwrite=args.overwrite,
                use_base_image=not args.no_base_image,
                runtime_version=instance.get("runtime_version"),
            )
            ok += 1
            print(f"  [{ok}/{len(instances)}] {iid}")
        except Exception as e:
            failed += 1
            print(f"  FAILED {iid}: {e}", file=sys.stderr)

    print(f"\nDone: {ok} packaged, {failed} failed.")


if __name__ == "__main__":
    main()
