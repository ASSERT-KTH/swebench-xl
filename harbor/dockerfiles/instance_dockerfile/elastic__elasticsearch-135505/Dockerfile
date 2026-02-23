# Instance image for elastic__elasticsearch-135505
# Elasticsearch 9.2.0 @ bc7da67cd9b6
# PR #135505: Address es819 tsdb doc values format performance bug
#
# The repo is checked out at the buggy commit (before the fix).
# Git history is cleaned: no future commits, tags, or remote access.

FROM es-bench-base

SHELL ["/bin/bash", "-c"]
WORKDIR /app

# Reset to the buggy version (base_commit, before the fix PR was merged)
RUN git checkout bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137 && \
    git reset --hard bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137 && \
    git clean -fdx

# === Git History Cleanup (SWE-bench issue #465) ===
# Prevents agents from cheating by looking at future commits/tags.

# 1. Remove remote origin so no future code can be fetched
# 2. Delete all branches except the current detached HEAD
# 3. Delete future tags (preserve past tags for legitimate use)
# 4. Expire reflog and garbage collect unreachable objects
RUN git remote remove origin && \
    git branch -a | grep -v '\*' | grep -v 'HEAD' | xargs -r git branch -D 2>/dev/null || true && \
    BASE_TIMESTAMP=$(git show -s --format=%ci bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137) && \
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
RUN FUTURE_COMMITS=$(git log --oneline --all --after="$(git show -s --format=%ci bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137)" \
        --not bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137 2>/dev/null | wc -l | tr -d ' ') && \
    if [ "$FUTURE_COMMITS" -gt 0 ]; then \
        echo "ERROR: $FUTURE_COMMITS future commits still accessible!" && \
        git log --oneline --all --after="$(git show -s --format=%ci bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137)" --not bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137 && \
        exit 1; \
    fi && \
    echo "Git history cleanup verified: no future commits accessible."

# 6. Verify we are at the correct commit
RUN CURRENT=$(git rev-parse HEAD) && \
    if [ "$CURRENT" != "bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137" ]; then \
        echo "ERROR: HEAD is $CURRENT, expected bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137" && \
        exit 1; \
    fi && \
    echo "Verified: HEAD at bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137"

WORKDIR /app
ENTRYPOINT ["/bin/bash"]
