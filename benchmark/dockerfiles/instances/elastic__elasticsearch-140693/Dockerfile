# Instance image for elastic__elasticsearch-140693
# Elasticsearch 9.4.0 @ ad866649260c
# PR #140693: Panama vector implementation of codePointCount
#
# The repo is checked out at the buggy commit (before the fix).
# Git history is cleaned: no future commits, tags, or remote access.

FROM es-bench-base

SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to the buggy version (base_commit, before the fix PR was merged)
RUN git checkout ad866649260c6a9fbf73c2a016cd4b91f687b6e1 && \
    git reset --hard ad866649260c6a9fbf73c2a016cd4b91f687b6e1 && \
    git clean -fdx

# === Git History Cleanup (SWE-bench issue #465) ===
# Prevents agents from cheating by looking at future commits/tags.

# 1. Remove remote origin so no future code can be fetched
# 2. Delete all branches except the current detached HEAD
# 3. Delete future tags (preserve past tags for legitimate use)
# 4. Expire reflog and garbage collect unreachable objects
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TIMESTAMP=$(git show -s --format=%ci ad866649260c6a9fbf73c2a016cd4b91f687b6e1) && \
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
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci ad866649260c6a9fbf73c2a016cd4b91f687b6e1)" \
        --not ad866649260c6a9fbf73c2a016cd4b91f687b6e1 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && \
        git log --oneline --all --after="$(git show -s --format=%ci ad866649260c6a9fbf73c2a016cd4b91f687b6e1)" --not ad866649260c6a9fbf73c2a016cd4b91f687b6e1 && \
        exit 1; \
    fi && \
    echo "Git history cleanup verified: no future commits accessible."

# 6. Verify we are at the correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "ad866649260c6a9fbf73c2a016cd4b91f687b6e1" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected ad866649260c6a9fbf73c2a016cd4b91f687b6e1" && \
        exit 1; \
    fi && \
    echo "Verified: HEAD at ad866649260c6a9fbf73c2a016cd4b91f687b6e1"

WORKDIR /app
ENTRYPOINT ["/bin/bash"]
