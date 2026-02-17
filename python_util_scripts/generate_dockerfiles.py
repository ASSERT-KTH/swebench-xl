#!/usr/bin/env python3
"""
Generate Dockerfiles for the Elasticsearch benchmark.

Generates:
  1. benchmark/dockerfiles/base/Dockerfile
     - Shared base image: JDK 21, system deps, clones elasticsearch with --single-branch
  2. benchmark/dockerfiles/instances/<instance_id>/Dockerfile
     - Per-instance: resets to base_commit, applies git history cleanup
       (remove remote, delete future tags, expire reflog, gc --prune=now --aggressive,
        verify no future commits remain)

Reference: https://github.com/SWE-bench/SWE-bench/issues/465
"""

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT_DIR / "fail_to_pass_results.json"
DOCKERFILES_DIR = ROOT_DIR / "benchmark" / "dockerfiles"

BASE_IMAGE_NAME = "es-bench-base"


def load_verified_instances(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    verified = [d for d in data if d["status"] == "verified"]
    print(f"Loaded {len(data)} total instances, {len(verified)} verified")
    return verified


def generate_base_dockerfile(output_dir: Path):
    """Generate the shared base Dockerfile for Elasticsearch."""
    output_dir.mkdir(parents=True, exist_ok=True)

    dockerfile = """\
# Base image for Elasticsearch benchmark instances
# Contains: JDK 21, Gradle, system deps, elasticsearch repo (single-branch clone)

FROM eclipse-temurin:21-jdk-jammy

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    python3 \\
    python3-pip \\
    curl \\
    wget \\
    unzip \\
    jq \\
    && rm -rf /var/lib/apt/lists/*

# Clone elasticsearch with --single-branch to limit initial history exposure
RUN mkdir /app && \\
    git clone -o origin --single-branch https://github.com/elastic/elasticsearch.git /app

WORKDIR /app

ENTRYPOINT ["/bin/bash"]
"""

    dockerfile_path = output_dir / "Dockerfile"
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile)
    print(f"Wrote base Dockerfile: {dockerfile_path}")


def generate_instance_dockerfile(instance: dict, output_dir: Path):
    """Generate per-instance Dockerfile with git history cleanup.

    The cleanup follows the approach from SWE-bench v4.1.0 (issue #465):
    1. Reset to base_commit (the buggy version, before the fix PR)
    2. Remove remote origin (no fetching future code)
    3. Delete future tags (preserve past tags for legitimate use)
    4. Expire reflog
    5. Aggressive garbage collection
    6. Verify no future commits are accessible
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    instance_id = instance["instance_id"]
    base_commit = instance["base_commit"]

    dockerfile = f"""\
# Instance image for {instance_id}
# Elasticsearch {instance["version"]} @ {base_commit[:12]}
# PR #{instance["pr_number"]}: {instance["title"][:80]}
#
# The repo is checked out at the buggy commit (before the fix).
# Git history is cleaned: no future commits, tags, or remote access.

FROM {BASE_IMAGE_NAME}

SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to the buggy version (base_commit, before the fix PR was merged)
RUN git checkout {base_commit} && \\
    git reset --hard {base_commit} && \\
    git clean -fdx

# === Git History Cleanup (SWE-bench issue #465) ===
# Prevents agents from cheating by looking at future commits/tags.

# 1. Remove remote origin so no future code can be fetched
# 2. Delete all branches except the current detached HEAD
# 3. Delete future tags (preserve past tags for legitimate use)
# 4. Expire reflog and garbage collect unreachable objects
RUN git remote remove origin && \\
    git branch -a | grep -v '\\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \\
    BASE_TIMESTAMP=$(git show -s --format=%ci {base_commit}) && \\
    git tag -l | while read tag; do \\
        TAG_COMMIT=$(git rev-list -n 1 "$tag" 2>/dev/null) || continue; \\
        TAG_TIME=$(git show -s --format=%ci "$TAG_COMMIT" 2>/dev/null) || continue; \\
        if [[ "$TAG_TIME" > "$BASE_TIMESTAMP" ]]; then \\
            git tag -d "$tag" > /dev/null 2>&1; \\
        fi; \\
    done && \\
    git reflog expire --expire=now --all && \\
    git gc --prune=now

# 5. Verify no future commits are accessible (exclude base_commit itself)
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci {base_commit})" \\
        --not {base_commit} 2>/dev/null | wc -l | tr -d ' ') && \\
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \\
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && \\
        git log --oneline --all --after="$(git show -s --format=%ci {base_commit})" --not {base_commit} && \\
        exit 1; \\
    fi && \\
    echo "Git history cleanup verified: no future commits accessible."

# 6. Verify we are at the correct commit
RUN CURRENT=$(git rev-parse HEAD) && \\
    if [ "$CURRENT" != "{base_commit}" ]; then \\
        echo "ERROR: HEAD is $CURRENT, expected {base_commit}" && \\
        exit 1; \\
    fi && \\
    echo "Verified: HEAD at {base_commit}"

WORKDIR /app
ENTRYPOINT ["/bin/bash"]
"""

    dockerfile_path = output_dir / "Dockerfile"
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile)


def main():
    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found", file=sys.stderr)
        sys.exit(1)

    instances = load_verified_instances(INPUT_FILE)

    # Generate base Dockerfile
    print("\n=== Generating base Dockerfile ===")
    base_dir = DOCKERFILES_DIR / "base"
    generate_base_dockerfile(base_dir)

    # Generate per-instance Dockerfiles
    print("\n=== Generating per-instance Dockerfiles ===")
    for i, inst in enumerate(instances):
        instance_id = inst["instance_id"]
        instance_dir = DOCKERFILES_DIR / "instances" / instance_id
        generate_instance_dockerfile(inst, instance_dir)

        if (i + 1) % 20 == 0 or i == len(instances) - 1:
            print(f"  Generated {i + 1}/{len(instances)} instance Dockerfiles")

    print(f"\n=== Done ===")
    print(f"Base Dockerfile:     {DOCKERFILES_DIR}/base/Dockerfile")
    print(f"Instance Dockerfiles: {DOCKERFILES_DIR}/instances/<instance_id>/Dockerfile")
    print(f"Total: 1 base + {len(instances)} instance Dockerfiles")
    print()
    print("To build:")
    print(f"  docker build -t {BASE_IMAGE_NAME} {DOCKERFILES_DIR}/base/")
    print(f"  docker build -t es-bench-<instance_id> {DOCKERFILES_DIR}/instances/<instance_id>/")


if __name__ == "__main__":
    main()
