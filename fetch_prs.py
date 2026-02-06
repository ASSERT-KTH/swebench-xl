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
    #"openjdk/jdk",
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

# Search API settings
SEARCH_RATE_LIMIT_DELAY = 2.5  # Search API has stricter rate limits (30/min)
SEARCH_YEARS_BACK = 10  # How many years back to search (in 1-year chunks to avoid 1000 limit)

# Output
OUTPUT_FILE = "pr_data_new_approach.json"
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

def handle_rate_limit(response, is_search_api=False):
    """Check rate limit headers and wait if necessary."""
    remaining = int(response.headers.get('X-RateLimit-Remaining', 1000))
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

    # Search API has lower limit (30/min), so use lower buffer
    buffer = 5 if is_search_api else RATE_LIMIT_BUFFER

    if remaining <= buffer:
        wait_time = max(0, reset_time - time.time()) + 5  # Add 5s buffer
        if wait_time > 0:
            print(f"\n  [Rate limit] {remaining} requests remaining. Waiting {wait_time:.0f}s until reset...")
            time.sleep(wait_time)
    else:
        # Use longer delay for search API
        delay = SEARCH_RATE_LIMIT_DELAY if is_search_api else MIN_DELAY_BETWEEN_REQUESTS
        time.sleep(delay)

def github_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a GitHub API request with rate limit handling and retries."""
    headers = kwargs.pop('headers', get_github_headers())

    for attempt in range(MAX_RETRIES):
        response = requests.request(method, url, headers=headers, **kwargs)

        # Success
        if response.status_code == 200:
            is_search = '/search/' in url
            handle_rate_limit(response, is_search_api=is_search)
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

def search_merged_prs_with_issues(owner: str, repo: str) -> List[Dict]:
    """
    Uses GitHub Search API to find merged PRs with linked issues.
    Searches in yearly chunks to avoid the 1000 result limit.
    """
    all_prs = []
    current_year = datetime.now().year

    print(f"\n[{owner}/{repo}] Searching for merged PRs with linked issues...")

    for year_offset in range(SEARCH_YEARS_BACK):
        year = current_year - year_offset
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        page = 1
        year_prs = []

        while True:
            # Search query: merged PRs with linked issues in this repo for this year
            query = f"repo:{owner}/{repo} is:pr is:merged linked:issue merged:{start_date}..{end_date}"
            url = f"{GITHUB_API_BASE}/search/issues"
            params = {
                'q': query,
                'per_page': 100,
                'page': page,
                'sort': 'updated',
                'order': 'desc'
            }

            response = github_request('GET', url, params=params)

            if response.status_code != 200:
                print(f"  Error searching PRs: {response.status_code} - {response.text[:200]}")
                break

            data = response.json()
            items = data.get('items', [])
            total_count = data.get('total_count', 0)

            if page == 1:
                print(f"  {year}: Found {total_count} PRs with linked issues")

            if not items:
                break

            year_prs.extend(items)

            # Search API has stricter rate limits
            time.sleep(SEARCH_RATE_LIMIT_DELAY)

            if len(items) < 100:
                break

            page += 1

            # Safety check - search API only returns max 1000 results
            if page > 10:
                print(f"  Warning: Hit 1000 result limit for {year}. Some PRs may be missing.")
                break

        all_prs.extend(year_prs)

    print(f"  Total: {len(all_prs)} merged PRs with linked issues")
    return all_prs

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
              labels(first: 20) {
                nodes {
                  name
                }
              }
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
            issues = pr_data.get("closingIssuesReferences", {}).get("nodes", [])
            # Flatten labels from GraphQL format
            for issue in issues:
                labels_data = issue.pop('labels', {})
                issue['labels'] = [l['name'] for l in labels_data.get('nodes', [])]
            return issues
    return []

def get_pr_files(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """Fetches the list of files changed in a PR."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"

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
    Fetches PR data from a repository using Search API, skipping already fetched PRs.
    Saves incrementally to disk.
    Returns the number of new PRs fetched.
    """
    repo_name = f"{owner}/{repo}"
    new_count = 0

    # Use search API to get only merged PRs with linked issues
    prs = search_merged_prs_with_issues(owner, repo)
    print(f"\n[{repo_name}] Processing {len(prs)} PRs with linked issues")

    for i, pr in enumerate(prs, 1):
        pr_number = pr['number']

        # Skip if already fetched
        if (repo_name, pr_number) in fetched_prs:
            continue

        print(f"\n[{repo_name}] Processing PR #{pr_number} ({i}/{len(prs)})")

        # Get closing issues via GraphQL (to get issue details)
        closing_issues = get_closing_issues(owner, repo, pr_number)

        if not closing_issues:
            print(f"  Warning: Search said linked but no closing issues found via GraphQL")
            continue

        print(f"  Closes issues: {[issue['number'] for issue in closing_issues]}")

        # Get PR files
        files = get_pr_files(owner, repo, pr_number)

        # Calculate additions/deletions from files
        additions = sum(f.get('additions', 0) for f in files)
        deletions = sum(f.get('deletions', 0) for f in files)

        # Get merged_at from pull_request object in search results
        merged_at = pr.get('pull_request', {}).get('merged_at')

        # Extract patches from files
        patches = [
            {
                'filename': f['filename'],
                'status': f.get('status', ''),  # added, removed, modified, renamed
                'additions': f.get('additions', 0),
                'deletions': f.get('deletions', 0),
                'patch': f.get('patch', '')  # The actual diff
            }
            for f in files
        ]

        # Extract labels from PR
        pr_labels = [label['name'] for label in pr.get('labels', [])]

        # Extract labels from issues
        issue_labels = []
        for issue in closing_issues:
            issue_labels.extend([label['name'] for label in issue.get('labels', [])])
        issue_labels = list(set(issue_labels))  # Remove duplicates

        # Store raw data
        pr_data = {
            'repo': repo_name,
            'pr_number': pr_number,
            'title': pr['title'],
            'description': pr.get('body', ''),
            'pr_labels': pr_labels,
            'issues': closing_issues,
            'issue_labels': issue_labels,
            'files_changed': len(files),
            'additions': additions,
            'deletions': deletions,
            'file_paths': [f['filename'] for f in files],
            'patches': patches,
            'created_at': pr.get('created_at'),
            'merged_at': merged_at,
            'pr_url': pr['html_url']
        }

        all_results.append(pr_data)
        fetched_prs.add((repo_name, pr_number))
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
