# Base image for Elasticsearch benchmark instances
# Contains: JDK 21, Gradle, system deps, elasticsearch repo (single-branch clone)

FROM eclipse-temurin:21-jdk-jammy

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    curl \
    wget \
    unzip \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Clone elasticsearch with --single-branch to limit initial history exposure
RUN mkdir /app && \
    git clone -o origin --single-branch https://github.com/elastic/elasticsearch.git /app

WORKDIR /app

ENTRYPOINT ["/bin/bash"]

# ── Instance-specific setup ──────────────────────────────────
# Instance image for elastic__elasticsearch-134501
# Elasticsearch 9.2.0 @ 47acb9a03aab
# PR #134501: Increasing default limit for TS queries
#
# The repo is checked out at the buggy commit (before the fix).
# Git history is cleaned: no future commits, tags, or remote access.


SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to the buggy version (base_commit, before the fix PR was merged)
RUN git checkout 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5 && \
    git reset --hard 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5 && \
    git clean -fdx

# === Git History Cleanup (SWE-bench issue #465) ===
# Prevents agents from cheating by looking at future commits/tags.

# 1. Remove remote origin so no future code can be fetched
# 2. Delete all branches except the current detached HEAD
# 3. Delete future tags (preserve past tags for legitimate use)
# 4. Expire reflog and garbage collect unreachable objects
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TIMESTAMP=$(git show -s --format=%ci 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5) && \
    git tag -l | while read tag; do \
        TAG_COMMIT=$(git rev-list -n 1 "$tag" 2>/dev/null) || continue; \
        TAG_TIME=$(git show -s --format=%ci "$TAG_COMMIT" 2>/dev/null) || continue; \
        if [[ "$TAG_TIME" > "$BASE_TIMESTAMP" ]]; then \
            git tag -d "$tag" > /dev/null 2>&1; \
        fi; \
    done && \
    git reflog expire --expire=now --all && \
    git gc --prune=now

# 5. Verify no future commits are accessible (exclude base_commit itself)
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5)" \
        --not 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && \
        git log --oneline --all --after="$(git show -s --format=%ci 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5)" --not 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5 && \
        exit 1; \
    fi && \
    echo "Git history cleanup verified: no future commits accessible."

# 6. Verify we are at the correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5" && \
        exit 1; \
    fi && \
    echo "Verified: HEAD at 47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5"

WORKDIR /app
ENTRYPOINT ["/bin/bash"]

# ── Harbor additions ──────────────────────────────────────
# Reset entrypoint so docker-compose can run (sleep infinity)
ENTRYPOINT []

WORKDIR /app

# Patches applied by the agent are loaded from /app/lib first
ENV PYTHONPATH=/app/lib:/app

RUN mkdir -p /logs

# /installed-agent is where Harbor copies the agent's install.sh before startup
RUN mkdir -p /installed-agent

# Elasticsearch refuses to run as root — create a dedicated user.
# The container stays as root so Harbor can install agents via apt-get;
# run_script.sh drops to this user with 'su elasticsearch' before invoking Gradle.
RUN useradd -m -u 1000 elasticsearch 2>/dev/null || true
RUN chown -R elasticsearch:elasticsearch /app
