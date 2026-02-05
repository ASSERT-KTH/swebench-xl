"""
GitHub PR Analyzer for Coding Agent Benchmark
Analyzes merged PRs that close issues to identify tasks requiring deep codebase understanding.
"""

import requests
import time
import json
import re
from typing import List, Dict

# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_TOKEN = "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"  # Get from https://github.com/settings/tokens
OPENROUTER_API_KEY = "your_openrouter_api_key_here"

# Repositories to analyze
REPOSITORIES = [
    "openjdk/jdk",
    "arangodb/arangodb",
    "nodejs/node"
]

# API Configuration
GITHUB_API_BASE = "https://api.github.com"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

# Rate limiting
REQUESTS_PER_HOUR = 4500  # Adjust based on your GitHub token tier
DELAY_BETWEEN_REQUESTS = 0.8  # seconds

# Output
OUTPUT_JSON = "pr_analysis_results.json"

# LLM Model (adjust to your preferred model on OpenRouter)
LLM_MODEL = "anthropic/claude-3.5-sonnet"  # or "openai/gpt-4-turbo", etc.

# ============================================================================
# GITHUB API FUNCTIONS
# ============================================================================

def get_github_headers():
    """Returns headers for GitHub API requests."""
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

def get_merged_prs(owner: str, repo: str, max_prs: int = 500) -> List[Dict]:
    """
    Fetches merged pull requests from a repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        max_prs: Maximum number of PRs to fetch
    
    Returns:
        List of PR objects
    """
    prs = []
    page = 1
    per_page = 100
    
    print(f"\n[{owner}/{repo}] Fetching merged PRs...")
    
    while len(prs) < max_prs and page <= 10:  # Limit to 10 pages to avoid excessive requests
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'closed',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': per_page,
            'page': page
        }
        
        response = requests.get(url, headers=get_github_headers(), params=params)
        
        if response.status_code != 200:
            print(f"Error fetching PRs: {response.status_code}")
            break
        
        page_prs = response.json()
        
        if not page_prs:
            break
        
        # Filter for merged PRs only
        merged_prs = [pr for pr in page_prs if pr.get('merged_at') is not None]
        prs.extend(merged_prs)
        
        print(f"  Fetched page {page}, total merged PRs: {len(prs)}")
        
        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
        if len(page_prs) < per_page:
            break
    
    return prs[:max_prs]

