#!/usr/bin/env python3
"""
fetch_prs_simple.py — Fetch merged PRs with linked issues for any repository.

Simplified fetcher with no adapter dependency. Filters by excluded directories,
file-change range, and requires both source and test file changes.

Usage:
    python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --until 2025-06-01
    python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --min-files 4 --max-files 8
    python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --exclude-dirs src/ deps/ tools/ benchmark/
    python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --resume
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

MAX_RETRIES = 3
MIN_DELAY = 0.5
RATE_LIMIT_BUFFER = 100
SEARCH_RATE_LIMIT_DELAY = 2.5  # Search API: 30 req/min
GRAPHQL_BATCH_SIZE = 20
SAVE_EVERY_N = 50

DEFAULT_DAYS_BACK = 365
DEFAULT_MIN_FILES = 2
DEFAULT_MAX_FILES = 100

# nodejs/node defaults
DEFAULT_EXCLUDE_DIRS = ["src/", "deps/", "tools/", "benchmark/"]


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)
    return token


import requests


def _handle_rate_limit(resp: requests.Response, *, is_search: bool = False) -> None:
    remaining = int(resp.headers.get("X-RateLimit-Remaining", 1000))
    reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
    buffer = 5 if is_search else RATE_LIMIT_BUFFER

    if remaining <= buffer:
        wait = max(0, reset_time - time.time()) + 5
        if wait > 0:
            print(f"  [Rate limit] {remaining} remaining, waiting {wait:.0f}s...")
            time.sleep(wait)
    else:
        time.sleep(SEARCH_RATE_LIMIT_DELAY if is_search else MIN_DELAY)


def _rest_get(url: str, params: Optional[dict] = None, *, is_search: bool = False) -> requests.Response:
    headers = {
        "Authorization": f"token {_get_token()}",
        "Accept": "application/vnd.github.v3+json",
    }
    for attempt in range(MAX_RETRIES):
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            _handle_rate_limit(resp, is_search=is_search)
            return resp
        if resp.status_code in (403, 429):
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(0, reset_time - time.time()) + 5
            if 0 < wait < 3700:
                print(f"  [Rate limited] Waiting {wait:.0f}s (attempt {attempt + 1})...")
                time.sleep(wait)
                continue
        if resp.status_code >= 500:
            wait = 2 ** attempt * 10
            print(f"  [Server error {resp.status_code}] Retrying in {wait}s...")
            time.sleep(wait)
            continue
        break
    return resp


def _graphql(query: str, variables: dict) -> requests.Response:
    headers = {"Authorization": f"bearer {_get_token()}"}
    for attempt in range(MAX_RETRIES):
        resp = requests.post(
            GRAPHQL_URL, headers=headers,
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
                print(f"  [Rate limited] Waiting {wait:.0f}s (attempt {attempt + 1})...")
                time.sleep(wait)
                continue
        if resp.status_code >= 500:
            wait = 2 ** attempt * 10
            print(f"  [Server error {resp.status_code}] Retrying in {wait}s...")
            time.sleep(wait)
            continue
        break
    return resp


# ── Search ────────────────────────────────────────────────────────────────────

def _month_ranges(since: str, until: str) -> List[Tuple[str, str]]:
    """Split a date range into monthly chunks (reverse chronological)."""
    start = datetime.strptime(since, "%Y-%m-%d")
    end = datetime.strptime(until, "%Y-%m-%d")
    ranges = []
    cursor = start
    while cursor < end:
        chunk_end = cursor.replace(day=28) + timedelta(days=4)
        chunk_end = chunk_end.replace(day=1) - timedelta(days=1)
        if chunk_end > end:
            chunk_end = end
        ranges.append((cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cursor = chunk_end + timedelta(days=1)
    ranges.reverse()
    return ranges


def search_merged_prs(
    owner: str, repo: str, since: str, until: str, *, max_results: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Search for merged PRs with linked issues in the given time window."""
    all_prs: list[dict] = []
    chunks = _month_ranges(since, until)

    print(f"\n[{owner}/{repo}] Searching merged PRs with linked issues ({since} → {until})...")

    for start_date, end_date in chunks:
        page = 1
        while True:
            q = (
                f"repo:{owner}/{repo} is:pr is:merged linked:issue "
                f"merged:{start_date}..{end_date}"
            )
            resp = _rest_get(
                f"{GITHUB_API_BASE}/search/issues",
                params={"q": q, "per_page": 100, "page": page, "sort": "updated", "order": "desc"},
                is_search=True,
            )
            if resp.status_code != 200:
                print(f"  Search error: {resp.status_code} — {resp.text[:200]}")
                break

            data = resp.json()
            items = data.get("items", [])
            total = data.get("total_count", 0)

            if page == 1 and total > 0:
                print(f"  {start_date[:7]}: {total} PRs")

            if not items:
                break

            all_prs.extend(items)

            if len(items) < 100:
                break
            page += 1
            if page > 10:
                print(f"  Warning: Hit 1000 result limit for {start_date[:7]}.")
                break

        if max_results and len(all_prs) >= max_results:
            print(f"  Reached {len(all_prs)} results (limit: {max_results}), stopping search.")
            break

    seen: set[int] = set()
    unique: list[dict] = []
    for pr in all_prs:
        if pr["number"] not in seen:
            seen.add(pr["number"])
            unique.append(pr)

    print(f"  Total unique: {len(unique)} merged PRs with linked issues")
    return unique


