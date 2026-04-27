#!/usr/bin/env python3
"""Analyze benchmark instances from a harbor task directory.

Supports multiple patch/test-metadata formats:
  1. tests/config.json          – legacy format with patch, fail_to_pass, pass_to_pass, source_files
  2. solution/patch.diff        – standalone unified diff file
  3. solution/solve.sh          – patch embedded as heredoc between __SOLUTION__ markers
  4. tests/unit-test/manifest.json  – newer test manifest (generated_tests + existing_tests)
  5. tests/e2e/manifest.json        – additional e2e test manifest
  6. task.toml                  – instance metadata (repo, commits, PR info)
"""

import argparse
import csv
import json
import re
import statistics
from pathlib import Path

DEFAULT_INPUT = Path("/Users/pontusberglund/Documents/swebench-xl-internal-repo-temp/harbor/instances")

# ---------------------------------------------------------------------------
# File filters (per-repo)
# ---------------------------------------------------------------------------

# For elasticsearch: exclude changelogs and generated files, keep only .java
ES_FILTER = {
    "extensions": {".java"},
    "exclude_patterns": ["changelog", "generated/", "generated-src/"],
}


def should_include_file(filepath: str, repo: str) -> bool:
    """Decide whether a source file should be counted, applying repo-specific filters."""
    if "elastic/elasticsearch" in repo:
        low = filepath.lower()
        ext = Path(filepath).suffix.lower()
        if ext not in ES_FILTER["extensions"]:
            return False
        for pat in ES_FILTER["exclude_patterns"]:
            if pat in low:
                return False
        return True
    if "huggingface/transformers" in repo:
        if filepath.startswith("tests/"):
            return False
    # Default: include all files
    return True


# ---------------------------------------------------------------------------
# Patch extraction
# ---------------------------------------------------------------------------

def extract_patch_from_solve_sh(solve_sh_path: Path) -> str | None:
    """Extract the unified diff from a solve.sh that uses a __SOLUTION__ heredoc."""
    text = solve_sh_path.read_text(encoding="utf-8", errors="replace")
    # Match the heredoc: cat > ... << '__SOLUTION__' ... __SOLUTION__
    match = re.search(r"<<\s*'__SOLUTION__'\s*\n(.*?)\n__SOLUTION__", text, re.DOTALL)
    if match:
        return match.group(1)
    return None


def extract_patch(instance_dir: Path) -> str:
    """Extract the solution patch from a harbor task directory.

    Tries sources in priority order:
      1. solution/patch.diff  (standalone file)
      2. solution/solve.sh    (embedded heredoc)
      3. tests/config.json    (legacy 'patch' field)
    """
    # 1. Standalone patch file
    patch_diff = instance_dir / "solution" / "patch.diff"
    if patch_diff.exists():
        return patch_diff.read_text(encoding="utf-8", errors="replace")

    # 2. Embedded in solve.sh
    solve_sh = instance_dir / "solution" / "solve.sh"
    if solve_sh.exists():
        patch = extract_patch_from_solve_sh(solve_sh)
        if patch:
            return patch

    # 3. Legacy config.json
    config_json = instance_dir / "tests" / "config.json"
    if config_json.exists():
        data = json.loads(config_json.read_text(encoding="utf-8"))
        return data.get("patch", "")

    return ""


# ---------------------------------------------------------------------------
# Test metadata extraction
# ---------------------------------------------------------------------------

def extract_tests_from_manifest(manifest_path: Path) -> tuple[list[str], list[str]]:
    """Parse a manifest.json and return (fail_to_pass, pass_to_pass) test lists."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    f2p, p2p = [], []

    # Newer format: "generated_tests" + "existing_tests"
    for entry in data.get("generated_tests", []):
        if entry.get("type") == "FAIL_TO_PASS":
            f2p.append(entry["path"])
        elif entry.get("type") == "PASS_TO_PASS":
            p2p.append(entry["path"])
    for entry in data.get("existing_tests", []):
        if entry.get("type") == "FAIL_TO_PASS":
            f2p.append(entry["path"])
        elif entry.get("type") == "PASS_TO_PASS":
            p2p.append(entry["path"])

    # e2e-style format: just "tests"
    for entry in data.get("tests", []):
        if entry.get("type") == "FAIL_TO_PASS":
            f2p.append(entry["path"])
        elif entry.get("type") == "PASS_TO_PASS":
            p2p.append(entry["path"])

    return f2p, p2p


def extract_test_counts(instance_dir: Path) -> tuple[list[str], list[str]]:
    """Extract fail-to-pass and pass-to-pass test lists.

    Tries sources:
      1. tests/unit-test/manifest.json + tests/e2e/manifest.json  (newer format)
      2. tests/config.json  (legacy format with fail_to_pass / pass_to_pass arrays)
    """
    f2p_all, p2p_all = [], []

    # 1. Manifest files in sub-directories (unit-test, e2e, etc.)
    tests_dir = instance_dir / "tests"
    found_manifest = False
    if tests_dir.exists():
        for subdir in sorted(tests_dir.iterdir()):
            manifest = subdir / "manifest.json"
            if manifest.exists():
                found_manifest = True
                f2p, p2p = extract_tests_from_manifest(manifest)
                f2p_all.extend(f2p)
                p2p_all.extend(p2p)

    if found_manifest:
        return f2p_all, p2p_all

    # 2. Legacy config.json
    config_json = tests_dir / "config.json"
    if config_json.exists():
        data = json.loads(config_json.read_text(encoding="utf-8"))
        f2p_all = data.get("fail_to_pass", [])
        p2p_all = data.get("pass_to_pass", [])

    return f2p_all, p2p_all


# ---------------------------------------------------------------------------
# Metadata extraction from task.toml / config.json
# ---------------------------------------------------------------------------

def parse_task_toml(path: Path) -> dict:
    """Minimal TOML parser for task.toml (avoids external dependency)."""
    result = {}
    current_section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        section_match = re.match(r"\[(.+)]", line)
        if section_match:
            current_section = section_match.group(1) + "."
            continue
        kv_match = re.match(r"""(\w+)\s*=\s*['"](.+?)['"]""", line)
        if kv_match:
            result[current_section + kv_match.group(1)] = kv_match.group(2)
            continue
        kv_match = re.match(r"(\w+)\s*=\s*(.+)", line)
        if kv_match:
            result[current_section + kv_match.group(1)] = kv_match.group(2).strip().strip("'\"")

    return result


