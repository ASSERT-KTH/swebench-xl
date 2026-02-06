"""
PR Analyzer with LLM
Reads PR data from JSON and analyzes each PR using an LLM.
"""

import os
import requests
import json
import re
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

# API Configuration
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

# LLM Model (adjust to your preferred model on OpenRouter)
LLM_MODEL = "anthropic/claude-3.5-sonnet"  # or "openai/gpt-4-turbo", etc.

# Files
INPUT_FILE = "pr_data.json"
OUTPUT_FILE = "pr_analysis_results.json"

# ============================================================================
# LLM ANALYSIS FUNCTIONS
# ============================================================================

def analyze_pr_with_llm(pr_data: Dict) -> Dict:
    """
    Sends PR data to LLM for categorization.
    """
    # Construct prompt
    prompt = f"""Analyze this pull request and categorize it based on the task type and level of codebase understanding required.

**Pull Request Information:**
- Title: {pr_data['title']}
- Description: {(pr_data.get('description') or '')[:1000]}
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

def print_statistics(results: List[Dict]):
    """Prints summary statistics."""
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total PRs analyzed: {len(results)}")

    if not results:
        return

    # Task type distribution
    task_types = {}
    understanding_levels = {}

    for result in results:
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
    scores = [r.get('complexity_score', 0) for r in results if r.get('complexity_score', 0) > 0]
    if scores:
        avg_complexity = sum(scores) / len(scores)
        print(f"\nAverage Complexity Score: {avg_complexity:.2f}/10")

    # Domain knowledge required
    domain_knowledge_count = sum(1 for r in results if r.get('requires_domain_knowledge'))
    print(f"PRs requiring domain knowledge: {domain_knowledge_count} ({domain_knowledge_count/len(results)*100:.1f}%)")

def main():
    """Main execution function."""
    print("=" * 80)
    print("PR Analyzer with LLM")
    print("=" * 80)

    # Load PR data
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            pr_data_list = json.load(f)
        print(f"\nLoaded {len(pr_data_list)} PRs from {INPUT_FILE}")
    except FileNotFoundError:
        print(f"\nError: {INPUT_FILE} not found. Run fetch_prs.py first.")
        return
    except json.JSONDecodeError as e:
        print(f"\nError: Invalid JSON in {INPUT_FILE}: {e}")
        return

    # Analyze each PR
    results = []
    for i, pr_data in enumerate(pr_data_list, 1):
        print(f"\n[{i}/{len(pr_data_list)}] Analyzing PR #{pr_data['pr_number']} from {pr_data['repo']}")

        analysis = analyze_pr_with_llm(pr_data)

        result = {
            **pr_data,
            **analysis
        }
        results.append(result)

        print(f"  Categorized as: {analysis['task_type']} ({analysis['understanding_level']})")

    # Save results
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved analysis results to {OUTPUT_FILE}")

    # Print statistics
    print_statistics(results)

if __name__ == "__main__":
    main()
