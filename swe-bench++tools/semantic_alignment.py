import argparse
import json
import os
import re
import time

import requests
from tqdm import tqdm

import dotenv

dotenv.load_dotenv()

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"


def _strip_code_fence(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _build_prompt(instance):
    title = instance.get("problem_statement_title", "")
    description = instance.get("problem_statement_description", "")
    patch = instance.get("patch", "")
    test_patch = instance.get("test_patch", "")

    return f"""You are an expert software engineering benchmark curator evaluating whether a GitHub issue and its corresponding code/test changes are well-aligned for use in a coding benchmark.

## Problem Statement
Title: {title}
Description: {description}

## Source Patch (fix implementation)
{patch}

## Test Oracle Patch (tests that should validate the fix)
{test_patch}

## Task
Evaluate the semantic alignment between the problem statement, source patch, and test oracle patch using the following rubric:

- **High Quality**: The tests and patch directly and clearly implement/validate the behavior described in the problem statement. A developer reading only the problem statement would naturally produce a very similar fix and tests.
- **Medium Quality**: The tests and patch partially capture the problem, but include notable implementation details not clearly implied by the issue. The core intent is still mostly recoverable.
- **Low Quality**: The tests and/or patch are misaligned, ambiguous, or target behavior that differs from the stated issue. A developer could not reasonably infer these changes from the problem statement alone.

Respond with a JSON object only, no markdown, with the following fields:
- "quality": one of "High", "Medium", or "Low"
- "reason": a concise 1-2 sentence explanation of your rating
"""


def check_semantic_alignment(instances, model=DEFAULT_MODEL, timeout=45, sleep_seconds=0.0):
    api_key = os.environ["OPENROUTER_API_KEY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    all_results = []

    for instance in tqdm(instances, desc="Semantic Alignment", unit="instance"):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": _build_prompt(instance)}],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            response = requests.post(
                f"{OPENROUTER_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )

            if response.status_code == 200:
                result = response.json()
                llm_response = result["choices"][0]["message"]["content"]
                analysis = json.loads(_strip_code_fence(llm_response))

                quality = analysis.get("quality", "Error")
                reason = analysis.get("reason", "Missing reason in model response")

                all_results.append(
                    {
                        "instance_id": instance.get("instance_id", "unknown_instance"),
                        "quality": quality,
                        "reason": reason,
                    }
                )
            else:
                all_results.append(
                    {
                        "instance_id": instance.get("instance_id", "unknown_instance"),
                        "quality": "Error",
                        "reason": f"API error: {response.status_code}",
                    }
                )
        except Exception as exc:
            all_results.append(
                {
                    "instance_id": instance.get("instance_id", "unknown_instance"),
                    "quality": "Error",
                    "reason": f"Exception: {str(exc)}",
                }
            )

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return all_results


def _load_verified_instances(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        instances = json.load(f)

    verified = [
        item
        for item in instances
        if item.get("status") == "verified"
        and item.get("problem_statement_title")
        and item.get("problem_statement_description")
        and item.get("patch")
        and item.get("test_patch")
    ]
    return verified


def main():
    parser = argparse.ArgumentParser(
        description="Rate semantic alignment for verified benchmark instances via OpenRouter."
    )
    parser.add_argument(
        "--input",
        default="../benchmark-pipeline/validated_instances.json",
        help="Path to validated_instances.json",
    )
    parser.add_argument(
        "--output",
        default="semantic_alignment_results_new.json",
        help="Path to output JSON results file",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="OpenRouter model name",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional delay between requests to reduce rate limits",
    )
    args = parser.parse_args()

    verified_instances = _load_verified_instances(args.input)
    print(f"Loaded {len(verified_instances)} verified instances from {args.input}")

    results = check_semantic_alignment(
        verified_instances,
        model=args.model,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Saved semantic alignment results to {args.output}")


if __name__ == "__main__":
    main()