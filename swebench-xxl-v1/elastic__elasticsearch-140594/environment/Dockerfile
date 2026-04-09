# Auto-generated Dockerfile for elastic__elasticsearch-140594
FROM swebench-base-elastic-elasticsearch

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace/elasticsearch

# Reset to base commit (before the fix)
RUN git checkout e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a && \
    git reset --hard e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a && \
    git clean -fdx

# Cap Gradle JVM heap and parallelism for memory-constrained hosts
RUN echo "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m" >> /workspace/elasticsearch/gradle.properties

# Gradlew wrapper: auto-drops to non-root user when invoked as root
RUN mv /workspace/elasticsearch/gradlew /workspace/elasticsearch/.gradlew-bin
RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' /workspace/elasticsearch/.gradlew-bin
RUN cat > /workspace/elasticsearch/gradlew << 'GRADLEW_WRAPPER_EOF'
#!/bin/sh
if [ "$(id -u)" = "0" ]; then
    chown -R elasticsearch:elasticsearch /workspace/elasticsearch 2>/dev/null || true
    exec su -s /bin/bash -c 'exec /workspace/elasticsearch/.gradlew-bin "$@"' -- elasticsearch _ "$@"
fi
exec /workspace/elasticsearch/.gradlew-bin "$@"
GRADLEW_WRAPPER_EOF
RUN chmod +x /workspace/elasticsearch/gradlew

# === Git History Cleanup ===
# Prevents agents from seeing future commits/tags (SWE-bench #465).
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TS=$(git show -s --format=%ct e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a) && \
    git for-each-ref --format='%(refname:short) %(creatordate:unix)' refs/tags | \
        awk -v cutoff="$BASE_TS" '$2 > cutoff {print $1}' | \
        xargs -r git tag -d > /dev/null 2>&1 || true && \
    git reflog expire --expire=now --all

# Verify no future commits accessible
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a)" --not e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && exit 1; \
    fi

# Verify HEAD at correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a" && exit 1; \
    fi

RUN find /workspace/elasticsearch -maxdepth 1 -exec chown elasticsearch:elasticsearch {} + && \
    find /workspace/elasticsearch -mindepth 1 -maxdepth 1 ! -name .git -exec chown -R elasticsearch:elasticsearch {} +

# Pre-warm Gradle distribution
RUN cd /workspace/elasticsearch && ./gradlew --version --no-daemon || true
