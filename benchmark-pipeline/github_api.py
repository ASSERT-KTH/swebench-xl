"""
GitHub API utilities for fetching commit SHAs via GraphQL.

Batch-fetches merge commit and parent (base) commit SHAs for pull requests.
"""

import os
import time
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

MAX_RETRIES = 3
MIN_DELAY = 0.5
RATE_LIMIT_BUFFER = 100
GRAPHQL_BATCH_SIZE = 20


def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN environment variable is required")
    return token


def _handle_rate_limit(response: requests.Response) -> None:
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1000))
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
    if remaining <= RATE_LIMIT_BUFFER:
        wait = max(0, reset_time - time.time()) + 5
        if wait > 0:
            print(f"  [Rate limit] {remaining} remaining, waiting {wait:.0f}s...")
            time.sleep(wait)
    else:
        time.sleep(MIN_DELAY)


def _graphql_request(query: str, variables: dict) -> requests.Response:
    headers = {"Authorization": f"bearer {_get_token()}"}
    for attempt in range(MAX_RETRIES):
        resp = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        if resp.status_code == 200:
            _handle_rate_limit(resp)
            return resp
        if resp.status_code in (403, 429):
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(0, reset_time - time.time()) + 5
            if 0 < wait < 3700:
                print(f"  [Rate limited] Waiting {wait:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
        if resp.status_code >= 500:
            wait = 2 ** attempt * 10
            print(f"  [Server error {resp.status_code}] Retrying in {wait}s...")
            time.sleep(wait)
            continue
        break
    return resp


def fetch_commit_shas(
    owner: str, repo: str, pr_numbers: List[int]
) -> Dict[int, Dict[str, str]]:
    """
    Batch-fetch merge commit + parent commit SHAs for a list of PR numbers.

    Returns: {pr_number: {"merge_commit": str, "base_commit": str}}
    """
    results: Dict[int, Dict[str, str]] = {}

    for batch_start in range(0, len(pr_numbers), GRAPHQL_BATCH_SIZE):
        batch = pr_numbers[batch_start : batch_start + GRAPHQL_BATCH_SIZE]

        pr_queries = []
        for i, pr_num in enumerate(batch):
            pr_queries.append(
                f"""
                pr{i}: pullRequest(number: {pr_num}) {{
                  number
                  mergeCommit {{
                    oid
                    parents(first: 1) {{
                      nodes {{ oid }}
                    }}
                  }}
                }}"""
            )

        query = f"""
        query($owner: String!, $repo: String!) {{
          repository(owner: $owner, name: $repo) {{
            {"".join(pr_queries)}
          }}
        }}
        """

        resp = _graphql_request(query, {"owner": owner, "repo": repo})
        if resp.status_code != 200:
            print(f"  Error fetching SHAs: {resp.status_code}")
            continue

        data = resp.json()
        if "errors" in data:
            print(f"  GraphQL errors: {data['errors'][:2]}")

        repo_data = data.get("data", {}).get("repository", {})
        for i, pr_num in enumerate(batch):
            pr_node = repo_data.get(f"pr{i}")
            if not pr_node or not pr_node.get("mergeCommit"):
                continue
            merge_commit = pr_node["mergeCommit"]["oid"]
            parents = pr_node["mergeCommit"].get("parents", {}).get("nodes", [])
            base_commit = parents[0]["oid"] if parents else None
            if merge_commit and base_commit:
                results[pr_num] = {
                    "merge_commit": merge_commit,
                    "base_commit": base_commit,
                }

        print(
            f"  Fetched SHAs batch {batch_start // GRAPHQL_BATCH_SIZE + 1} "
            f"({len(batch)} PRs, {len(results)} total resolved)"
        )

    return results