def get_closing_issues(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """
    Fetches issues that are closed by a PR using GitHub's GraphQL API.
    This is more reliable than regex parsing as GitHub determines the links.
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

    response = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
        json={
            "query": query,
            "variables": {"owner": owner, "repo": repo, "pr": pr_number}
        }
    )
    time.sleep(DELAY_BETWEEN_REQUESTS)

    if response.status_code == 200:
        data = response.json()
        pr_data = data.get("data", {}).get("repository", {}).get("pullRequest")
        if pr_data:
            return pr_data.get("closingIssuesReferences", {}).get("nodes", [])
    return []

def get_pr_files(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """Fetches the list of files changed in a PR."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    
    response = requests.get(url, headers=get_github_headers())
    time.sleep(DELAY_BETWEEN_REQUESTS)
    
    if response.status_code == 200:
        return response.json()
    return []

def get_pr_commits(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """Fetches commits in a PR."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    
    response = requests.get(url, headers=get_github_headers())
    time.sleep(DELAY_BETWEEN_REQUESTS)
    
    if response.status_code == 200:
        return response.json()
    return []

# ============================================================================
# LLM ANALYSIS FUNCTIONS
# ============================================================================

def analyze_pr_with_llm(pr_data: Dict) -> Dict:
    """
    Sends PR data to LLM for categorization.
    
    Returns:
        Dict with categorization results
    """
    
    # Construct prompt
    prompt = f"""Analyze this pull request and categorize it based on the task type and level of codebase understanding required.

**Pull Request Information:**
- Title: {pr_data['title']}
- Description: {pr_data['description'][:1000]}...
- Repository: {pr_data['repo']}
- Files Changed: {pr_data['files_changed']}
- Lines Added: {pr_data['additions']}
- Lines Deleted: {pr_data['deletions']}
- File Paths: {', '.join(pr_data['file_paths'][:10])}

**Linked Issues:**
{chr(10).join(f"#{issue['number']}: {issue['title']}{chr(10)}{(issue.get('body') or '')[:500]}" for issue in pr_data.get('issues', []))}

**Commit Messages:**
{chr(10).join(pr_data['commit_messages'][:5])}

Please provide a JSON response with the following fields:
1. "task_type": One of [bug_fix, feature_addition, refactoring, performance_optimization, documentation, test_addition, dependency_update, other]
2. "understanding_level": One of [surface_level, module_level, cross_module, architecture_level]
   - surface_level: Isolated change, minimal context needed
   - module_level: Requires understanding one component/module
   - cross_module: Requires understanding interactions between multiple modules
   - architecture_level: Requires system-wide architectural understanding
3. "complexity_score": Integer 1-10 (1=simple, 10=highly complex)
4. "requires_domain_knowledge": Boolean (does it require specific domain expertise beyond coding?)
5. "reasoning": Brief explanation (2-3 sentences) of your categorization

Respond ONLY with valid JSON, no other text."""

    # Call OpenRouter API
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,  # Lower temperature for more consistent categorization
        "max_tokens": 500
    }
    
    try:
        response = requests.post(
            f"{OPENROUTER_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            llm_response = result['choices'][0]['message']['content']
            
            # Parse JSON from response
            # Remove markdown code blocks if present
            llm_response = llm_response.strip()
            if llm_response.startswith('```'):
                llm_response = re.sub(r'^```json?\n', '', llm_response)
                llm_response = re.sub(r'\n```$', '', llm_response)
            
            analysis = json.loads(llm_response)
            return analysis
        else:
            print(f"LLM API error: {response.status_code}")
            return get_default_analysis()
    
    except Exception as e:
        print(f"Error analyzing with LLM: {e}")
        return get_default_analysis()

def get_default_analysis():
    """Returns default analysis in case of LLM failure."""
    return {
        "task_type": "unknown",
        "understanding_level": "unknown",
        "complexity_score": 0,
        "requires_domain_knowledge": False,
        "reasoning": "Analysis failed"
    }

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_repository(owner: str, repo: str) -> List[Dict]:
    """
    Processes a single repository and returns analyzed PR data.
    """
    results = []
    
    # Fetch merged PRs
    prs = get_merged_prs(owner, repo, max_prs=100)  # Adjust max_prs as needed
    print(f"\n[{owner}/{repo}] Found {len(prs)} merged PRs")
    
    for i, pr in enumerate(prs, 1):
        print(f"\n[{owner}/{repo}] Processing PR #{pr['number']} ({i}/{len(prs)})")

        # Get closing issues via GraphQL
        closing_issues = get_closing_issues(owner, repo, pr['number'])

        if not closing_issues:
            print(f"  Skipping - no linked issues found")
            continue

        print(f"  Closes issues: {[issue['number'] for issue in closing_issues]}")

        # Get PR files and commits
        files = get_pr_files(owner, repo, pr['number'])
        commits = get_pr_commits(owner, repo, pr['number'])

        # Prepare data for LLM analysis
        pr_data = {
            'repo': f"{owner}/{repo}",
            'pr_number': pr['number'],
            'title': pr['title'],
            'description': pr.get('body', ''),
            'issues': closing_issues,
            'files_changed': len(files),
            'additions': pr.get('additions', 0),
            'deletions': pr.get('deletions', 0),
            'commits_count': len(commits),
            'file_paths': [f['filename'] for f in files],
            'commit_messages': [c['commit']['message'].split('\n')[0] for c in commits],
            'merged_at': pr['merged_at'],
            'pr_url': pr['html_url']
        }
        
        # Analyze with LLM
        print(f"  Analyzing with LLM...")
        analysis = get_default_analysis()#analyze_pr_with_llm(pr_data)
        
        # Combine data
        result = {
            **pr_data,
            **analysis
        }
        
        # Clean up lists for CSV
        result['file_paths'] = '; '.join(result['file_paths'][:20])  # Limit to 20 files
        result['commit_messages'] = '; '.join(result['commit_messages'][:10])  # Limit to 10
        
        results.append(result)
        
        print(f"  ✓ Categorized as: {analysis['task_type']} ({analysis['understanding_level']})")
        
        # Be nice to the APIs
        time.sleep(1)
    
    return results

def save_results_to_json(all_results: List[Dict], filename: str):
    """Saves results to JSON file."""
    if not all_results:
        print("No results to save!")
        return

    with open(filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(all_results, jsonfile, indent=2, ensure_ascii=False)

    print(f"\n✓ Results saved to {filename}")

def main():
    """Main execution function."""
    print("=" * 80)
    print("GitHub PR Analyzer for Coding Agent Benchmark")
    print("=" * 80)
    
    all_results = []
    
    for repo_path in REPOSITORIES:
        owner, repo = repo_path.split('/')
        
        try:
            results = process_repository(owner, repo)
            all_results.extend(results)
            print(f"\n[{owner}/{repo}] Processed {len(results)} PRs with linked issues")
        
        except Exception as e:
            print(f"\n[{owner}/{repo}] Error processing repository: {e}")
            continue
    
    # Save results
    save_results_to_json(all_results, OUTPUT_JSON)
    
    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total PRs analyzed: {len(all_results)}")
    
    if all_results:
        # Task type distribution
        task_types = {}
        understanding_levels = {}
        
        for result in all_results:
            task_type = result.get('task_type', 'unknown')
            understanding = result.get('understanding_level', 'unknown')
            
            task_types[task_type] = task_types.get(task_type, 0) + 1
            understanding_levels[understanding] = understanding_levels.get(understanding, 0) + 1
        
        print("\nTask Type Distribution:")
        for task_type, count in sorted(task_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {task_type}: {count}")
        
        print("\nUnderstanding Level Distribution:")
        for level, count in sorted(understanding_levels.items(), key=lambda x: x[1], reverse=True):
            print(f"  {level}: {count}")
        
        # Average complexity
        avg_complexity = sum(r.get('complexity_score', 0) for r in all_results) / len(all_results)
        print(f"\nAverage Complexity Score: {avg_complexity:.2f}/10")
        
        # Domain knowledge required
        domain_knowledge_count = sum(1 for r in all_results if r.get('requires_domain_knowledge'))
        print(f"PRs requiring domain knowledge: {domain_knowledge_count} ({domain_knowledge_count/len(all_results)*100:.1f}%)")

if __name__ == "__main__":
    main()