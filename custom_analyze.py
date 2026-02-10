import json
import csv

INPUT_FILE = "pr_analysis_results_full.json"

CSV_FILE = "full_swe_bench_pro_complexity.csv"

def load_results(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def load_csv(path: str):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data
    
if __name__ == "__main__":
    results = load_results(INPUT_FILE)
    print(f"Loaded {len(results)} results\n")
    difficulties = []
    for r in results:
        if r['benchmark_verdict']['is_suitable'] and r["verifiability_audit"]["has_tests"] and r["verifiability_audit"]["self_contained_issue"] and r["repo"] == "BabylonJS/Babylon.js":
            difficulties.append((r["benchmark_verdict"]["difficulty_score"]))
    
    print(f"Number of suitable PRs with self-contained issues and tests in BabylonJS/Babylon.js: {len(difficulties)}")
    print(f"Average difficulty of suitable PRs with self-contained issues and tests in BabylonJS/Babylon.js: {sum(difficulties)/len(difficulties) if difficulties else 'N/A':.3f}")
    
    csv_data = load_csv(CSV_FILE)
    print(f"Loaded {len(csv_data)} rows from CSV\n")
    difficulties_csv = []
    for row in csv_data:
        difficulties_csv.append(float(row["difficulty"]))
    print(f"Average difficulty from CSV: {sum(difficulties_csv)/len(difficulties_csv) if difficulties_csv else 'N/A':.3f}")
    
    