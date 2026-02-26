import json
import subprocess
from pathlib import Path
from collections import defaultdict
import os
import re
import requests
import shutil
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

def load_dataset():
    dataset_path = Path("../benchmark/dataset_new.jsonl")
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
    
    checkpoint_file = Path("build_stability_checkpoint.json")
    
    # Load checkpoint if exists
    build_results = defaultdict(list)
    processed_ids = set()
    if checkpoint_file.exists():
        print(f"Loading checkpoint from {checkpoint_file}")
        with open(checkpoint_file) as f:
            checkpoint_data = json.load(f)
            build_results = defaultdict(list, checkpoint_data["build_results"])
            processed_ids = set(checkpoint_data["processed_ids"])
        print(f"Resuming from checkpoint with {len(processed_ids)} instances already processed")
    
    for idx, instance_id in enumerate(tqdm(instance_ids, desc="Build Stability", unit="instance")):
        # Skip if already processed
        if instance_id in processed_ids:
            continue

        dockerfile = dockerfile_dir / f"{instance_id}/Dockerfile"
        
        # Attempt to build 3 times
        for attempt in tqdm(range(3), desc=f"  Builds for {instance_id}", unit="build", leave=False):
            if attempt > 0:
                # Remove previous image to ensure clean build
                subprocess.run(["docker", "rmi", f"es-bench-{instance_id}"], capture_output=True)
            image_tag = f"es-bench-{instance_id}"
            try:
                results = subprocess.run(
                    ["docker", "build", "--no-cache", "-f", str(dockerfile), "-t", image_tag, str(dockerfile_dir/instance_id)],
                    check=True,
                    capture_output=True,
                    timeout=600
                )
                if results.returncode == 0:
                    build_results[instance_id].append(True)
                else:
                    build_results[instance_id].append(False)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"Build failed for {instance_id} on attempt {attempt + 1} with exception {e}.")
                build_results[instance_id].append(False)
        
        processed_ids.add(instance_id)
        
        # Save checkpoint every 5 instances
        if (idx + 1) % 5 == 0:
            checkpoint_data = {
                "build_results": dict(build_results),
                "processed_ids": list(processed_ids)
            }
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
            print(f"\nCheckpoint saved at instance {idx + 1}/{len(instance_ids)}")
    
    # Save final checkpoint
    checkpoint_data = {
        "build_results": dict(build_results),
        "processed_ids": list(processed_ids)
    }
    with open(checkpoint_file, "w") as f:
        json.dump(checkpoint_data, f, indent=2)
    print(f"\nFinal checkpoint saved")
    
    # Filter: keep only instances that built successfully all 3 times
    stable_instances = {id for id, results in build_results.items() if all(results)}
    
    return stable_instances

# Layer 2: Oracle Consistency (Test Determinism)

def check_oracle_consistency(instance_ids):
    """Run eval.py on each instance multiple times to verify test determinism."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    eval_script = repo_root / "benchmark" / "eval.py"
    
    checkpoint_file = Path("oracle_consistency_checkpoint.json")
    
    # Load checkpoint if exists
    consistent_instances = set()
    processed_ids = set()
    if checkpoint_file.exists():
        print(f"Loading checkpoint from {checkpoint_file}")
        with open(checkpoint_file) as f:
            checkpoint_data = json.load(f)
            consistent_instances = set(checkpoint_data["consistent_instances"])
            processed_ids = set(checkpoint_data["processed_ids"])
        print(f"Resuming from checkpoint with {len(processed_ids)} instances already processed")
    
    for idx, instance_id in enumerate(tqdm(instance_ids, desc="Oracle Consistency", unit="instance")):
        # Skip if already processed
        if instance_id in processed_ids:
            continue
            
        print(f"Testing oracle consistency for {instance_id}...")
        run_results = []
        output_dir = repo_root / "swe-bench++tools" / "tmp" / "eval_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run eval 3 times
        for attempt in tqdm(range(3), desc=f"  Attempts for {instance_id}", unit="attempt", leave=False):
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
                        "--save_debug_dir",
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
                    if eval_results and eval_results.get(instance_id) is True:
                        run_results.append(True)
                        # Clean up debug dir on success
                        debug_dir = repo_root / f"debug_{instance_id}"
                        if debug_dir.exists():
                            shutil.rmtree(debug_dir)
                            print(f"Cleaned up debug directory for {instance_id}")
                    else:
                        print(f"Output mismatch for {instance_id} on attempt {attempt + 1}: {eval_results}")
                        run_results.append(False)
                        break  # No need to continue if we already have a failure
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Output JSON not found or invalid for {instance_id} on attempt {attempt + 1}: {e}")
                    run_results.append(False)
                    break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"Eval script failed for {instance_id} on attempt {attempt + 1}: {e}")
                if isinstance(e, subprocess.CalledProcessError):
                    print(f"stdout:\n{e.stdout}\n")
                    print(f"stderr:\n{e.stderr}\n")
                run_results.append(False)
                break  # No need to continue if we already have a failure

            #Delete output files to avoid confusion in next run
            finally:
                for output_file in output_dir.glob("*"):
                    output_file.unlink(missing_ok=True)
        
        # Keep only instances that pass all 3 runs
        if all(run_results):
            consistent_instances.add(instance_id)
        
        processed_ids.add(instance_id)
        
        # Save checkpoint every 5 instances
        if (idx + 1) % 5 == 0:
            checkpoint_data = {
                "consistent_instances": list(consistent_instances),
                "processed_ids": list(processed_ids)
            }
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
            print(f"\nCheckpoint saved at instance {idx + 1}/{len(instance_ids)}")
    
    # Save final checkpoint
    checkpoint_data = {
        "consistent_instances": list(consistent_instances),
        "processed_ids": list(processed_ids)
    }
    with open(checkpoint_file, "w") as f:
        json.dump(checkpoint_data, f, indent=2)
    print(f"\nFinal checkpoint saved")
    
    return consistent_instances

# Layer 3: Semantic Alignment & Automated Curation
# TODO: Currently I only check semantic alignment but skip the curation step.

def check_semantic_alignment(instances):
    OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

    OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

    LLM_MODEL = "google/gemini-2.5-flash"
    
    all_results = []
    high_quality_instances = set()
    
    for instance in tqdm(instances, desc="Semantic Alignment", unit="instance"):
        prompt = f"""You are an expert software engineering benchmark curator evaluating whether a GitHub issue and its corresponding tests are well-aligned for use in a coding benchmark.

