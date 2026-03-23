#!/usr/bin/env python3
"""
pipeline.py — Unified validate pipeline: verify + local oracle + NOP per PR.

Combines PR verification with immediate local oracle and NOP validation so
you know each instance is valid without waiting for Docker builds.  Outputs
verified_instances.json that can later be batch-packaged with
``package_instances.py`` and Docker-tested once with ``smoke_test.py``.

─── Workflow (per PR) ──────────────────────────────────────────────────────────

    ┌──────────┐     ┌────────────────┐     ┌────────────────┐
    │ verify   │ ──► │ local oracle   │ ──► │ local NOP      │
    │ (f2p)    │     │ (reward = 1?)  │     │ (reward = 0?)  │
    └──────────┘     └────────────────┘     └────────────────┘

─── Usage ──────────────────────────────────────────────────────────────────────

    # Validate 5 PRs end-to-end (verify + oracle + NOP):
    python pipeline.py --repo elastic/elasticsearch \\
        --input elastic__elasticsearch_prs.json --limit 5

    # Resume a previous run:
    python pipeline.py --repo elastic/elasticsearch \\
        --input elastic__elasticsearch_prs.json --resume

    # Skip NOP validation (faster, slightly less safe):
    python pipeline.py --repo elastic/elasticsearch \\
        --input elastic__elasticsearch_prs.json --skip-nop

─── After pipeline produces validated instances ────────────────────────────────

    # Batch-package all validated instances for Harbor:
    python package_instances.py --input validated_instances.json

    # Docker-test ONE instance to confirm the template works:
    python smoke_test.py --task-dir harbor_tasks/elastic__elasticsearch-135899
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

# Local modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import get_adapter
from github_api import fetch_commit_shas
from repo_config import get_config, registered_repos
from smoke_test import run_local_oracle
from verify_instances import (
    ensure_clone,
    load_candidates,
    load_results,
    save_results,
    verify_pr,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "benchmark-pipeline" / "validated_instances.json"


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified validate pipeline: verify + local oracle + NOP per PR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Output: validated_instances.json\n"
            "Next:   python package_instances.py --input validated_instances.json\n"
            "Then:   python smoke_test.py --task-dir <one-instance>  (Docker sanity check)"
        ),
    )
    parser.add_argument(
        "--repo", type=str, default="elastic/elasticsearch",
        help="Repository slug (default: elastic/elasticsearch). "
             f"Registered: {', '.join(registered_repos())}",
    )
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Input JSON file from fetch_prs.py (e.g. elastic__elasticsearch_prs.json)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output JSON file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--clone-dir", type=str, default=None,
        help="Directory for repo clone (default: from repo config)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of PRs to process",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from previous run (skip already-processed PRs)",
    )
    parser.add_argument(
        "--skip-nop", action="store_true",
        help="Skip NOP validation (faster, less safe — won't catch trivially-passing tests)",
    )
    parser.add_argument(
        "--timeout", type=int, default=600,
        help="Timeout in seconds per test run (default: 600)",
    )
    args = parser.parse_args()

    # ── Setup ──
    repo_config = get_config(args.repo)
    adapter = get_adapter(repo_config.adapter_name)
    clone_dir = args.clone_dir or repo_config.get_clone_dir()

    print("=" * 70)
    print("  Unified Validate Pipeline")
    print(f"  Repo:    {args.repo}")
    print(f"  Adapter: {adapter.language_name} + {adapter.build_tool_name}")
    print(f"  Steps:   verify → oracle → {'NOP' if not args.skip_nop else '(NOP skipped)'}")
    print("=" * 70)

    # Prerequisites
    print("\n[Prerequisites]")
    if not adapter.check_prerequisites(repo_config):
        print(f"Prerequisites not met for {adapter.language_name}/{adapter.build_tool_name}.")
        sys.exit(1)

    # Load candidates
    print(f"\n[Loading data]")
    if not args.input.exists():
        print(f"Error: {args.input} not found")
        sys.exit(1)

    candidates = load_candidates(args.input, args.repo, repo_config)
    print(f"  {len(candidates)} candidates for {args.repo}")

    # Resume support
    if args.resume:
        results, already_done = load_results(args.output)
        candidates = [c for c in candidates if c["pr_number"] not in already_done]
        print(f"  {len(already_done)} already processed, {len(candidates)} remaining")
    else:
        results, already_done = [], set()

    if not candidates:
        print("\nNo candidates to process.")
        return

    if args.limit:
        candidates = candidates[: args.limit]

    # Fetch commit SHAs in bulk
    print(f"\n[Fetching commit SHAs]")
    owner, repo_name = args.repo.split("/")
    pr_numbers = [pr["pr_number"] for pr in candidates]
    sha_map = fetch_commit_shas(owner, repo_name, pr_numbers)
    print(f"  Resolved SHAs for {len(sha_map)}/{len(pr_numbers)} PRs")
    candidates = [c for c in candidates if c["pr_number"] in sha_map]

    # Ensure repo clone exists
    print(f"\n[Repository setup]")
    if not os.path.isdir(clone_dir):
        repo_url = f"https://github.com/{args.repo}.git"
        if not ensure_clone(repo_url, clone_dir):
            print("Failed to clone repo. Exiting.")
            sys.exit(1)
    else:
        print(f"  Using existing clone at {clone_dir}")

    # ── Process each PR ──
    stats: dict[str, int] = {}
    print(f"\n[Processing {len(candidates)} PRs]")

    for i, pr in enumerate(candidates):
        pr_number = pr["pr_number"]
        shas = sha_map[pr_number]

        print(f"\n{'═' * 70}")
        print(f"[{i + 1}/{len(candidates)}] PR #{pr_number}: {pr['title'][:55]}")
        print(f"  base={shas['base_commit'][:10]} merge={shas['merge_commit'][:10]}")
        t0 = time.time()

        # ── Step 1: Verify ──
        print(f"\n  ── Step 1/{'3' if not args.skip_nop else '2'}: Verify instance ──")
        try:
            result = verify_pr(pr, shas, clone_dir, repo_config)
        except Exception as e:
            result = {
                "pr_number": pr_number,
                "instance_id": f"{owner}__{repo_name}-{pr_number}".lower(),
                "repo": args.repo,
                "title": pr["title"],
                "merge_commit": shas["merge_commit"],
                "base_commit": shas["base_commit"],
                "status": "error",
                "instance_type": "",
                "details": f"Exception: {str(e)[:500]}",
            }

        if result["status"] != "verified":
            status = result["status"]
            stats[status] = stats.get(status, 0) + 1
            elapsed = time.time() - t0
            print(f"  → {status}: {result.get('details', '')[:80]}  ({elapsed:.0f}s)")
            results.append(result)
            save_results(results, args.output)
            continue

        print(f"  → verified ({result.get('instance_type')}): "
              f"{len(result.get('fail_to_pass', []))} fail_to_pass, "
              f"{len(result.get('pass_to_pass', []))} pass_to_pass")

        # ── Step 2: Local oracle (expect reward=1) ──
        step_count = "3" if not args.skip_nop else "2"
        print(f"\n  ── Step 2/{step_count}: Local oracle (gold patch → reward=1?) ──")
        try:
            oracle_reward = run_local_oracle(
                result, clone_dir, adapter, repo_config,
                nop=False, timeout=args.timeout,
            )
        except Exception as e:
            oracle_reward = 0
            print(f"  Oracle exception: {str(e)[:200]}")

        if oracle_reward != 1:
            result["status"] = "invalid_oracle_failed"
            result["details"] = (
                f"Local oracle returned reward={oracle_reward} "
                f"(expected 1 — tests should pass with gold patch)"
            )
            stats["invalid_oracle_failed"] = stats.get("invalid_oracle_failed", 0) + 1
            elapsed = time.time() - t0
            print(f"  → invalid_oracle_failed  ({elapsed:.0f}s)")
            results.append(result)
            save_results(results, args.output)
            continue

        # ── Step 3: Local NOP (expect reward=0) ──
        if not args.skip_nop:
            print(f"\n  ── Step 3/3: Local NOP (no patch → reward=0?) ──")
            try:
                nop_reward = run_local_oracle(
                    result, clone_dir, adapter, repo_config,
                    nop=True, timeout=args.timeout,
                )
            except Exception as e:
                nop_reward = 1
                print(f"  NOP exception: {str(e)[:200]}")

            if nop_reward != 0:
                result["status"] = "invalid_nop_passed"
                result["details"] = (
                    f"NOP agent returned reward={nop_reward} "
                    f"(expected 0 — tests should fail WITHOUT the fix)"
                )
                stats["invalid_nop_passed"] = stats.get("invalid_nop_passed", 0) + 1
                elapsed = time.time() - t0
                print(f"  → invalid_nop_passed  ({elapsed:.0f}s)")
                results.append(result)
                save_results(results, args.output)
                continue

        # ── All checks passed ──
        result["oracle_validated"] = True
        stats["validated"] = stats.get("validated", 0) + 1
        elapsed = time.time() - t0
        print(f"\n  ✓ VALIDATED ({result.get('instance_type')}) — {elapsed:.0f}s")

        results.append(result)
        save_results(results, args.output)

    # ── Summary ──
    validated = [r for r in results if r.get("oracle_validated")]
    print(f"\n{'═' * 70}")
    print("SUMMARY")
    print(f"{'═' * 70}")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")
    print(f"  Total processed: {sum(stats.values())}")
    print(f"\n  Fully validated instances: {len(validated)}")
    print(f"  Results saved to: {args.output}")
    if validated:
        print(f"\n  Next steps:")
        print(f"    1. Package:      python package_instances.py --input {args.output}")
        print(f"    2. Docker test:  python smoke_test.py --task-dir <one-instance>")


if __name__ == "__main__":
    main()
