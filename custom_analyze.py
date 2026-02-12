import json
import csv
import statistics

INPUT_FILE = "pr_analysis_results_full.json"
FAIL_TO_PASS_FILE = "fail_to_pass_results.json"

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

def count_modified_lines(patch_text: str) -> tuple[int, int]:
    added = 0
    removed = 0
    current_file = None
    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            continue
        if line.startswith("--- "):
            path = line[4:].strip()
            if path.startswith("a/"):
                path = path[2:]
            if current_file is None:
                current_file = path
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed
    
if __name__ == "__main__":
    full_results = load_results(INPUT_FILE)
    fail_to_pass_results = load_results(FAIL_TO_PASS_FILE)
    difficulties = []
    non_test_line_mods = []
    for r in fail_to_pass_results:
        if r["status"] != 'verified':
            continue
        pr_number = r["pr_number"]
        for pr in full_results:
            if pr["pr_number"] == pr_number:
                #print(pr)
                difficulty = pr["benchmark_verdict"]["difficulty_score"]
                difficulties.append(difficulty)
        patch_text = r.get("patch") or ""
        added, removed = count_modified_lines(patch_text)
        non_test_line_mods.append(added + removed)
                
    print(f"Average difficulty for fail-to-pass PRs: {sum(difficulties)/len(difficulties) if difficulties else 'N/A':.3f} with {len(difficulties)} PRs")
    if non_test_line_mods:
        avg_lines_modified = sum(non_test_line_mods) / len(non_test_line_mods)
        median_lines_modified = statistics.median(non_test_line_mods)
        print(
            "Average lines modified (non-test files): "
            f"{avg_lines_modified:.3f} | Median: {median_lines_modified:.3f} "
            f"({len(non_test_line_mods)} PRs)"
        )
    else:
        print("Average lines modified (non-test files): N/A | Median: N/A (0 PRs)")
    csv_data = load_csv(CSV_FILE)
    print(f"Loaded {len(csv_data)} rows from CSV\n")
    difficulties_csv = []
    for row in csv_data:
        difficulties_csv.append(float(row["difficulty"]))
    print(f"Average difficulty from CSV: {sum(difficulties_csv)/len(difficulties_csv) if difficulties_csv else 'N/A':.3f}")
    
    