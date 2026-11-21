"""Fetch the list of files git tracks at every base commit in results/task_commits.tsv.

Uses the GitHub tree API (``gh api``, so `gh` must be authenticated). The API truncates
very large trees (here: all microsoft/typescript and some elastic/elasticsearch commits);
those are fetched instead with a shallow, blobless ``git fetch`` and listed with
``git ls-tree``, which downloads trees but no file contents.

Each commit's file list is cached as ``.trees/<owner>__<repo>__<sha>.json.gz``
({"blobs": [...], "submodules": [...]}); re-running skips cached commits.

    python fetch_trees.py [--workers 8]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREES = HERE / ".trees"
GIT_CACHE = HERE / ".git-cache"


def tree_path(repo: str, sha: str) -> Path:
    return TREES / f"{repo.replace('/', '__')}__{sha}.json.gz"


def save(repo: str, sha: str, blobs: list[str], submodules: list[str], source: str) -> None:
    with gzip.open(tree_path(repo, sha), "wt") as f:
        json.dump({"blobs": blobs, "submodules": submodules, "source": source}, f)


def from_api(pair: tuple[str, str]) -> str:
    repo, sha = pair
    if tree_path(repo, sha).exists():
        return "cached"
    r = subprocess.run(["gh", "api", f"repos/{repo}/git/trees/{sha}?recursive=1"], capture_output=True, text=True)
    if r.returncode != 0:
        return "error: " + (r.stderr or r.stdout).strip()[:200]
    d = json.loads(r.stdout)
    if d.get("truncated"):
        return "truncated"
    save(repo, sha, [e["path"] for e in d["tree"] if e["type"] == "blob"],
         [e["path"] for e in d["tree"] if e["type"] == "commit"], "github-api")
    return "ok"


def from_git(repo: str, shas: list[str]) -> None:
    g = GIT_CACHE / (repo.replace("/", "__") + ".git")
    if not g.exists():
        subprocess.run(["git", "init", "-q", "--bare", str(g)], check=True)
    subprocess.run(["git", "-C", str(g), "fetch", "-q", "--filter=blob:none", "--depth=1",
                    f"https://github.com/{repo}.git", *shas], check=True)
    for sha in shas:
        out = subprocess.run(["git", "-C", str(g), "ls-tree", "-r", "--full-tree", sha],
                             capture_output=True, text=True, check=True).stdout
        blobs, subs = [], []
        for line in out.splitlines():
            meta, path = line.split("\t", 1)
            (blobs if meta.split()[1] == "blob" else subs).append(path)
        save(repo, sha, blobs, subs, "git")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    TREES.mkdir(exist_ok=True)
    with (HERE / "results" / "task_commits.tsv").open() as f:
        pairs = sorted({(r["repo"], r["base_commit"]) for r in csv.DictReader(f, delimiter="\t")})
    with ThreadPoolExecutor(args.workers) as ex:
        status = dict(zip(pairs, ex.map(from_api, pairs)))
    errors = {p: s for p, s in status.items() if s.startswith("error")}
    if errors:
        raise SystemExit(f"{len(errors)} commits failed, e.g. {next(iter(errors.items()))}")
    truncated = defaultdict(list)
    for (repo, sha), s in status.items():
        if s == "truncated":
            truncated[repo].append(sha)
    for repo, shas in truncated.items():
        from_git(repo, shas)
    n_trunc = sum(map(len, truncated.values()))
    print(f"{len(pairs)} commits: {len(pairs) - n_trunc} from the API or cache, {n_trunc} via shallow git fetch")


if __name__ == "__main__":
    main()
