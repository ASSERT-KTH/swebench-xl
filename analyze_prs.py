"""
PR Analyzer with LLM
Reads PR data from JSON and analyzes each PR using an LLM.
"""

import os
import requests
import json
import re
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

LLM_MODEL = "google/gemini-2.5-flash"

# Files
INPUT_FILE = "pr_data_new_approach.json"
OUTPUT_FILE = "pr_analysis_results_test.json"

# ============================================================================
# LLM ANALYSIS FUNCTIONS
# ============================================================================

def analyze_pr_with_llm(pr_data: Dict) -> Dict:
    """
    Sends PR data to LLM for categorization.
    """
    file_paths = [p['filename'] for p in pr_data['patches']]

    # Build issue text from linked issues
    issues = pr_data.get('issues', [])
    if issues:
        issue_text_content = '\n'.join(
            f"Issue #{iss['number']}: {iss['title']}\n{(iss.get('body') or '')[:500]}"
            for iss in issues
        )
    else:
        issue_text_content = 'No linked issue'

    # Sample patches intelligently - prioritize smaller, meaningful files
    patches_to_include = []
    patch_budget = 8000  # characters
    for patch in sorted(pr_data['patches'], key=lambda p: len(p.get('patch', ''))):
        patch_text = patch.get('patch', '')
        if len(patch_text) + sum(len(p) for p in patches_to_include) < patch_budget:
            patches_to_include.append(f"File: {patch['filename']}\n{patch_text}")
        if len(patches_to_include) >= 10:
            break

    diff_snippet = '\n'.join(patches_to_include) if patches_to_include else 'No diff available'

    prompt = f"""You are an expert Senior Software Engineer auditing pull requests to build a dataset for coding agents.
Your goal is to identify if this PR represents a "Large Codebase Challenge"—a task where the difficulty lies in understanding the existing system, navigation, and integration, rather than just algorithmic logic.

Input Data:
- Repo: {pr_data['repo']}
- Title: {pr_data['title']}
- Description: {(pr_data.get('description') or '')[:1500]}
- Issue Body: {issue_text_content[:1000]}
- Files Changed: {pr_data['files_changed']} (Add: {pr_data['additions']}, Del: {pr_data['deletions']})
- File Paths: {', '.join(file_paths[:30])}
- Diff Snippet:
{diff_snippet}

Analyze the data and return a JSON object evaluating this PR as a benchmark candidate.

JSON Schema:
{{
  "category": "String: [bug, feature, refactor, test, docs, dependency, other]",
  "complexity_analysis": {{
    "context_dependency": "String: [low, medium, high] (Low=isolated change, High=requires reading many external files)",
    "multi_file_logic": "Boolean: Does the logic span multiple files? (Not just import updates)",
    "requires_domain_knowledge": "Boolean: Does it require knowing specific business rules mentioned in the issue?"
  }},
  "large_codebase_factors": {{
    "navigation_step_required": "Boolean: Would an agent need to search for usages/definitions to solve this?",
    "pattern_matching_required": "Boolean: Must the agent copy a specific coding style/pattern used elsewhere in the repo?",
    "breaking_change_risk": "String: [low, high] (Is there a high risk of breaking unrelated modules?)"
  }},
  "verifiability_audit": {{
    "has_tests": "Boolean: Does the PR include new/modified test files?",
    "test_type": "String: [unit, integration, e2e, none]",
    "self_contained_issue": "Boolean: Is the issue description sufficient to solve the task without external links (Jira/Slack)?"
  }},
  "benchmark_verdict": {{
    "is_suitable": "Boolean",
    "difficulty_score": "Integer: 1-5 (5 = hardest)",
    "rejection_reason": "String or null (e.g. 'Too trivial', 'Missing tests', 'Ambiguous description')",
    "primary_challenge": "String: [navigation, logic, testing, api_knowledge]"
  }}
}}

Constraint: Return ONLY valid JSON. No markdown formatting."""

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
        "temperature": 0.3,
        "max_tokens": 1024
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
        "category": "other",
        "complexity_analysis": {
            "context_dependency": "low",
            "multi_file_logic": False,
            "requires_domain_knowledge": False
        },
        "large_codebase_factors": {
            "navigation_step_required": False,
            "pattern_matching_required": False,
            "breaking_change_risk": "low"
        },
        "verifiability_audit": {
            "has_tests": False,
            "test_type": "none",
            "self_contained_issue": False
        },
        "benchmark_verdict": {
            "is_suitable": False,
            "difficulty_score": 0,
            "rejection_reason": "Analysis failed",
            "primary_challenge": "logic"
        }
    }

def main():
    """Main execution function."""
    print(f"Loading PRs from {INPUT_FILE}...")

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            pr_data_list = json.load(f)
        print(f"Loaded {len(pr_data_list)} PRs")
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found. Run fetch_prs.py first.")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {INPUT_FILE}: {e}")
        return

    results = []
    for i, pr_data in enumerate(pr_data_list, 1):
        if i > 100:
            print(f"Limiting to first 100 PRs for testing. Remove this condition to analyze all.")
            break

        if pr_data['files_changed'] < 4 or pr_data['files_changed'] > 100:
            print(f"[{i}/{len(pr_data_list)}] PR #{pr_data['pr_number']} — skipped ({pr_data['files_changed']} files)")
            continue

        analysis = analyze_pr_with_llm(pr_data)

        result = {**pr_data, **analysis}
        results.append(result)

        suitable = "✓" if analysis.get('benchmark_verdict', {}).get('is_suitable') else "✗"
        print(f"[{i}/{len(pr_data_list)}] PR #{pr_data['pr_number']} — {analysis.get('category', '?')} | {suitable}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nDone. {len(results)} results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
