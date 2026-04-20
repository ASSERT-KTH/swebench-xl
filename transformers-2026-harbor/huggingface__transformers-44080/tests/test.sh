#!/bin/bash

# Reset test-patch files to base-commit state (auto-injected)
python3 /tests/reset_test_files.py
set -euo pipefail

# ── Harbor test.sh for transformers (pytest) ──────────────────────────────────
#
# This script is called by the harbor verifier. Steps:
#   1. Apply the test_patch (new / modified tests)
#   2. Run the tests via run_script.sh
#   3. Parse JUnit XML results → output.json
#   4. Evaluate pass / fail against fail_to_pass + pass_to_pass lists
#   5. Write reward (0 or 1) to /logs/verifier/reward.txt

CONFIG_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="/app"
LOG_DIR="/logs/verifier"
REPORT_DIR="/app/test-results"
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# ── 1. Apply the test patch ──────────────────────────────────────────────────
cd "$REPO_DIR"
python3 -c "
import json, subprocess, sys, tempfile, os
with open('$CONFIG_DIR/config.json') as f:
    config = json.load(f)
test_patch = config.get('test_patch', '').strip()
if not test_patch:
    sys.exit(0)
if not test_patch.endswith(chr(10)):
    test_patch += chr(10)
with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tmp:
    tmp.write(test_patch)
    tmp_path = tmp.name
result = subprocess.run(['git', 'apply', '--verbose', tmp_path], capture_output=True, text=True)
os.unlink(tmp_path)
if result.returncode != 0:
    print('WARNING: git apply for test_patch failed, trying patch --fuzz=5', file=sys.stderr)
    print(result.stderr, file=sys.stderr)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tmp:
        tmp.write(test_patch)
        tmp_path = tmp.name
    subprocess.run(['patch', '--batch', '--fuzz=5', '-p1', '-i', tmp_path])
    os.unlink(tmp_path)
else:
    print('test_patch applied successfully')
    print(result.stdout)
"

# ── 2. Run the tests ────────────────────────────────────────────────────────
echo "Running tests..."

# Fix ownership for non-root user
chown -R app:app /app 2>/dev/null || true

export PATH="/opt/venv/bin:$PATH"
export HF_HUB_DOWNLOAD_TIMEOUT=60
export TOKENIZERS_PARALLELISM=false

su -s /bin/bash -c 'cd /app && export PATH="/opt/venv/bin:$PATH" && bash '"$CONFIG_DIR"'/run_script.sh' app \
    > "$LOG_DIR/test_output.log" 2>&1 || true

# ── 3. Parse results ────────────────────────────────────────────────────────
echo "Parsing test results..."
python3 "$CONFIG_DIR/parser.py" \
    --report-dir "$REPORT_DIR" \
    --output "$LOG_DIR/output.json" 2>&1 || {
    echo '{"passed": [], "failed": []}' > "$LOG_DIR/output.json"
}

# ── 4. Evaluate ─────────────────────────────────────────────────────────────
echo "Evaluating results..."
python3 -c "
import json, sys

config = json.load(open('$CONFIG_DIR/config.json'))
results = json.load(open('$LOG_DIR/output.json'))

f2p = set(config.get('fail_to_pass', []))
p2p = set(config.get('pass_to_pass', []))
passed = set(results.get('passed', []))
failed = set(results.get('failed', []))

# All fail_to_pass tests must now pass
f2p_ok = f2p.issubset(passed)
# No pass_to_pass test should fail
p2p_ok = len(p2p & failed) == 0

reward = 1 if (f2p_ok and p2p_ok and len(f2p) > 0) else 0

f2p_label = 'PASS' if f2p_ok else 'FAIL'
p2p_label = 'PASS' if p2p_ok else 'FAIL'
print(f'fail_to_pass ({len(f2p)}): {f2p_label}')
print(f'  expected pass: {sorted(f2p)}')
print(f'  actually passed: {sorted(f2p & passed)}')
print(f'  still failing: {sorted(f2p - passed)}')
print(f'pass_to_pass ({len(p2p)}): {p2p_label}')
print(f'  newly broken: {sorted(p2p & failed)}')
print(f'reward: {reward}')

if reward == 1:
    print('\nRESULT: PASSED')
else:
    print('\nRESULT: FAILED')
    if f2p - passed:
        print(f'  fail_to_pass not satisfied: {sorted(f2p - passed)}')
    if p2p & failed:
        print(f'  pass_to_pass broken: {sorted(p2p & failed)}')

with open('$LOG_DIR/reward.txt', 'w') as f:
    f.write(str(reward))
sys.exit(0 if reward == 1 else 1)
"
