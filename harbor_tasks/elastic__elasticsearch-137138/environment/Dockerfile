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
# Instance image for elastic__elasticsearch-137138
# Elasticsearch 9.3.0 @ ac0bc487771a
# PR #137138: Fix mutateInstance() imlementations in inference module
#
# The repo is checked out at the buggy commit (before the fix).
# Git history is cleaned: no future commits, tags, or remote access.


SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to the buggy version (base_commit, before the fix PR was merged)
RUN git checkout ac0bc487771aa0405dbd50dcbae3b0803b7fac84 && \
    git reset --hard ac0bc487771aa0405dbd50dcbae3b0803b7fac84 && \
    git clean -fdx

# === Git History Cleanup (SWE-bench issue #465) ===
# Prevents agents from cheating by looking at future commits/tags.

# 1. Remove remote origin so no future code can be fetched
# 2. Delete all branches except the current detached HEAD
# 3. Delete future tags (preserve past tags for legitimate use)
# 4. Expire reflog and garbage collect unreachable objects
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TIMESTAMP=$(git show -s --format=%ci ac0bc487771aa0405dbd50dcbae3b0803b7fac84) && \
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
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci ac0bc487771aa0405dbd50dcbae3b0803b7fac84)" \
        --not ac0bc487771aa0405dbd50dcbae3b0803b7fac84 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && \
        git log --oneline --all --after="$(git show -s --format=%ci ac0bc487771aa0405dbd50dcbae3b0803b7fac84)" --not ac0bc487771aa0405dbd50dcbae3b0803b7fac84 && \
        exit 1; \
    fi && \
    echo "Git history cleanup verified: no future commits accessible."

# 6. Verify we are at the correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "ac0bc487771aa0405dbd50dcbae3b0803b7fac84" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected ac0bc487771aa0405dbd50dcbae3b0803b7fac84" && \
        exit 1; \
    fi && \
    echo "Verified: HEAD at ac0bc487771aa0405dbd50dcbae3b0803b7fac84"

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

# Pre-warm the Gradle distribution so the agent doesn't time out downloading it.
# Run as root (same user the agent uses), so the cache lands in /root/.gradle.
# The 'refuses to run as root' restriction only applies to starting an ES server,
# not to Gradle compilation or unit test runs.
RUN cd /app && ./gradlew --version --no-daemon || true

# Write a mini-swe-agent config that:
#   1. Restores the system_template from mini.yaml (lost when MSWEA_MINI_CONFIG_PATH
#      fully replaces mini.yaml instead of merging with it).
#   2. Raises per-command timeout to 600s (default 30s is too short for Gradle).
#   3. Sets step_limit to 250.
#   4. Fixes the format_error_template to explicitly require ```bash blocks.
RUN cat > /root/mini-swe-agent-config.yaml << 'MSWEA_CONFIG_EOF'
env:
  timeout: 600
agent:
  step_limit: 250
  system_template: |
    You are a helpful assistant that can interact with a computer.

    Your response must contain exactly ONE bash code block with ONE command (or
    commands connected with && or ||).
    Include a THOUGHT section before your command where you explain your reasoning
    process.
    Format your response as shown in <format_example>.

    <format_example>
    Your reasoning and analysis here. Explain why you want to perform the action.

    ```bash
    your_command_here
    ```
    </format_example>

    Failure to follow these rules will cause your response to be rejected.
  format_error_template: |
    Please always provide EXACTLY ONE action in triple backticks, found {{actions|length}} actions.
    If you want to end the task, please issue the following command: `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`
    without any other command.
    Else, please format your response exactly as follows:

    <response_example>
    Here are some thoughts about why you want to perform the action.

    ```bash
    <action>
    ```
    </response_example>

    Note: In rare cases, if you need to reference a similar format in your command,
    you might have to proceed in two steps, first writing TRIPLEBACKTICKSBASH, then replacing them with ```bash.
MSWEA_CONFIG_EOF
ENV MSWEA_MINI_CONFIG_PATH=/root/mini-swe-agent-config.yaml
