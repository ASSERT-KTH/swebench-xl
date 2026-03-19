"""
Build and manage per-repo base Docker images.

A base image contains the upstream OS image, system packages, language
tooling, and a full git clone of the repository — everything that is
shared across all instances from the same repo.  Instance images then
``FROM`` the base image and only need to checkout a specific commit and
run the history cleanup, which is dramatically faster than cloning from
scratch every time.

Usage from Python::

    from base_image import ensure_base_image
    ensure_base_image("elastic/elasticsearch")  # builds if missing

Usage from the CLI::

    python base_image.py elastic/elasticsearch
    python base_image.py --rebuild elastic/elasticsearch
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure benchmark-pipeline is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import get_adapter
from repo_config import get_config, registered_repos


def build_base_image(repo_slug: str, *, quiet: bool = False) -> bool:
    """
    Build the base Docker image for *repo_slug*.

    Returns True on success, False on build failure.
    """
    cfg = get_config(repo_slug)
    adapter = get_adapter(cfg.adapter_name)
    repo_url = f"https://github.com/{cfg.slug}.git"
    tag = cfg.base_image_tag

    lines = adapter.generate_base_dockerfile_lines(cfg, repo_url)
    dockerfile_content = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory(prefix="swebench-base-") as tmpdir:
        dockerfile_path = Path(tmpdir) / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)

        if not quiet:
            print(f"[base-image] Building {tag} for {repo_slug}...")
            print(f"[base-image] This will clone {repo_url} (may take a few minutes)")

        cmd = ["docker", "build", "-t", tag, "."]
        result = subprocess.run(
            cmd,
            cwd=tmpdir,
            timeout=7200,  # 2 hours max for large repos
        )

        if result.returncode != 0:
            if not quiet:
                print(f"[base-image] Build FAILED (exit {result.returncode})")
            return False

        if not quiet:
            print(f"[base-image] Build OK — {tag}")
        return True


def base_image_exists(repo_slug: str) -> bool:
    """Check if the base image for *repo_slug* already exists locally."""
    cfg = get_config(repo_slug)
    tag = cfg.base_image_tag
    result = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
    )
    return result.returncode == 0


def ensure_base_image(repo_slug: str, *, rebuild: bool = False) -> bool:
    """
    Ensure the base image exists, building it if necessary.

    Returns True if the image is available (already existed or was built
    successfully).  Returns False only if the build fails.
    """
    if not rebuild and base_image_exists(repo_slug):
        cfg = get_config(repo_slug)
        print(f"[base-image] {cfg.base_image_tag} already exists (use --rebuild-base to force)")
        return True
    return build_base_image(repo_slug)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build per-repo base Docker images for the benchmark pipeline.",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        help=f"Repository slug (registered: {', '.join(registered_repos())})",
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Force rebuild even if the image already exists",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Build base images for all registered repos",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the generated Dockerfile without building",
    )
    args = parser.parse_args()

    if args.all:
        slugs = registered_repos()
    elif args.repo:
        slugs = [args.repo]
    else:
        parser.error("Provide a repo slug or --all")

    for slug in slugs:
        if args.dry_run:
            cfg = get_config(slug)
            adapter = get_adapter(cfg.adapter_name)
            repo_url = f"https://github.com/{cfg.slug}.git"
            lines = adapter.generate_base_dockerfile_lines(cfg, repo_url)
            print(f"# ── Base Dockerfile for {slug} ({cfg.base_image_tag}) ──")
            print("\n".join(lines))
            print()
            continue

        ok = ensure_base_image(slug, rebuild=args.rebuild)
        if not ok:
            print(f"FAILED to build base image for {slug}", file=sys.stderr)
            sys.exit(1)

    if not args.dry_run:
        print("\nAll base images ready.")


if __name__ == "__main__":
    main()
