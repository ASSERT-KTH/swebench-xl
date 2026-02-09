import json

INPUT_FILE = "pr_analysis_results_full.json"

def load_results(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
if __name__ == "__main__":
    results = load_results(INPUT_FILE)
    print(f"Loaded {len(results)} results\n")
    difficulties = []
    for r in results:
        if r['benchmark_verdict']['is_suitable'] and r["verifiability_audit"]["has_tests"] and r["verifiability_audit"]["self_contained_issue"]:
            difficulties.append((r["benchmark_verdict"]["difficulty_score"]))
    
    print(f"Average difficulty of suitable PRs with self-contained issues and tests: {sum(difficulties)/len(difficulties) if difficulties else 'N/A':.3f}")