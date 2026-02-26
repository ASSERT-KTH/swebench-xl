# Replace problem_statement_title and problem_statement_description in dataset.jsonl with actual title and description from the issues.

import json


def update_problem_statements(
    dataset_path: str = "../benchmark/dataset.jsonl",
    pr_analysis_path: str = "../data/pr_analysis_results_full.json",
    output_path: str = "../benchmark/dataset_new.jsonl",
) -> None:
    """
    For each entry in dataset.jsonl, find the matching entry in pr_analysis_results_full.json
    by instance_id and replace problem_statement_title and problem_statement_description
    with the combined titles and bodies from the matching entry's 'issues' array.
    """
    # Load pr_analysis_results_full.json and index by instance_id
    with open(pr_analysis_path, "r", encoding="utf-8") as f:
        pr_data = json.load(f)

    pr_lookup: dict = {
        f"{entry['repo'].replace('/', '__')}-{entry['pr_number']}": entry
        for entry in pr_data
    }

    # Process each line in dataset.jsonl
    updated_entries = []
    matched = 0
    skipped = 0

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            entry = json.loads(line)
            instance_id = entry.get("instance_id")

            pr_entry = pr_lookup.get(instance_id)

            if pr_entry is None:
                print(f"[Line {line_num}] No match found for instance_id: {instance_id}")
                skipped += 1
                updated_entries.append(entry)
                continue

            issues = pr_entry.get("issues", [])
            if not issues:
                print(f"[Line {line_num}] No issues found for instance_id: {instance_id}")
                skipped += 1
                updated_entries.append(entry)
                continue

            if len(issues) == 1:
                entry["problem_statement_title"] = issues[0].get("title", "")
                entry["problem_statement_description"] = issues[0].get("body", "")
            else:
                entry["problem_statement_title"] = " | ".join(
                    issue.get("title", "") for issue in issues
                )
                entry["problem_statement_description"] = "\n\n---\n\n".join(
                    f"### Issue {i + 1}: {issue.get('title', '')}\n\n{issue.get('body', '')}"
                    for i, issue in enumerate(issues)
                )

            matched += 1
            updated_entries.append(entry)

    # Write updated entries back to output file
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in updated_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"\nDone. Matched: {matched}, Skipped: {skipped}, Total: {len(updated_entries)}")

if __name__ == "__main__":
    update_problem_statements()