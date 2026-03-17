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
    # Name of the LanguageAdapter to use (registered in adapters/__init__.py).
    # See ``adapters/base.py`` for the interface and ``adapters/java_gradle.py``
    # for the reference implementation.
    adapter_name: str = "java-gradle"

    # ── Docker / environment ──────────────────────────────────────────
    base_image: str = "eclipse-temurin:21-jdk-jammy"
    system_packages: str = "git python3 python3-pip curl wget unzip jq patch"

    # ── Build tool ────────────────────────────────────────────────────
    build_tool: str = "gradle"  # only "gradle" supported today
    gradle_flags: List[str] = field(default_factory=lambda: [
        "--no-daemon", "--stacktrace", "-x", "javadoc",
        "--no-configuration-cache", "--max-workers=2",
    ])
    gradle_env_overrides: Dict[str, str] = field(
        default_factory=lambda: {"GRADLE_OPTS": "-Xmx2g"},
    )

    # ── Non-root user (for gradlew wrapper) ───────────────────────────
    no_root_user: str = "app"

    # ── Version detection ─────────────────────────────────────────────
    # Paths (relative to repo root) to look for a version properties file.
    version_files: List[str] = field(default_factory=lambda: [
        "gradle.properties",
    ])
    # Key to match at the start of a line, e.g. "version" matches
    # ``version=1.2.3``.  Set to "" to skip version extraction.
    version_key: str = "version"

    # ── JDK ───────────────────────────────────────────────────────────
    java_version_file: str = ".java-version"
    min_jdk_version: int = 17

    # ── Clone directory ───────────────────────────────────────────────
    clone_dir_env_var: str = ""  # env var override, e.g. "ES_CLONE_DIR"
    default_clone_dir: str = ""  # computed from slug if empty

    # ── File classification ───────────────────────────────────────────
    # Filenames that control test execution (shipped with the test patch).
    test_config_files: Set[str] = field(default_factory=set)
    # Extra path segments that mark a file as a test (beyond the standard
    # ``/src/test/java/`` convention).  E.g. ``["/compute/test/"]``.
    extra_test_path_segments: List[str] = field(default_factory=list)

    # ── Dockerfile extras ─────────────────────────────────────────────
    # Extra RUN lines injected after the clone in the Dockerfile.
    dockerfile_extra_lines: List[str] = field(default_factory=list)

    # ── Arbitrary extras (forward-compatible) ─────────────────────────
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.default_clone_dir:
            safe = self.slug.replace("/", "-")
            self.default_clone_dir = f"/tmp/{safe}-pipeline"

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
    version_files=[
        "build-tools-internal/version.properties",
    ],
    version_key="elasticsearch",
    min_jdk_version=21,
    clone_dir_env_var="ES_CLONE_DIR",
    default_clone_dir="/tmp/elasticsearch-pipeline",
    test_config_files={"muted-tests.yml", "muted-tests.yaml"},
    extra_test_path_segments=["/compute/test/"],
    gradle_flags=[
        "--no-daemon", "--stacktrace", "-x", "javadoc",
        "--no-configuration-cache", "--max-workers=2",
    ],
))

register_repo(RepoConfig(
    slug="spring-projects/spring-framework",
    # JDK 21 — the Gradle wrapper in Spring 6.1.x/6.2.x does NOT support
    # JDK 25 (class file major version 69).  JDK 21 is the latest LTS
    # supported by all Gradle 8.x wrappers shipped with Spring 6.x.
    base_image="eclipse-temurin:21-jdk-jammy",
    no_root_user="spring",
    version_files=["gradle.properties"],
    version_key="version",
    min_jdk_version=17,
    clone_dir_env_var="SPRING_CLONE_DIR",
    default_clone_dir="/tmp/spring-framework-pipeline",
    test_config_files=set(),
    extra_test_path_segments=["/testFixtures/"],
    gradle_flags=[
        "--no-daemon", "--stacktrace", "--max-workers=2",
    ],
))

register_repo(RepoConfig(
    slug="gradle/gradle",
    base_image="eclipse-temurin:21-jdk-jammy",
    no_root_user="gradle",
    # Version lives in version.txt as a bare string, not a key=value pair.
    version_files=["version.txt"],
    version_key="",
    min_jdk_version=21,
    clone_dir_env_var="GRADLE_CLONE_DIR",
    default_clone_dir="/tmp/gradle-pipeline",
    test_config_files=set(),
    extra_test_path_segments=["/testing/", "/integTest/"],
    gradle_flags=[
        "--no-daemon", "--stacktrace", "--max-workers=2",
        "-Dorg.gradle.dependency.verification=lenient",
    ],
    gradle_env_overrides={"GRADLE_OPTS": "-Xmx4g"},
))

register_repo(RepoConfig(
    slug="libgdx/libgdx",
    base_image="eclipse-temurin:17-jdk-jammy",
    no_root_user="libgdx",
    version_files=["gradle.properties"],
    version_key="version",
    min_jdk_version=11,
    clone_dir_env_var="LIBGDX_CLONE_DIR",
    default_clone_dir="/tmp/libgdx-pipeline",
    test_config_files=set(),
    extra_test_path_segments=["/tests/"],
    gradle_flags=[
        "--no-daemon", "--stacktrace", "--max-workers=2",
    ],
    gradle_env_overrides={"GRADLE_OPTS": "-Xmx2g"},
))

register_repo(RepoConfig(
    slug="signalapp/Signal-Android",
    base_image="eclipse-temurin:17-jdk-jammy",
    system_packages="git python3 python3-pip curl wget unzip jq patch android-sdk",
    no_root_user="signal",
    version_files=["gradle.properties"],
    version_key="",
    min_jdk_version=17,
    clone_dir_env_var="SIGNAL_CLONE_DIR",
    default_clone_dir="/tmp/signal-android-pipeline",
    test_config_files=set(),
    extra_test_path_segments=["/testFixtures/"],
    gradle_flags=[
        "--no-daemon", "--stacktrace", "--max-workers=2",
    ],
    gradle_env_overrides={"GRADLE_OPTS": "-Xmx4g"},
))

# ──────────────────────────────────────────────────────────────────────────────
# To add a new repo, copy a block above and adjust.  Example:
#
# register_repo(RepoConfig(
#     slug="apache/kafka",
#     base_image="eclipse-temurin:17-jdk-jammy",
#     no_root_user="kafka",
#     version_files=["gradle.properties"],
#     version_key="version",
#     min_jdk_version=17,
#     clone_dir_env_var="KAFKA_CLONE_DIR",
#     test_config_files=set(),
#     extra_test_path_segments=[],
# ))
# ──────────────────────────────────────────────────────────────────────────────
