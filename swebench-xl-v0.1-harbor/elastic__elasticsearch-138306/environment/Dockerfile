# Auto-generated Dockerfile for elastic__elasticsearch-138306
FROM eclipse-temurin:21-jdk-jammy

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3 python3-pip curl wget unzip jq \
    && rm -rf /var/lib/apt/lists/*

# Install junitparser for test result parsing inside the container
RUN pip3 install --no-cache-dir junitparser

# Clone repository
RUN mkdir /app && \
    git clone -o origin --single-branch https://github.com/elastic/elasticsearch.git /app

WORKDIR /app
SHELL ["/bin/bash", "-c"]

# Reset to base commit (before the fix)
RUN git checkout e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de && \
    git reset --hard e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de && \
    git clean -fdx

# === Git History Cleanup ===
# Prevents agents from seeing future commits/tags.
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TIMESTAMP=$(git show -s --format=%ci e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de) && \
    git tag -l | while read tag; do \
        TAG_COMMIT=$(git rev-list -n 1 "$tag" 2>/dev/null) || continue; \
        TAG_TIME=$(git show -s --format=%ci "$TAG_COMMIT" 2>/dev/null) || continue; \
        if [[ "$TAG_TIME" > "$BASE_TIMESTAMP" ]]; then \
            git tag -d "$tag" > /dev/null 2>&1; \
        fi; \
    done && \
    git reflog expire --expire=now --all && \
    git gc --prune=now

# Verify no future commits accessible
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de)" --not e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && exit 1; \
    fi

# Verify HEAD at correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de" && exit 1; \
    fi

# ── Harbor additions ──────────────────────────────────────
ENTRYPOINT []
WORKDIR /app
ENV PYTHONPATH=/app/lib:/app
# Cap Gradle JVM heap and parallelism for memory-constrained hosts
# GRADLE_OPTS applies to the wrapper/launcher JVM only.
# org.gradle.jvmargs (via gradle.properties) controls the daemon JVM that
# actually compiles code — this is what needs the extra heap.
ENV GRADLE_OPTS="-Xmx512m"
RUN echo "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m" >> /app/gradle.properties
RUN mkdir -p /logs
RUN mkdir -p /installed-agent

RUN useradd -m -u 1000 elasticsearch 2>/dev/null || true

# Gradlew wrapper: auto-drops to non-root user when invoked as root
RUN useradd -m -u 1001 agent 2>/dev/null || true
RUN chown -R agent:agent /app

RUN mv /app/gradlew /app/.gradlew-bin
RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' /app/.gradlew-bin
RUN cat > /app/gradlew << 'GRADLEW_WRAPPER_EOF'
#!/bin/sh
if [ "$(id -u)" = "0" ]; then
    chown -R agent:agent /app 2>/dev/null || true
    exec su -s /bin/bash -c 'exec /app/.gradlew-bin "$@"' -- agent _ "$@"
fi
exec /app/.gradlew-bin "$@"
GRADLEW_WRAPPER_EOF
RUN chmod +x /app/gradlew
RUN cp /app/gradlew /app/gradlew.real
RUN cp /app/gradlew /app/.gradlew-real

# Agent config
COPY mini-swe-agent-config.yaml /root/mini-swe-agent-config.yaml
ENV MSWEA_MINI_CONFIG_PATH=/root/mini-swe-agent-config.yaml

# Pre-warm Gradle distribution
RUN cd /app && ./gradlew --version --no-daemon || true
