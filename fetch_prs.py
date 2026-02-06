"""
GitHub PR Fetcher
Fetches merged PRs that close issues and saves the raw data to JSON.
"""

import os
import requests
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

# Repositories to analyze
REPOSITORIES = [
    "openjdk/jdk",
    "arangodb/arangodb",
    "nodejs/node",
    "BabylonJS/Babylon.js",
    "elastic/elasticsearch"
]

# API Configuration
GITHUB_API_BASE = "https://api.github.com"

# Rate limiting
MIN_DELAY_BETWEEN_REQUESTS = 0.5  # seconds
RATE_LIMIT_BUFFER = 100  # Start slowing down when this many requests remain
MAX_RETRIES = 3

# Time range (set to None for no cutoff - fetch all PRs)
YEARS_TO_FETCH = None
CUTOFF_DATE = datetime.now() - timedelta(days=YEARS_TO_FETCH * 365) if YEARS_TO_FETCH else None

# Output
OUTPUT_FILE = "pr_data_overnight.json"
SAVE_EVERY_N_PRS = 50  # Save to disk after every N PRs

# ============================================================================
# GITHUB API FUNCTIONS
# ============================================================================

def get_github_headers():
    """Returns headers for GitHub API requests."""
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

def handle_rate_limit(response):
    """Check rate limit headers and wait if necessary."""
    remaining = int(response.headers.get('X-RateLimit-Remaining', 1000))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    if remaining <= RATE_LIMIT_BUFFER:
        wait_time = max(0, reset_time - time.time()) + 5  # Add 5s buffer
        if wait_time > 0:
            print(f"\n  [Rate limit] {remaining} requests remaining. Waiting {wait_time:.0f}s until reset...")
            time.sleep(wait_time)
    else:
        time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

def github_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a GitHub API request with rate limit handling and retries."""
    headers = kwargs.pop('headers', get_github_headers())

    for attempt in range(MAX_RETRIES):
        response = requests.request(method, url, headers=headers, **kwargs)

        # Success
        if response.status_code == 200:
            handle_rate_limit(response)
            return response

        # Rate limited
        if response.status_code in (403, 429):
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_time = max(0, reset_time - time.time()) + 5

            if wait_time > 0 and wait_time < 3700:  # Don't wait more than ~1 hour
                print(f"\n  [Rate limited] Waiting {wait_time:.0f}s until reset (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait_time)
                continue
            else:
                print(f"\n  [Rate limited] Reset time too far away ({wait_time:.0f}s). Retrying in 60s...")
                time.sleep(60)
                continue

        # Other errors - retry with backoff
        if response.status_code >= 500:
            wait = 2 ** attempt * 10  # 10s, 20s, 40s
            print(f"\n  [Server error {response.status_code}] Retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue

        # Client error - don't retry
        break

    return response

def github_graphql(query: str, variables: dict) -> requests.Response:
    """Make a GitHub GraphQL request with rate limit handling and retries."""
    headers = {"Authorization": f"bearer {GITHUB_TOKEN}"}

    for attempt in range(MAX_RETRIES):
        response = requests.post(
            "https://api.github.com/graphql",
            headers=headers,
            json={"query": query, "variables": variables}
        )

        if response.status_code == 200:
            handle_rate_limit(response)
            return response

        if response.status_code in (403, 429):
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            wait_time = max(0, reset_time - time.time()) + 5

            if wait_time > 0 and wait_time < 3700:
                print(f"\n  [GraphQL rate limited] Waiting {wait_time:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait_time)
                continue

        if response.status_code >= 500:
            wait = 2 ** attempt * 10
            print(f"\n  [GraphQL error {response.status_code}] Retrying in {wait}s...")
            time.sleep(wait)
            continue

        break

    return response

def get_merged_prs(owner: str, repo: str) -> List[Dict]:
    """
    Fetches merged pull requests. If CUTOFF_DATE is set, only fetches PRs after that date.
    If CUTOFF_DATE is None, fetches all available PRs.
    """
    prs = []
    page = 1
    per_page = 100
    reached_cutoff = False

    if CUTOFF_DATE:
        print(f"\n[{owner}/{repo}] Fetching merged PRs from last {YEARS_TO_FETCH} years...")
        print(f"  Cutoff date: {CUTOFF_DATE.strftime('%Y-%m-%d')}")
    else:
        print(f"\n[{owner}/{repo}] Fetching all merged PRs (no cutoff)...")

    while not reached_cutoff:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'closed',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': per_page,
            'page': page
        }

        response = github_request('GET', url, params=params)

        if response.status_code != 200:
            print(f"Error fetching PRs: {response.status_code}")
            break

        page_prs = response.json()

        if not page_prs:
            break

        # Filter for merged PRs within date range
        for pr in page_prs:
            if pr.get('merged_at') is None:
                continue

            # Check cutoff if set
            if CUTOFF_DATE:
                merged_at = datetime.fromisoformat(pr['merged_at'].replace('Z', '+00:00'))
                merged_at = merged_at.replace(tzinfo=None)  # Make naive for comparison

                if merged_at < CUTOFF_DATE:
                    reached_cutoff = True
                    break

            prs.append(pr)

        print(f"  Fetched page {page}, total merged PRs: {len(prs)}")

        page += 1

        if len(page_prs) < per_page:
            break

    return prs

def get_closing_issues(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """
    Fetches issues that are closed by a PR using GitHub's GraphQL API.
    """
    query = """
    query($owner: String!, $repo: String!, $pr: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          closingIssuesReferences(first: 10) {
            nodes {
              number
              title
              body
            }
          }
        }
      }
    }
    """

    response = github_graphql(query, {"owner": owner, "repo": repo, "pr": pr_number})

    if response.status_code == 200:
        data = response.json()
        pr_data = data.get("data", {}).get("repository", {}).get("pullRequest")
        if pr_data:
            return pr_data.get("closingIssuesReferences", {}).get("nodes", [])
    return []

def get_pr_files(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """Fetches the list of files changed in a PR."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"

    response = github_request('GET', url)

    if response.status_code == 200:
        return response.json()
    return []