def extract_metadata(instance_dir: Path) -> dict:
    """Extract repo, instance_type, etc. from available metadata files."""
    meta = {"repo": "", "instance_type": ""}

    # task.toml
    task_toml = instance_dir / "task.toml"
    if task_toml.exists():
        toml = parse_task_toml(task_toml)
        meta["repo"] = toml.get("metadata.repository", "")

    # config.json (legacy) — has richer metadata
    config_json = instance_dir / "tests" / "config.json"
    if config_json.exists():
        data = json.loads(config_json.read_text(encoding="utf-8"))
        if not meta["repo"]:
            meta["repo"] = data.get("repo", "")
        meta["instance_type"] = data.get("instance_type", "")
        meta["source_files"] = data.get("source_files", [])

    # Infer repo from instance_id if not found
    if not meta["repo"]:
        instance_id = instance_dir.name
        parts = instance_id.split("__")
        if len(parts) == 2:
            org = parts[0]
            repo_name = parts[1].rsplit("-", 1)[0]
            meta["repo"] = f"{org}/{repo_name}"

    return meta


# ---------------------------------------------------------------------------
# Patch analysis
# ---------------------------------------------------------------------------

def count_patch_lines_per_file(patch_text: str) -> dict[str, tuple[int, int]]:
    """Parse a unified diff and return {filepath: (lines_added, lines_removed)} per file."""
    per_file: dict[str, tuple[int, int]] = {}
    current_file = None

    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path
            if current_file not in per_file:
                per_file[current_file] = (0, 0)
            continue
        if line.startswith("--- "):
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added, removed = per_file[current_file]
            per_file[current_file] = (added + 1, removed)
        elif line.startswith("-") and not line.startswith("---"):
            added, removed = per_file[current_file]
            per_file[current_file] = (added, removed + 1)

    return per_file


def get_files_from_patch(patch_text: str) -> list[str]:
    """Extract the list of files touched by a unified diff."""
    files = []
    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path != "/dev/null":
                files.append(path)
    return files


# ---------------------------------------------------------------------------
# Module detection (Gradle / Maven style for Elasticsearch)
# ---------------------------------------------------------------------------

def get_module(filepath: str) -> str:
    """Extract the Gradle module from a source file path."""
    for marker in ("/src/main/java/", "/src/test/java/", "/src/main/resources/", "/src/test/resources/"):
        idx = filepath.find(marker)
        if idx != -1:
            return filepath[:idx]
    return filepath.split("/")[0]


# ---------------------------------------------------------------------------
# Instance analysis
# ---------------------------------------------------------------------------

