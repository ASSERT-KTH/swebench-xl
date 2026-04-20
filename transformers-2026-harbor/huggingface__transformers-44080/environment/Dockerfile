# Auto-generated Dockerfile for huggingface__transformers-44080
FROM swebench-base-huggingface-transformers

SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to base commit (before the fix)
RUN git checkout e0b07d1b120fdc374b9a563f7edf0305401216be && \
    git reset --hard e0b07d1b120fdc374b9a563f7edf0305401216be && \
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
    BASE_TS=$(git show -s --format=%ct e0b07d1b120fdc374b9a563f7edf0305401216be) && \
    git for-each-ref --format='%(refname:short) %(creatordate:unix)' refs/tags | \
        awk -v cutoff="$BASE_TS" '$2 > cutoff {print $1}' | \
        xargs -r git tag -d > /dev/null 2>&1 || true && \
    git reflog expire --expire=now --all

# Verify no future commits accessible
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci e0b07d1b120fdc374b9a563f7edf0305401216be)" --not e0b07d1b120fdc374b9a563f7edf0305401216be 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && exit 1; \
    fi

# Verify HEAD at correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "e0b07d1b120fdc374b9a563f7edf0305401216be" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected e0b07d1b120fdc374b9a563f7edf0305401216be" && exit 1; \
    fi

RUN find /app -maxdepth 1 -exec chown app:app {} + && \
    find /app -mindepth 1 -maxdepth 1 ! -name .git -exec chown -R app:app {} +

# Verify pytest is available
RUN python -m pytest --version

