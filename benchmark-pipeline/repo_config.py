"""
Repository configuration registry.

This is the single file to edit when adding a new repository to the
benchmark pipeline.  Each repo gets a ``RepoConfig`` that captures every
repo-specific setting the pipeline needs — Docker images, version
detection, file-classification hints, JDK requirements, etc.

To add a new Java + Gradle repo:
    1. Call ``register_repo(RepoConfig(...))`` at the bottom of this file.
    2. That's it — the rest of the pipeline reads from get_config().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class RepoConfig:
    """All settings that vary between repositories."""

    # ── Identity ──────────────────────────────────────────────────────
    slug: str  # e.g. "elastic/elasticsearch"

    # ── Adapter ───────────────────────────────────────────────────────
    adapter_name: str = "java-gradle"

    # ── Docker / environment ──────────────────────────────────────────
    base_image: str = "eclipse-temurin:21-jdk-jammy"
    system_packages: str = "git python3 python3-pip curl wget unzip jq patch"

    # ── Non-root user (for running tests) ─────────────────────────────
    no_root_user: str = "app"

    # ── Version detection ─────────────────────────────────────────────
    version_files: List[str] = field(default_factory=lambda: [
        "gradle.properties",
    ])
    version_key: str = "version"

    # ── Clone directory ───────────────────────────────────────────────
    clone_dir_env_var: str = ""
    default_clone_dir: str = ""

    # ── File classification ───────────────────────────────────────────
    test_config_files: Set[str] = field(default_factory=set)
    extra_test_path_segments: List[str] = field(default_factory=list)

    # ── Dockerfile extras ─────────────────────────────────────────────
    dockerfile_extra_lines: List[str] = field(default_factory=list)

    # ── Noise repos (cloned alongside the main repo) ─────────────────
    noise_repos: List[str] = field(default_factory=list)

    # ── Arbitrary extras (forward-compatible) ─────────────────────────
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.default_clone_dir:
            safe = self.slug.replace("/", "-")
            self.default_clone_dir = f"/tmp/{safe}-pipeline"

    @property
    def repo_dir(self) -> str:
        """Container path to the main repository.

        When noise repos are configured the main repo lives under
        ``/workspace/<repo-short-name>`` so that sibling noise repos
        can sit alongside it.  Otherwise falls back to ``/app``.
        """
        if self.noise_repos:
            return f"/workspace/{self.slug.split('/')[-1]}"
        return "/app"

    @property
    def docker_workdir(self) -> str:
        """WORKDIR for the Docker image.

        ``/workspace`` when noise repos are present (so the agent sees
        all repos), ``/app`` otherwise.
        """
        if self.noise_repos:
            return "/workspace"
        return "/app"

    @property
    def base_image_tag(self) -> str:
        """Docker tag for the per-repo base image (e.g. ``swebench-base-elastic-elasticsearch``)."""
        return f"swebench-base-{self.slug.replace('/', '-')}".lower()

    def get_clone_dir(self) -> str:
        """Resolve clone directory from env var or default."""
        import os

        if self.clone_dir_env_var:
            return os.environ.get(self.clone_dir_env_var, self.default_clone_dir)
        return self.default_clone_dir


# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, RepoConfig] = {}


def register_repo(config: RepoConfig) -> None:
    """Register a RepoConfig so the pipeline can look it up by slug."""
    _REGISTRY[config.slug] = config


def get_config(slug: str) -> RepoConfig:
    """
    Return the RepoConfig for *slug*.

    Raises ValueError with a helpful message if the slug isn't registered.
    """
    if slug in _REGISTRY:
        return _REGISTRY[slug]
    registered = ", ".join(sorted(_REGISTRY)) or "(none)"
    raise ValueError(
        f"Unknown repository: {slug!r}. "
        f"Register it in repo_config.py.  Currently registered: {registered}"
    )


def registered_repos() -> List[str]:
    """Return the list of registered repo slugs."""
    return sorted(_REGISTRY)


# ── Built-in configurations ──────────────────────────────────────────────────

register_repo(RepoConfig(
    slug="elastic/elasticsearch",
    base_image="eclipse-temurin:21-jdk-jammy",
    no_root_user="elasticsearch",
    version_files=["build-tools-internal/version.properties"],
    version_key="elasticsearch",
    clone_dir_env_var="ES_CLONE_DIR",
    default_clone_dir="/tmp/elasticsearch-pipeline",
    test_config_files={"muted-tests.yml", "muted-tests.yaml"},
    extra_test_path_segments=["/compute/test/"],
    noise_repos=[
        "elastic/kibana",
        "elastic/logstash",
        "elastic/beats",
        "elastic/apm-server",
        "elastic/elasticsearch-py",
        "elastic/go-elasticsearch",
        "elastic/elasticsearch-js",
        "elastic/elastic-agent",
        "elastic/elasticsearch-specification",
    ],
    extra={
        "min_jdk_version": 21,
        "gradle_flags": [
            "--no-daemon", "--stacktrace", "-x", "javadoc",
            "--no-configuration-cache", "--max-workers=2",
        ],
    },
))

register_repo(RepoConfig(
    slug="elastic/kibana",
    adapter_name="kibana",
    base_image="node:20-bookworm",
    system_packages="git python3 python3-pip curl wget unzip jq patch",
    no_root_user="node",
    version_files=["package.json"],
    version_key="version",
    clone_dir_env_var="KIBANA_CLONE_DIR",
    default_clone_dir="/tmp/kibana-pipeline",
    test_config_files={"jest.config.js", "jest.config.ts", "jest.integration.config.js"},
    extra_test_path_segments=["/__tests__/", "/__mocks__/", "/test_helpers/"],
    extra={
        "jest_flags": ["--ci", "--no-cache", "--forceExit"],
    },
))

register_repo(RepoConfig(
    slug="spring-projects/spring-framework",
    base_image="eclipse-temurin:21-jdk-jammy",
    no_root_user="spring",
    version_files=["gradle.properties"],
    version_key="version",
    clone_dir_env_var="SPRING_CLONE_DIR",
    default_clone_dir="/tmp/spring-framework-pipeline",
    test_config_files=set(),
    extra_test_path_segments=["/testFixtures/"],
    extra={
        "min_jdk_version": 17,
        "gradle_flags": [
            "--no-daemon", "--stacktrace", "--max-workers=2",
        ],
    },
))

register_repo(RepoConfig(
    slug="BabylonJS/Babylon.js",
    adapter_name="babylon",
    base_image="node:20-bookworm",
    system_packages="git python3 python3-pip curl wget unzip jq patch",
    no_root_user="node",
    version_files=["packages/public/umd/babylonjs/package.json"],
    version_key="version",
    clone_dir_env_var="BABYLONJS_CLONE_DIR",
    default_clone_dir="/tmp/babylonjs-pipeline",
    test_config_files={"jest.config.ts", "jest.config.js", "tsconfig.test.json"},
    extra_test_path_segments=["/test/unit/", "/__tests__/"],
    extra={
        "jest_flags": ["--ci", "--no-cache", "--forceExit"],
        "npm_memory_limit": 8192,
    },
))
