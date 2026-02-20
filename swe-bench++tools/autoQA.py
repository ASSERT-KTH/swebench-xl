import json
import subprocess
from pathlib import Path
from collections import defaultdict
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

def load_dataset():
    dataset_path = Path("../benchmark/dataset.jsonl")
    instance_ids = []
    instances = []
    with open(dataset_path) as f:
        for line in f:
            instance = json.loads(line)
            instance_ids.append(instance["instance_id"])
            instances.append(instance)
            
    return instance_ids, instances
    
    

# This is the Automated Quality Assurance (autoQA) script based on the methodology in SWE-Bench++.
# Layer 1: Envrionment Determinism (Build Stability)

def check_build_stability(instance_ids):
    """Build each Dockerfile 3 times and filter out unstable builds."""
    dockerfile_dir = Path("../benchmark/dockerfiles/instances")
    
    
    build_results = defaultdict(list)
    
    for instance_id in instance_ids[0:1]:

        dockerfile = dockerfile_dir / f"{instance_id}/Dockerfile"
        
        # Attempt to build 3 times
        for attempt in range(3):
            print(f"Building {instance_id}, attempt {attempt + 1}...")
            try:
                results = subprocess.run(
                    ["docker", "build", "-f", str(dockerfile), "-t", f"{instance_id}:attempt{attempt}", str(dockerfile_dir)],
                    check=True,
                    capture_output=True,
                    timeout=600
                )
                if results.returncode == 0:
                    build_results[instance_id].append(True)
                else:
                    build_results[instance_id].append(False)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                build_results[instance_id].append(False)
    
    # Filter: keep only instances that built successfully all 3 times
    stable_instances = {id for id, results in build_results.items() if all(results)}
    
    return stable_instances

# Layer 2: Oracle Consistency (Test Determinism)

def check_oracle_consistency(instance_ids):
    """Run eval.py on each instance multiple times to verify test determinism."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    eval_script = repo_root / "benchmark" / "eval.py"
    consistent_instances = set()
    
    for instance_id in instance_ids:
        print(f"Testing oracle consistency for {instance_id}...")
        run_results = []
        output_dir = repo_root / "swe-bench++tools" / "tmp" / "eval_output"
        
        # Run eval 3 times
        for attempt in range(3):
            print(f"Running eval for {instance_id}, attempt {attempt + 1}...")
            try:
                run_result = subprocess.run(
                    [
                        "python",
                        str(eval_script),
                        "--instances",
                        instance_id,
                        "--patches",
                        str(repo_root / "benchmark" / "gold_patches.json"),
                        "--output_dir",
                        str(output_dir),
                        "--allow_network",
                    ],
                    check=True,
                    capture_output=True,
                    cwd=str(repo_root),
                    timeout=800
                )

                # Check JSON for output results
                try:
                    with open(output_dir/f"eval_summary_gold.json") as f:
                        eval_results = json.load(f)
                    if eval_results and eval_results.get(instance_id):
                        run_results.append(True)
                    else:
                        run_results.append(False)
                except (FileNotFoundError, json.JSONDecodeError):
                    print(f"Output JSON not found or invalid for {instance_id} on attempt {attempt + 1}")
                    run_results.append(False)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"Eval script failed for {instance_id} on attempt {attempt + 1}: {e}")
                if isinstance(e, subprocess.CalledProcessError):
                    print(f"stdout:\n{e.stdout}\n")
                    print(f"stderr:\n{e.stderr}\n")
                run_results.append(False)
        
        # Keep only instances that pass all 3 runs
        if all(run_results):
            consistent_instances.add(instance_id)
    
    return consistent_instances

# Layer 3: Semantic Alignment & Automated Curation
# TODO: Currently I only check semantic alignment but skip the curation step.

def check_semantic_alignment(instaces):
    print("Not running semantic alignment yet - placeholder for LLM-based analysis of PRs to determine suitability for benchmarking. This will involve prompting an LLM with PR data and parsing its response to filter for semantically suitable PRs.")
    pass
    OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

    OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

    LLM_MODEL = "google/gemini-2.5-flash"
    
    for instance in instances:
        prompt = f"Given this problem stated in a PR: {instance}" #TODO: complete this prompt
    
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
            return None

    except Exception as e:
        print(f"Error analyzing with LLM: {e}")
        return None

# (Optional, mayber for later use)Layer 4: False Negative Filtering (model breaking verification)

if __name__ == "__main__":
    instance_ids, instances = load_dataset()
    stable_instances = check_build_stability(instance_ids)
    print("Stable instances:", stable_instances)
    consistent_instances = check_oracle_consistency(stable_instances)
    print("Consistent instances:", consistent_instances)