# ── Detail fetching ───────────────────────────────────────────────────────────

def fetch_pr_details_batch(
    owner: str, repo: str, pr_numbers: List[int],
) -> Dict[int, Dict[str, Any]]:
    """Batch-fetch PR details and closing issues via GraphQL."""
    if not pr_numbers:
        return {}

    fragments = []
    for i, num in enumerate(pr_numbers):
        fragments.append(f"""
        pr{i}: pullRequest(number: {num}) {{
          number
          title
          body
          mergedAt
          closingIssuesReferences(first: 10) {{
            nodes {{
              number
              title
              body
            }}
          }}
        }}""")

    query = f"""
    query($owner: String!, $repo: String!) {{
      repository(owner: $owner, name: $repo) {{
        {"".join(fragments)}
      }}
    }}
    """
    resp = _graphql(query, {"owner": owner, "repo": repo})
    results: dict[int, dict] = {}

    if resp.status_code != 200:
        print(f"  GraphQL error: {resp.status_code}")
        return results

    data = resp.json()
    if "errors" in data:
        print(f"  GraphQL errors: {[e.get('message', '?') for e in data['errors'][:2]]}")

    repo_data = data.get("data", {}).get("repository", {})
    for i, num in enumerate(pr_numbers):
        node = repo_data.get(f"pr{i}")
        if not node:
            continue
        issues_raw = node.get("closingIssuesReferences", {}).get("nodes", [])
        results[num] = {
            "title": node.get("title", ""),
            "body": node.get("body", ""),
            "merged_at": node.get("mergedAt", ""),
            "issues": [
                {"number": iss.get("number"), "title": iss.get("title", ""), "body": iss.get("body", "")}
                for iss in issues_raw
            ],
        }
    return results


def fetch_pr_files(owner: str, repo: str, pr_number: int) -> List[Dict[str, str]]:
    """Fetch files changed in a PR."""
    all_files: list[dict] = []
    page = 1
    while True:
        resp = _rest_get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files",
            params={"per_page": 100, "page": page},
        )
        if resp.status_code != 200:
            break
        files = resp.json()
        if not files:
            break
        for f in files:
            all_files.append({
                "filename": f["filename"],
                "status": f.get("status", "modified"),
                "patch": f.get("patch", ""),
            })
        if len(files) < 100:
            break
        page += 1
    return all_files


# ── Filtering ─────────────────────────────────────────────────────────────────

def touches_excluded_dir(patches: List[Dict[str, str]], exclude_dirs: List[str]) -> bool:
    """Return True if any file in the PR is under an excluded directory."""
    for p in patches:
        fn = p["filename"]
        for excluded in exclude_dirs:
            if fn.startswith(excluded):
                return True
    return False


def has_test_and_source_files(patches: List[Dict[str, str]], test_dirs: List[str], source_dirs: List[str]) -> bool:
    """Check that the PR touches at least one test file and one source file.

    test_dirs: prefixes that identify test files (e.g. ["test/"])
    source_dirs: prefixes that identify source files (e.g. ["lib/"])
    """
    has_test = False
    has_source = False
    for p in patches:
        fn = p["filename"]
        if not has_test:
            for td in test_dirs:
                if fn.startswith(td):
                    has_test = True
                    break
        if not has_source:
            for sd in source_dirs:
                if fn.startswith(sd):
                    has_source = True
                    break
        if has_test and has_source:
            return True
    return has_test and has_source


# ── Persistence ───────────────────────────────────────────────────────────────

def load_existing(path: Path) -> Tuple[List[Dict], Set[int]]:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            done = {pr["pr_number"] for pr in data}
            return data, done
        except (json.JSONDecodeError, IOError):
            pass
    return [], set()


