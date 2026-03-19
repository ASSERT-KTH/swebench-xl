#!/usr/bin/env python3
"""
smoke_test.py — End-to-end pipeline validation using a known-good PR.

Validates the full chain: PR data → verify_instances → package → docker build → oracle → reward 1.

This does NOT run a Harbor agent. It applies the gold patch (solve.sh) directly
and executes test.sh to confirm reward=1. This is much faster than
``harbor run`` because it skips the agent entirely — Docker build + test
execution only, typically 10–20 minutes for Elasticsearch.

─── Workflow ───────────────────────────────────────────────────────────────────

    ┌─────────────┐     ┌──────────┐     ┌─────────┐     ┌────────────────┐
    │ PR data     │ ──► │ verify   │ ──► │ package │ ──► │ docker oracle  │
    │ (fixture)   │     │          │     │         │     │ (solve + test) │
    └─────────────┘     └──────────┘     └─────────┘     └────────────────┘

─── Usage ──────────────────────────────────────────────────────────────────────

  First time — build a fixture from a known-good PR:

    # Fetch PR from GitHub, verify, package, and save as fixture:
    python smoke_test.py --repo elastic/elasticsearch --pr 135899 \\
        --save-fixture tests/fixtures/es-135899.json --no-docker

    # Or load PR from an existing fetch_prs.py output file:
    python smoke_test.py --repo elastic/elasticsearch --pr 135899 \\
        --prs-json elastic__elasticsearch_prs.json \\
        --save-fixture tests/fixtures/es-135899.json --no-docker

  After making pipeline changes — fast iteration:

    # Fastest (~1s): only test packaging logic (no clone, no Docker):
    python smoke_test.py --fixture tests/fixtures/es-135899.json \\
        --skip-verify --no-docker

    # Medium (~10-20 min): test packaging + Docker oracle:
    python smoke_test.py --fixture tests/fixtures/es-135899.json \\
        --skip-verify

    # Full (~15-25 min): re-verify from repo clone + Docker oracle:
    python smoke_test.py --fixture tests/fixtures/es-135899.json

  Test a pre-existing Harbor task directory (already packaged):

    python smoke_test.py --task-dir ../harbor_tasks_approved/elastic__elasticsearch-135899

─── Speed comparison vs ``harbor run`` ─────────────────────────────────────────

  ``harbor run`` spins up an LLM agent to solve the task, which is the purpose
  of the benchmark but takes 10–60+ minutes.  This script applies the gold
  patch directly and just checks that test.sh produces reward=1.  Docker build
  time is identical either way — the speedup comes entirely from skipping the
  agent.

  ┌──────────────────────┬──────────────┬──────────────────────────────┐
  │ Mode                 │ Time         │ What it validates            │
  ├──────────────────────┼──────────────┼──────────────────────────────┤
  │ --skip-verify        │ ~1 second    │ packaging logic only         │
  │   --no-docker        │              │                              │
  │ --skip-verify        │ ~10-20 min   │ packaging + Dockerfile +     │
  │                      │              │ test.sh + parser.py          │
  │ (full, no flags)     │ ~15-25 min   │ full pipeline end-to-end     │
  │ harbor run           │ ~30-90 min   │ agent solving ability        │
  └──────────────────────┴──────────────┴──────────────────────────────┘
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure benchmark-pipeline is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import get_adapter
from base_image import ensure_base_image
from harbor_packager import generate_harbor_task
from repo_config import get_config


# ── PR data loading ───────────────────────────────────────────────────────────


def load_pr_from_prs_json(prs_json: Path, pr_number: int) -> Dict[str, Any]:
    """Find a specific PR in a fetch_prs.py output file."""
    with open(prs_json) as f:
        all_prs = json.load(f)
    for pr in all_prs:
        if pr["pr_number"] == pr_number:
            return pr
    raise ValueError(f"PR #{pr_number} not found in {prs_json}")


def fetch_single_pr(repo: str, pr_number: int) -> Dict[str, Any]:
    """Fetch a single PR from GitHub using fetch_prs.py internals."""
    from fetch_prs import fetch_pr_details_batch, fetch_pr_files

    owner, repo_name = repo.split("/")
    details = fetch_pr_details_batch(owner, repo_name, [pr_number])
    if pr_number not in details:
        raise ValueError(f"Could not fetch PR #{pr_number} from GitHub")
    d = details[pr_number]
    patches = fetch_pr_files(owner, repo_name, pr_number)
    return {
        "repo": repo,
        "pr_number": pr_number,
        "title": d["title"],
        "description": d.get("body", ""),
        "issues": d.get("issues", []),
        "files_changed": len(patches),
        "patches": patches,
        "merged_at": d.get("merged_at", ""),
    }


# ── Pipeline steps ────────────────────────────────────────────────────────────


def step_verify(pr: Dict, repo: str, clone_dir: str) -> Dict[str, Any]:
    """Run verify_pr on a single PR.  Returns the result dict."""
    from github_api import fetch_commit_shas
    from verify_instances import verify_pr

    config = get_config(repo)

    # Ensure the clone exists — if not, clone the repo first
    if not os.path.isdir(clone_dir):
        repo_url = f"https://github.com/{repo}.git"
        print(f"  Clone dir {clone_dir} not found — cloning {repo_url} ...")
        os.makedirs(os.path.dirname(clone_dir), exist_ok=True)
        ret = subprocess.run(
            ["git", "clone", repo_url, clone_dir],
            capture_output=True,
            timeout=3600,
        )
        if ret.returncode != 0:
            return {"status": "error", "details": f"git clone failed: {ret.stderr.decode()[:500]}"}

    owner, repo_name = repo.split("/")
    sha_map = fetch_commit_shas(owner, repo_name, [pr["pr_number"]])
    if pr["pr_number"] not in sha_map:
        return {"status": "error", "details": "Could not fetch commit SHAs"}
    shas = sha_map[pr["pr_number"]]
    print(f"  base={shas['base_commit'][:10]}  merge={shas['merge_commit'][:10]}")
    return verify_pr(pr, shas, clone_dir, config)


def step_package(instance: Dict, output_dir: Path, *, use_base_image: bool = True) -> Path:
    """Package a verified instance into a Harbor task directory."""
    return generate_harbor_task(instance, output_dir, overwrite=True, use_base_image=use_base_image)


def step_docker_oracle(
    task_dir: Path,
    timeout: int = 1800,
    *,
    repo_slug: Optional[str] = None,
    use_base_image: bool = True,
    rebuild_base: bool = False,
) -> int:
    """
    Build Docker image, apply gold patch, run test.sh, return reward.

    Returns 1 on success, 0 on test failure, -1 on build failure.
    """
    env_dir = task_dir / "environment"
    instance_id = task_dir.name
    image_tag = f"smoke-{instance_id}".lower()

    # ── Ensure base image exists ──
    if use_base_image and repo_slug:
        if not ensure_base_image(repo_slug, rebuild=rebuild_base):
            print("[docker] Base image build FAILED")
            return -1

    # ── Build ──
    print(f"\n{'─' * 60}")
    print(f"[docker] Building image {image_tag}...")
    if use_base_image and repo_slug:
        print(f"[docker] Using base image (fast — checkout + cleanup only)")
    else:
        print(f"[docker] Self-contained build (git clone + dependency install)")
    build = subprocess.run(
        ["docker", "build", "-t", image_tag, "."],
        cwd=env_dir,
        timeout=3600,
    )
    if build.returncode != 0:
        print(f"[docker] Build FAILED (exit {build.returncode})")
        return -1
    print("[docker] Build OK")

    # ── Run oracle ──
    # Mount tests/ and solution/ read-only, then apply gold patch and run test.sh.
    # Create a /logs dir inside the container for test.sh's reward file.
    print(f"[docker] Running oracle: solve.sh → test.sh")
    tests_dir = str(task_dir / "tests")
    solution_dir = str(task_dir / "solution")

    run_cmd = [
        "docker", "run", "--rm",
        "-v", f"{tests_dir}:/tests:ro",
        "-v", f"{solution_dir}:/solution:ro",
        image_tag,
        "bash", "-c",
        "bash /solution/solve.sh && bash /tests/test.sh",
    ]
    result = subprocess.run(run_cmd, capture_output=True, timeout=timeout)
    stdout = result.stdout.decode(errors="replace")
    stderr = result.stderr.decode(errors="replace")
    combined = stdout + "\n" + stderr

    # ── Evaluate ──
    if "RESULT: PASSED" in combined:
        print("[docker] RESULT: PASSED — reward=1")
        return 1

    print(f"[docker] RESULT: FAILED — reward=0  (exit code {result.returncode})")
    # Print tail for debugging
    tail = combined.strip().split("\n")[-40:]
    for line in tail:
        print(f"  | {line}")
    return 0


def step_validate_structure(task_dir: Path) -> bool:
    """Check that all expected files exist in the task directory."""
    expected = [
        "instruction.md",
        "task.toml",
        "environment/Dockerfile",
        "tests/config.json",
        "tests/run_script.sh",
        "tests/test.sh",
        "tests/parser.py",
        "solution/solve.sh",
    ]
    ok = True
    for rel in expected:
        if not (task_dir / rel).exists():
            print(f"  MISSING: {rel}")
            ok = False
    return ok


# ── Fixture I/O ───────────────────────────────────────────────────────────────


def save_fixture(pr: Dict, result: Dict, path: Path) -> None:
    """Save a known-good PR + verified result as a reusable fixture."""
    fixture = {"pr": pr, "verified_instance": result}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)
    print(f"[fixture] Saved to {path}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline smoke test using a known-good PR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input sources (mutually exclusive-ish)
    src = parser.add_argument_group("input source (pick one)")
    src.add_argument(
        "--fixture", type=Path,
        help="Load PR + verified instance from a fixture JSON file",
    )
    src.add_argument(
        "--task-dir", type=Path,
        help="Test an already-packaged Harbor task directory (skip verify+package)",
    )
    src.add_argument(
        "--pr", type=int,
        help="PR number to test (fetched from GitHub or --prs-json)",
    )
    src.add_argument(
        "--prs-json", type=Path,
        help="Load PR data from an existing fetch_prs.py output file",
    )

    # Options
    parser.add_argument(
        "--repo", type=str, default="elastic/elasticsearch",
        help="Repository slug (default: elastic/elasticsearch)",
    )
    parser.add_argument(
        "--clone-dir", type=str, default=None,
        help="Directory for repo clone (default: from repo config)",
    )
    parser.add_argument(
        "--skip-verify", action="store_true",
        help="Skip verification step (use fixture's verified_instance directly)",
    )
    parser.add_argument(
        "--no-docker", action="store_true",
        help="Skip Docker build+run (only test verify + package)",
    )
    parser.add_argument(
        "--no-base-image", action="store_true",
        help="Generate self-contained Dockerfiles (skip base image optimization)",
    )
    parser.add_argument(
        "--rebuild-base", action="store_true",
        help="Force rebuild of the repo base Docker image",
    )
    parser.add_argument(
        "--save-fixture", type=Path,
        help="Save the PR data + verified result as a fixture for future runs",
    )
    parser.add_argument(
        "--keep-task-dir", type=Path, default=None,
        help="Write the packaged task here instead of a temp dir (for inspection)",
    )
    args = parser.parse_args()

    # ── Mode: test an existing task directory ──
    if args.task_dir:
        task_dir = args.task_dir.resolve()
        print(f"[task-dir] Testing existing task: {task_dir.name}")
        if not step_validate_structure(task_dir):
            print("\nFAILED: task directory is incomplete")
            sys.exit(1)
        print("[task-dir] Structure OK")

        if args.no_docker:
            print("\nSMOKE TEST PASSED (structure only, --no-docker)")
            return

        reward = step_docker_oracle(
            task_dir,
            repo_slug=args.repo,
            use_base_image=not args.no_base_image,
            rebuild_base=args.rebuild_base,
        )
        _exit_with_reward(reward)
        return

    # ── Load PR data ──
    pr: Optional[Dict] = None
    verified: Optional[Dict] = None

    if args.fixture:
        with open(args.fixture) as f:
            fixture = json.load(f)
        pr = fixture["pr"]
        verified = fixture.get("verified_instance")
        args.repo = pr.get("repo", args.repo)
        print(f"[load] PR #{pr['pr_number']} from fixture {args.fixture.name}")
    elif args.prs_json and args.pr:
        pr = load_pr_from_prs_json(args.prs_json, args.pr)
        print(f"[load] PR #{args.pr} from {args.prs_json.name}")
    elif args.pr:
        print(f"[fetch] Fetching PR #{args.pr} from GitHub...")
        pr = fetch_single_pr(args.repo, args.pr)
        print(f"[fetch] {pr['title']}")
    else:
        parser.error("Provide --fixture, --task-dir, or --pr")

    config = get_config(args.repo)
    clone_dir = args.clone_dir or config.get_clone_dir()

    # ── Step 1: Verify ──
    print(f"\n{'=' * 60}")
    print("[step 1/3] Verify instance")
    print(f"{'=' * 60}")

    if args.skip_verify and verified and verified.get("status") == "verified":
        print(f"  Skipped (using fixture).  type={verified.get('instance_type')}")
        result = verified
    elif args.skip_verify and verified:
        print(f"  Fixture status is '{verified.get('status')}', not 'verified' — re-verifying")
        result = step_verify(pr, args.repo, clone_dir)
    else:
        result = step_verify(pr, args.repo, clone_dir)

    print(f"\n  Status: {result['status']}")
    if result["status"] != "verified":
        print(f"  Details: {result.get('details', '')}")
        print(f"\nFAILED at verification step")
        sys.exit(1)

    print(f"  Type: {result.get('instance_type')}")
    print(f"  fail_to_pass: {len(result.get('fail_to_pass', []))}")
    print(f"  pass_to_pass: {len(result.get('pass_to_pass', []))}")

    # Save fixture if requested
    if args.save_fixture:
        save_fixture(pr, result, args.save_fixture)

    # ── Step 2: Package ──
    print(f"\n{'=' * 60}")
    print("[step 2/3] Package Harbor task")
    print(f"{'=' * 60}")

    output_dir = args.keep_task_dir or Path(tempfile.mkdtemp(prefix="smoke_"))
    use_base = not args.no_base_image
    task_dir = step_package(result, output_dir, use_base_image=use_base)
    print(f"  Task dir: {task_dir}")

    if not step_validate_structure(task_dir):
        print("\nFAILED: packaged task directory is incomplete")
        sys.exit(1)
    print("  Structure OK")

    # Quick sanity checks on config.json
    cfg_data = json.loads((task_dir / "tests" / "config.json").read_text())
    assert cfg_data["instance_id"] == result["instance_id"], "instance_id mismatch"
    assert len(cfg_data.get("fail_to_pass", [])) > 0, "no fail_to_pass tests"
    print(f"  config.json OK ({len(cfg_data['fail_to_pass'])} fail_to_pass, "
          f"{len(cfg_data.get('pass_to_pass', []))} pass_to_pass)")

    # ── Step 3: Docker oracle ──
    if args.no_docker:
        print(f"\n{'=' * 60}")
        print("[step 3/3] Docker oracle — SKIPPED (--no-docker)")
        print(f"{'=' * 60}")
        print("\nSMOKE TEST PASSED (verify + package)")
        _cleanup_temp(output_dir, args.keep_task_dir)
        return

    print(f"\n{'=' * 60}")
    print("[step 3/3] Docker oracle (solve.sh → test.sh)")
    print(f"{'=' * 60}")

    reward = step_docker_oracle(
        task_dir,
        repo_slug=args.repo,
        use_base_image=use_base,
        rebuild_base=args.rebuild_base,
    )
    _cleanup_temp(output_dir, args.keep_task_dir)
    _exit_with_reward(reward)


def _cleanup_temp(output_dir: Path, keep: Optional[Path]) -> None:
    """Remove temp directory if it wasn't explicitly kept."""
    if keep is None and output_dir.exists() and str(output_dir).startswith(tempfile.gettempdir()):
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)


def _exit_with_reward(reward: int) -> None:
    if reward == 1:
        print(f"\n{'=' * 60}")
        print("SMOKE TEST PASSED — reward=1")
        print(f"{'=' * 60}")
    elif reward == 0:
        print(f"\n{'=' * 60}")
        print("SMOKE TEST FAILED — reward=0 (tests did not pass)")
        print(f"{'=' * 60}")
        sys.exit(1)
    else:
        print(f"\n{'=' * 60}")
        print("SMOKE TEST FAILED — Docker build failed")
        print(f"{'=' * 60}")
        sys.exit(2)


if __name__ == "__main__":
    main()