"""Download the repository and base commit of every SWE-bench Verified and SWE-bench Pro instance.

Writes inputs/verified_commits.jsonl and inputs/pro_commits.jsonl (one JSON object per
line: instance_id, repo, base_commit). Pro uses the dataset's ``v1`` configuration (731
instances); its default configuration changed to a 642-instance set in September 2026.

Needs pyarrow, e.g.:  uv run --with pyarrow python fetch_hf_commits.py
"""
from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
DATASETS = {
    "verified": ("SWE-bench/SWE-bench_Verified", "default"),
    "pro": ("ScaleAI/SWE-bench_Pro", "v1"),
}


def parquet_urls(dataset: str, config: str) -> list[str]:
    url = f"https://huggingface.co/api/datasets/{dataset}/parquet/{config}/test"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def main() -> None:
    for name, (dataset, config) in DATASETS.items():
        rows = []
        for url in parquet_urls(dataset, config):
            with urllib.request.urlopen(url, timeout=300) as r:
                table = pq.read_table(io.BytesIO(r.read()), columns=["instance_id", "repo", "base_commit"])
            rows += table.to_pylist()
        out = HERE / "inputs" / f"{name}_commits.jsonl"
        out.write_text("".join(json.dumps(row) + "\n" for row in rows))
        print(f"{name}: {len(rows)} instances -> {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