def save(data: List[Dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def fetch_repo_prs(
    owner: str,
    repo: str,
    since: str,
    until: str,
    output: Path,
    *,
    limit: Optional[int] = None,
    min_files: int = DEFAULT_MIN_FILES,
    max_files: int = DEFAULT_MAX_FILES,
    exclude_dirs: List[str],
    test_dirs: List[str],
    source_dirs: List[str],
    resume: bool = False,
) -> None:
    repo_slug = f"{owner}/{repo}"

    if resume:
        results, already_done = load_existing(output)
        print(f"  Resuming: {len(already_done)} PRs already fetched")
    else:
        results, already_done = [], set()

    search_results = search_merged_prs(owner, repo, since, until, max_results=limit)
    to_fetch = [pr for pr in search_results if pr["number"] not in already_done]
    print(f"  {len(to_fetch)} new PRs to fetch (skipping {len(search_results) - len(to_fetch)} already done)")

    if limit:
        to_fetch = to_fetch[:limit]

    new_count = 0
    skipped = {"no_issues": 0, "excluded_dir": 0, "no_test_source": 0, "file_count": 0}

    for batch_start in range(0, len(to_fetch), GRAPHQL_BATCH_SIZE):
        batch = to_fetch[batch_start : batch_start + GRAPHQL_BATCH_SIZE]
        batch_nums = [pr["number"] for pr in batch]

        print(f"\n  Batch {batch_start // GRAPHQL_BATCH_SIZE + 1} ({len(batch)} PRs)...")

        details_map = fetch_pr_details_batch(owner, repo, batch_nums)

        for pr in batch:
            pr_number = pr["number"]
            details = details_map.get(pr_number)
            if not details:
                continue

            issues = details.get("issues", [])
            if not issues:
                skipped["no_issues"] += 1
                continue

            patches = fetch_pr_files(owner, repo, pr_number)
            files_changed = len(patches)

            if files_changed < min_files or files_changed > max_files:
                skipped["file_count"] += 1
                continue

            if touches_excluded_dir(patches, exclude_dirs):
                skipped["excluded_dir"] += 1
                continue

            if not has_test_and_source_files(patches, test_dirs, source_dirs):
                skipped["no_test_source"] += 1
                continue

            pr_data = {
                "repo": repo_slug,
                "pr_number": pr_number,
                "title": details["title"],
                "description": details.get("body", "") or "",
                "issues": issues,
                "files_changed": files_changed,
                "patches": patches,
                "merged_at": details.get("merged_at", ""),
            }

            results.append(pr_data)
            already_done.add(pr_number)
            new_count += 1
            print(f"    PR #{pr_number}: {files_changed} files, {len(issues)} issue(s) ✓")

        if new_count > 0:
            save(results, output)

    save(results, output)

    print(f"\n{'=' * 60}")
    print(f"DONE — {repo_slug}")
    print(f"  New PRs fetched: {new_count}")
    print(f"  Total in output: {len(results)}")
    print(f"  Skipped: {skipped}")
    print(f"  Output: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch merged PRs with linked issues. No adapter needed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --until 2025-06-01\n"
            "  python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --min-files 4 --max-files 8\n"
            "  python fetch_prs_simple.py --repo nodejs/node --exclude-dirs src/ deps/ tools/ benchmark/\n"
            "  python fetch_prs_simple.py --repo nodejs/node --since 2025-01-01 --resume\n"
        ),
    )
    parser.add_argument("--repo", required=True, help="Repository slug (e.g. nodejs/node)")
    parser.add_argument("--since", type=str, default=None, help="Start date YYYY-MM-DD (default: 365 days ago)")
    parser.add_argument("--until", type=str, default=None, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON file (default: <owner>__<repo>_prs.json)")
    parser.add_argument("--limit", type=int, default=None, help="Max PRs to fetch")
    parser.add_argument("--min-files", type=int, default=DEFAULT_MIN_FILES, help=f"Min files changed (default: {DEFAULT_MIN_FILES})")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help=f"Max files changed (default: {DEFAULT_MAX_FILES})")
    parser.add_argument(
        "--exclude-dirs", nargs="*", default=DEFAULT_EXCLUDE_DIRS,
        help=f"Directory prefixes to exclude (default: {' '.join(DEFAULT_EXCLUDE_DIRS)})",
    )
    parser.add_argument(
        "--test-dirs", nargs="*", default=["test/"],
        help="Directory prefixes that identify test files (default: test/)",
    )
    parser.add_argument(
        "--source-dirs", nargs="*", default=["lib/"],
        help="Directory prefixes that identify source files (default: lib/)",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from previous output file")

    args = parser.parse_args()

    owner, repo = args.repo.split("/")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    since = args.since or (datetime.now(timezone.utc) - timedelta(days=DEFAULT_DAYS_BACK)).strftime("%Y-%m-%d")
    until = args.until or today
    output = args.output or Path(f"{owner}__{repo}_prs.json")

    print("=" * 60)
    print(f"  Fetch PRs: {args.repo}")
    print(f"  Period: {since} → {until}")
    print(f"  Files range: {args.min_files}–{args.max_files}")
    print(f"  Exclude dirs: {args.exclude_dirs}")
    print(f"  Test dirs: {args.test_dirs}")
    print(f"  Source dirs: {args.source_dirs}")
    print(f"  Output: {output}")
    print("=" * 60)

    fetch_repo_prs(
        owner, repo, since, until, output,
        limit=args.limit,
        min_files=args.min_files,
        max_files=args.max_files,
        exclude_dirs=args.exclude_dirs,
        test_dirs=args.test_dirs,
        source_dirs=args.source_dirs,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
