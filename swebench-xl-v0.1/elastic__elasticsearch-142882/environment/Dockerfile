# Auto-generated Dockerfile for elastic__elasticsearch-142882
FROM swebench-base-elastic-elasticsearch

SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to base commit (before the fix)
RUN git checkout df16cba3b96fbf18311dff00d64f184c8a7844d3 && \
    git reset --hard df16cba3b96fbf18311dff00d64f184c8a7844d3 && \
    git clean -fdx

# Cap Gradle JVM heap and parallelism for memory-constrained hosts
RUN echo "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m" >> /app/gradle.properties

# Gradlew wrapper: auto-drops to non-root user when invoked as root
RUN mv /app/gradlew /app/.gradlew-bin
RUN sed -i 's|APP_BASE_NAME=.*|APP_BASE_NAME=gradlew|' /app/.gradlew-bin
RUN cat > /app/gradlew << 'GRADLEW_WRAPPER_EOF'
#!/bin/sh
if [ "$(id -u)" = "0" ]; then
    chown -R elasticsearch:elasticsearch /app 2>/dev/null || true
    exec su -s /bin/bash -c 'exec /app/.gradlew-bin "$@"' -- elasticsearch _ "$@"
fi
exec /app/.gradlew-bin "$@"
GRADLEW_WRAPPER_EOF
RUN chmod +x /app/gradlew

# === Git History Cleanup ===
# Prevents agents from seeing future commits/tags (SWE-bench #465).
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TS=$(git show -s --format=%ct df16cba3b96fbf18311dff00d64f184c8a7844d3) && \
    git for-each-ref --format='%(refname:short) %(creatordate:unix)' refs/tags | \
        awk -v cutoff="$BASE_TS" '$2 > cutoff {print $1}' | \
        xargs -r git tag -d > /dev/null 2>&1 || true && \
    git reflog expire --expire=now --all

# Verify no future commits accessible
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci df16cba3b96fbf18311dff00d64f184c8a7844d3)" --not df16cba3b96fbf18311dff00d64f184c8a7844d3 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && exit 1; \
    fi

# Verify HEAD at correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "df16cba3b96fbf18311dff00d64f184c8a7844d3" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected df16cba3b96fbf18311dff00d64f184c8a7844d3" && exit 1; \
    fi

RUN find /app -maxdepth 1 -exec chown elasticsearch:elasticsearch {} + && \
    find /app -mindepth 1 -maxdepth 1 ! -name .git -exec chown -R elasticsearch:elasticsearch {} +

# Pre-warm Gradle distribution
RUN cd /app && ./gradlew --version --no-daemon || true
