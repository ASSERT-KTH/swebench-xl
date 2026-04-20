# Auto-generated Dockerfile for huggingface__transformers-44570
FROM swebench-base-huggingface-transformers

SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to base commit (before the fix)
RUN git checkout bc8c80e0288fd369ad06bff5b480d3c51f97a95e && \
    git reset --hard bc8c80e0288fd369ad06bff5b480d3c51f97a95e && \
    git clean -fdx

# Install transformers in editable mode with testing dependencies
RUN pip install -e ".[testing]" 2>&1 | tail -20

# Write rebuild script for dependency metadata changes
RUN echo '#!/bin/bash' > /app/rebuild.sh && \
    echo 'pip install -e .' >> /app/rebuild.sh && \
    chmod +x /app/rebuild.sh

# === Git History Cleanup ===
# Prevents agents from seeing future commits/tags (SWE-bench #465).
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TS=$(git show -s --format=%ct bc8c80e0288fd369ad06bff5b480d3c51f97a95e) && \
    git for-each-ref --format='%(refname:short) %(creatordate:unix)' refs/tags | \
        awk -v cutoff="$BASE_TS" '$2 > cutoff {print $1}' | \
        xargs -r git tag -d > /dev/null 2>&1 || true && \
    git reflog expire --expire=now --all

# Verify no future commits accessible
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci bc8c80e0288fd369ad06bff5b480d3c51f97a95e)" --not bc8c80e0288fd369ad06bff5b480d3c51f97a95e 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && exit 1; \
    fi

# Verify HEAD at correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "bc8c80e0288fd369ad06bff5b480d3c51f97a95e" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected bc8c80e0288fd369ad06bff5b480d3c51f97a95e" && exit 1; \
    fi

RUN find /app -maxdepth 1 -exec chown app:app {} + && \
    find /app -mindepth 1 -maxdepth 1 ! -name .git -exec chown -R app:app {} +

# Verify pytest is available
RUN python -m pytest --version