def analyze_instance(instance_dir: Path) -> dict:
    """Compute stats for a single harbor task instance."""
    instance_id = instance_dir.name
    meta = extract_metadata(instance_dir)
    repo = meta["repo"]

    # Extract patch
    patch_text = extract_patch(instance_dir)
    per_file = count_patch_lines_per_file(patch_text)

    # Determine source files: from config.json if available, otherwise from patch
    source_files = meta.get("source_files", [])
    if not source_files:
        source_files = get_files_from_patch(patch_text)

    # Apply repo-specific filters
    filtered_source = [f for f in source_files if should_include_file(f, repo)]

    # Count patch lines (only for filtered files if elasticsearch, otherwise all)
    lines_added = 0
    lines_removed = 0
    for filepath, (added, removed) in per_file.items():
        if should_include_file(filepath, repo):
            lines_added += added
            lines_removed += removed

    # Module analysis (elasticsearch-specific but harmless for other repos)
    modules = sorted(set(get_module(f) for f in filtered_source)) if filtered_source else []
    cross_module = len(modules) > 1

    # Test counts
    f2p, p2p = extract_test_counts(instance_dir)

    return {
        "instance_id": instance_id,
        "instance_type": meta.get("instance_type", ""),
        "f2p_count": len(f2p),
        "p2p_count": len(p2p),
        "source_file_count": len(filtered_source),
        "source_files": filtered_source,
        "modules": modules,
        "module_count": len(modules),
        "cross_module": cross_module,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "total_lines_changed": lines_added + lines_removed,
        "_repo": repo,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(results: list[dict]) -> None:
    """Print a formatted table of per-instance stats."""
    header = f"{'Instance ID':<45} {'Type':<20} {'F2P':>4} {'P2P':>5} {'Src':>4} {'Mods':>5} {'XMod':>5} {'+Lines':>7} {'-Lines':>7} {'Total':>7}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in results:
        xmod = "YES" if r['cross_module'] else ""
        print(
            f"{r['instance_id']:<45} {r['instance_type']:<20} "
            f"{r['f2p_count']:>4} {r['p2p_count']:>5} {r['source_file_count']:>4} "
            f"{r['module_count']:>5} {xmod:>5} "
            f"{r['lines_added']:>7} {r['lines_removed']:>7} {r['total_lines_changed']:>7}"
        )
    print(sep)


def print_summary(results: list[dict]) -> None:
    """Print aggregate statistics."""
    n = len(results)
    if n == 0:
        print("No instances to summarize.")
        return

    cross_module_count = sum(1 for r in results if r["cross_module"])
    single_module_count = n - cross_module_count

    metrics = {
        "Fail-to-Pass tests": [r["f2p_count"] for r in results],
        "Pass-to-Pass tests": [r["p2p_count"] for r in results],
        "Source files (.java only)": [r["source_file_count"] for r in results],
        "Modules touched": [r["module_count"] for r in results],
        "Lines added": [r["lines_added"] for r in results],
        "Lines removed": [r["lines_removed"] for r in results],
        "Total lines changed": [r["total_lines_changed"] for r in results],
    }

    print(f"\n{'='*60}")
    print(f" SUMMARY  ({n} instances)")
    print(f"{'='*60}")
    print(f" Cross-module: {cross_module_count}  |  Single-module: {single_module_count}")
    print(f"{'Metric':<32} {'Min':>6} {'Max':>6} {'Mean':>8} {'Median':>8} {'Total':>8}")
    print(f"{'-'*32} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
    for name, values in metrics.items():
        mn = min(values)
        mx = max(values)
        avg = statistics.mean(values)
        med = statistics.median(values)
        total = sum(values)
        print(f"{name:<32} {mn:>6} {mx:>6} {avg:>8.1f} {med:>8.1f} {total:>8}")


def build_summary(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}
    metric_keys = [
        ("f2p_count", "fail_to_pass"),
        ("p2p_count", "pass_to_pass"),
        ("source_file_count", "source_files"),
        ("lines_added", "lines_added"),
        ("lines_removed", "lines_removed"),
        ("total_lines_changed", "total_lines_changed"),
    ]
    summary: dict = {"total_instances": n}
    for key, label in metric_keys:
        values = [r[key] for r in results]
        summary[label] = {
            "min": min(values),
            "max": max(values),
            "mean": round(statistics.mean(values), 2),
            "median": statistics.median(values),
            "total": sum(values),
        }
    return summary


def write_json_output(results: list[dict], summary: dict, path: str) -> None:
    # Strip internal-only keys before writing
    clean_results = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    output = {"instances": clean_results, "summary": summary}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nJSON output written to {path}")


def write_csv_output(results: list[dict], path: str) -> None:
    fieldnames = [
        "instance_id", "instance_type", "f2p_count", "p2p_count",
        "source_file_count", "module_count", "cross_module",
        "lines_added", "lines_removed", "total_lines_changed",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"CSV output written to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark instances from a harbor task directory")
    parser.add_argument(
        "input", nargs="?", default=str(DEFAULT_INPUT),
        help="Path to the harbor instances directory (contains one sub-dir per instance)",
    )
    parser.add_argument("-o", "--output", default=None, help="Path for JSON output")
    parser.add_argument("--csv", default=None, help="Path for CSV output")
    parser.add_argument("--repo", default=None, help="Filter to a specific repo (e.g. elastic/elasticsearch)")
    args = parser.parse_args()

    if args.output is None:
        args.output = str(Path(__file__).resolve().parent / "instance_stats_harbor_output.json")

    instances_dir = Path(args.input)
    if not instances_dir.is_dir():
        print(f"ERROR: {instances_dir} is not a directory")
        return

    # Discover instances
    instance_dirs = sorted(
        d for d in instances_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    if not instance_dirs:
        print(f"No instance directories found in {instances_dir}")
        return

    results = []
    for d in instance_dirs:
        result = analyze_instance(d)
        if args.repo and result["_repo"] != args.repo:
            continue
        results.append(result)

    results.sort(key=lambda r: r["instance_id"])

    print_table(results)
    print_summary(results)

    summary = build_summary(results)
    write_json_output(results, summary, args.output)

    if args.csv:
        write_csv_output(results, args.csv)


if __name__ == "__main__":
    main()