## Problem Statement
Title: {instance['problem_statement_title']}
Description: {instance['problem_statement_description']}

## Test Oracle (tests that must pass after a correct fix)
{instance['test_patch']}

## Task
Evaluate the semantic alignment between the problem statement and the test oracle using the following rubric:

- **High Quality**: The tests directly and clearly validate the behavior described in the problem statement. A developer reading only the problem statement would naturally write these tests or very similar ones.
- **Medium Quality**: The tests partially capture the problem, but also test implementation details not explicitly requested (e.g., specific method names, accessor patterns, or internal behavior not mentioned in the issue). The core intent is still recoverable.
- **Low Quality**: The tests are misaligned, ambiguous, or test something fundamentally different from what the problem statement describes. A developer could not reasonably infer these tests from the problem statement alone.

Respond with a JSON object only, no markdown, with the following fields:
- "quality": one of "High", "Medium", or "Low"
- "reason": a concise 1-2 sentence explanation of your rating
"""
    
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
            "max_tokens": 512
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
                
                # Store result
                result_entry = {
                    "instance_id": instance["instance_id"],
                    "quality": analysis["quality"],
                    "reason": analysis["reason"]
                }
                all_results.append(result_entry)
                
                # Track high quality instances
                if analysis["quality"] == "High":
                    high_quality_instances.add(instance["instance_id"])
            else:
                print(f"LLM API error for {instance['instance_id']}: {response.status_code}")
                all_results.append({
                    "instance_id": instance["instance_id"],
                    "quality": "Error",
                    "reason": f"API error: {response.status_code}"
                })

        except Exception as e:
            print(f"Error analyzing {instance['instance_id']} with LLM: {e}")
            all_results.append({
                "instance_id": instance["instance_id"],
                "quality": "Error",
                "reason": f"Exception: {str(e)}"
            })
    
    # Save all results to JSON file
    with open("semantic_alignment_results_new.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nSaved semantic alignment results to semantic_alignment_results_new.json")
    
    return high_quality_instances

# (Optional, mayber for later use)Layer 4: False Negative Filtering (model breaking verification)

if __name__ == "__main__":
    instance_ids, instances = load_dataset()
    print(f"Loaded {len(instance_ids)} instances")
    print("\n" + "="*50)
    print("LAYER 3: Semantic Alignment Check")
    print("="*50)
    high_quality_instances = check_semantic_alignment(instances)
    print(f"\nHigh quality instances: {len(high_quality_instances)}/{len(instances)}")
    #save high quality instances to a jsonl file for later use
    with open("high_quality_instances_new.jsonl", "w") as f:
        for instance in instances:
            if instance["instance_id"] in high_quality_instances:
                f.write(json.dumps(instance) + "\n")

    """
    print("\n" + "="*50)
    print("LAYER 1: Build Stability Check")
    print("="*50)
    with open("high_quality_instances.jsonl") as f:
        high_quality_instances = [json.loads(line)["instance_id"] for line in f]
    #for instance in high_quality_instances:
    #    print(instance)
    #    print(instance["instance_id"])
    stable_instances = check_build_stability(high_quality_instances)
    print(f"\nStable instances: {len(stable_instances)}/{len(high_quality_instances)}")
    #save stable instances to a jsonl file for later use
    with open("stable_instances.jsonl", "w") as f:
        for instance in instances:
            print(instance)
            if instance["instance_id"] in stable_instances:
                f.write(json.dumps(instance) + "\n")
    
    print("\n" + "="*50)
    print("LAYER 2: Oracle Consistency Check")
    print("="*50)
    consistent_instances = check_oracle_consistency(stable_instances)
    print(f"\nConsistent instances: {len(consistent_instances)}/{len(stable_instances)}")
    #save final consistent instances to a jsonl file for later use
    with open("final_consistent_instances.jsonl", "w") as f:
        for instance in instances:
            if instance["instance_id"] in consistent_instances:
                f.write(json.dumps(instance) + "\n")
    """


#elastic__elasticsearch-141503