def get_pr_commits(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """Fetches commits in a PR."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/commits"

    response = github_request('GET', url)

    if response.status_code == 200:
        return response.json()
    return []

# ============================================================================
# DATA PERSISTENCE
# ============================================================================

def load_existing_data() -> List[Dict]:
    """Load existing PR data from file if it exists."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"Loaded {len(data)} existing PRs from {OUTPUT_FILE}")
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load existing data: {e}")
    return []

def save_data(data: List[Dict]):
    """Save PR data to file."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_fetched_prs(data: List[Dict]) -> set:
    """Get set of already fetched PR identifiers (repo, pr_number)."""
    return {(pr['repo'], pr['pr_number']) for pr in data}

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def fetch_repository_data(owner: str, repo: str, all_results: List[Dict], fetched_prs: set) -> int:
    """
    Fetches PR data from a repository, skipping already fetched PRs.
    Saves incrementally to disk.
    Returns the number of new PRs fetched.
    """
    repo_name = f"{owner}/{repo}"
    new_count = 0

    prs = get_merged_prs(owner, repo)
    print(f"\n[{repo_name}] Found {len(prs)} merged PRs")

    for i, pr in enumerate(prs, 1):
        # Skip if already fetched
        if (repo_name, pr['number']) in fetched_prs:
            print(f"\n[{repo_name}] Skipping PR #{pr['number']} - already fetched")
            continue

        print(f"\n[{repo_name}] Processing PR #{pr['number']} ({i}/{len(prs)})")

        # Get closing issues via GraphQL
        closing_issues = get_closing_issues(owner, repo, pr['number'])

        if not closing_issues:
            print(f"  Skipping - no linked issues found")
            continue

        print(f"  Closes issues: {[issue['number'] for issue in closing_issues]}")

        # Get PR files and commits
        files = get_pr_files(owner, repo, pr['number'])
        commits = get_pr_commits(owner, repo, pr['number'])

        # Calculate additions/deletions from files
        additions = sum(f.get('additions', 0) for f in files)
        deletions = sum(f.get('deletions', 0) for f in files)

        # Store raw data
        pr_data = {
            'repo': repo_name,
            'pr_number': pr['number'],
            'title': pr['title'],
            'description': pr.get('body', ''),
            'issues': closing_issues,
            'files_changed': len(files),
            'additions': additions,
            'deletions': deletions,
            'commits_count': len(commits),
            'file_paths': [f['filename'] for f in files],
            'commit_messages': [c['commit']['message'].split('\n')[0] for c in commits],
            'merged_at': pr['merged_at'],
            'pr_url': pr['html_url']
        }

        all_results.append(pr_data)
        fetched_prs.add((repo_name, pr['number']))
        new_count += 1

        # Save periodically
        if new_count % SAVE_EVERY_N_PRS == 0:
            save_data(all_results)
            print(f"  [Checkpoint] Saved {len(all_results)} total PRs to disk")

    # Final save for this repo
    if new_count > 0:
        save_data(all_results)

    return new_count

def main():
    """Main execution function."""
    print("=" * 80)
    print("GitHub PR Fetcher")
    print("=" * 80)

    # Load existing data for resume support
    all_results = load_existing_data()
    fetched_prs = get_fetched_prs(all_results)

    for repo_path in REPOSITORIES:
        owner, repo = repo_path.split('/')

        try:
            new_count = fetch_repository_data(owner, repo, all_results, fetched_prs)
            print(f"\n[{owner}/{repo}] Fetched {new_count} new PRs (total: {len(all_results)})")

        except Exception as e:
            print(f"\n[{owner}/{repo}] Error processing repository: {e}")
            # Save what we have so far
            if all_results:
                save_data(all_results)
                print(f"  [Emergency save] Saved {len(all_results)} PRs to disk")
            continue

    print(f"\nDone! Total PRs saved: {len(all_results)}")

if __name__ == "__main__":
    main()
