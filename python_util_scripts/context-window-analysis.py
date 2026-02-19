from transformers import AutoTokenizer
import os
import json
import matplotlib.pyplot as plt

tokenizer = AutoTokenizer.from_pretrained("moonshotai/Kimi-K2.5", trust_remote_code=True)

ELASTICSEARCH_PATH = "/Users/pontusberglund/Documents/GitHub/elasticsearch"
ELASTICSEARCH_FILE_EXTENSIONS = ('.java')

REPO_PATH = "/Users/pontusberglund/Documents/GitHub/"

SWE_BENCH_VERIFIED_REPOS = [
    "astropy/astropy",
    "django/django",
    "matplotlib/matplotlib",
    "mwaskom/seaborn",
    "pallets/flask",
    "psf/requests",
    "pydata/xarray",
    "pylint-dev/pylint",
    "pytest-dev/pytest",
    "scikit-learn/scikit-learn",
    "sphinx-doc/sphinx",
    "sympy/sympy"
]

CONTEXT_WINDOW_SIZE = {
    "Gemini 3 Pro Preview": 1050000,
    "Claude 4 Sonnet": 1000000,
    "Claude 4.5 Opus": 200000,
    "GPT-5.2 Codex": 400000,
    "Kimi K2 Thinking": 262100,
}

OUTPUT_FILE = "../data/token_counts.json"

def clone_repo(repo_url, dest_path):
    if os.path.exists(dest_path):
        print(f"Directory {dest_path} already exists. Skipping clone.")
        return
    os.system(f"git clone {repo_url} {dest_path}")

def count_tokens_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return len(tokenizer.encode(content))

def walk_and_count_tokens(repo_path, file_extensions=None):
    total_tokens = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file_extensions is None or file.endswith(file_extensions):
                file_path = os.path.join(root, file)
                tokens_in_file = count_tokens_in_file(file_path)
                total_tokens += tokens_in_file
    return total_tokens

if __name__ == "__main__":
    print("Cloning SWE-Bench verified repos")
    for repo in SWE_BENCH_VERIFIED_REPOS:
        print(f"Cloning {repo}...")
        clone_repo(f"https://github.com/{repo}.git", REPO_PATH + repo)
        
    print("\nCounting tokens in SWE-Bench verified repos (filtered by extensions .py)...")
    
    total_tokens = {}
    if os.path.exists(OUTPUT_FILE):
        print(f"{OUTPUT_FILE} already exists. Loading existing token counts.")
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            total_tokens = json.load(f)
    else:
        total_tokens = {}
        for repo in SWE_BENCH_VERIFIED_REPOS:
            repo_path = REPO_PATH + repo
            tokens_in_repo = walk_and_count_tokens(repo_path, file_extensions=('.py',))
            total_tokens[repo] = tokens_in_repo
            print(f"Tokens in {repo}: {tokens_in_repo}")
    
    total_tokens["elasticsearch"] = walk_and_count_tokens(ELASTICSEARCH_PATH, file_extensions=ELASTICSEARCH_FILE_EXTENSIONS)
    print("Tokens in elasticsearch (filtered by extensions .java, .gradle, .xml):", total_tokens["elasticsearch"])
    
    

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(total_tokens, f, indent=2)
        print(f"\nToken counts saved to {OUTPUT_FILE}")

    print("\nCalculating context window percentages:")
    for model_name, context_window in CONTEXT_WINDOW_SIZE.items():
        print(f"\nModel: {model_name}")
        percentages = []
        repos = []
        for repo, token_count in total_tokens.items():
            percentage = (context_window / token_count) * 100 if token_count > 0 else 0
            print(f"{repo}: {percentage:.2f}%")

### REPOS IN SWE-BENCH VERIFIED:
# SOURCE: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/viewer/default/test?p=4
# 1. astropy/astropy
# 2. django/django
# 4. matplotlib/matplotlib
# 5. mwaskom/seaborn
# 6. pallets/flask
# 7. psf/requests
# 8. pydata/xarray
# 9. pylint-dev/pylint
# 10. pytest-dev/pytest
# 11. scikit-learn/scikit-learn
# 12. sphinx-doc/sphinx
# 13. sympy/sympy

# RESULTS:
# Model: Claude 4.5 Opus
# astropy/astropy: 5.54%
# django/django: 4.90%
# matplotlib/matplotlib: 7.74%
# mwaskom/seaborn: 40.92%
# pallets/flask: 148.43%
# psf/requests: 232.33%
# pydata/xarray: 11.67%
# pylint-dev/pylint: 23.20%
# pytest-dev/pytest: 25.01%
# scikit-learn/scikit-learn: 5.38%
# sphinx-doc/sphinx: 17.28%
# sympy/sympy: 2.39%
# elasticsearch: 0.44%