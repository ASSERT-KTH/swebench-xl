# Auto-generated Dockerfile for elastic__elasticsearch-143241
FROM swebench-base-elastic-elasticsearch

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace/elasticsearch

# Reset to base commit (before the fix)
RUN git checkout 246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6 && \
    git reset --hard 246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6 && \
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
    BASE_TS=$(git show -s --format=%ct 246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6) && \
    git for-each-ref --format='%(refname:short) %(creatordate:unix)' refs/tags | \
        awk -v cutoff="$BASE_TS" '$2 > cutoff {print $1}' | \
        xargs -r git tag -d > /dev/null 2>&1 || true && \
    git reflog expire --expire=now --all

# Verify no future commits accessible
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci 246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6)" --not 246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && exit 1; \
    fi

# Verify HEAD at correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected 246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6" && exit 1; \
    fi

RUN find /workspace/elasticsearch -maxdepth 1 -exec chown elasticsearch:elasticsearch {} + && \
    find /workspace/elasticsearch -mindepth 1 -maxdepth 1 ! -name .git -exec chown -R elasticsearch:elasticsearch {} +

# Pre-warm Gradle distribution
RUN cd /workspace/elasticsearch && ./gradlew --version --no-daemon || true
