# Harbor repo-size tokenizer agent

A [Harbor](https://www.harborframework.com/docs/agents) agent that measures how
*large* a benchmark instance is instead of trying to solve it. Point it at a
dataset with `harbor run` and, for every task, it tokenizes the task's
repository with [`tiktoken`](https://github.com/openai/tiktoken) and records
how many tokens (and files) that repository contains — total, and restricted
to source code.

It never edits, runs, or reads any test related to the task. It's purely an
instrumentation agent for answering "how big is this benchmark, instance by
instance, and on average?"

## Files

| File | Purpose |
| --- | --- |
| `tokenizer_agent.py` | The Harbor agent (`RepoTokenizerAgent`). Run this via `harbor run`. |
| `benchmark_size_stats.py` | Standalone script that aggregates a completed job's per-instance results into mean/median/stdev. |
| `tokenizer copy.py` | The original standalone tokenization script this agent's algorithm is ported from. Kept as-is for reference; not used by Harbor. |

## How it works

For each trial, `RepoTokenizerAgent.run()`:

1. **Locates the task's working directory** inside the environment — the
   `TESTBED_DIR` env var if set, else `/testbed` (the conventional path for
   file-graded, SWE-bench-style tasks) if present, else the agent user's
   default working directory (via `pwd -P`). Override explicitly with the
   `testbed_dir` agent kwarg if a task uses a different layout.
2. **Downloads that directory to the host** with
   `BaseEnvironment.download_dir_with_exclusions`, skipping VCS/dependency/
   build noise (`.git`, `node_modules`, `venv`, `build`, `dist`, ...). This
   works against any Harbor environment backend (local Docker, remote
   sandboxes, etc.), not just ones with a directly mounted filesystem.
3. **Tokenizes every text file** with `tiktoken` (`cl100k_base` by default,
   override via `TIKTOKEN_ENCODING` or the `encoding_name` agent kwarg),
   chunking large files to avoid tiktoken's regex backtracking on
   pathological input. Binary/media/lock-file extensions are skipped. This is
   the same walk/skip-list/chunking logic as `tokenizer copy.py`, just fed a
   locally downloaded copy of the repo instead of a directly mounted path.
4. **Writes results using Harbor's own conventions** — see below.

The agent never mutates the task's files and makes no LLM calls, so it has no
`model_name` requirement and there's nothing for a task's verifier to grade
(expect a failing/zero reward — that's expected; this agent isn't attempting
the task).

## Where the stats land

**Per trial** (i.e. per benchmark instance), written to the trial's own
Harbor-standard output locations:

- `<trial_dir>/agent/token_counts.json` — the detailed report: total/source-code
  token and file counts, a full per-extension breakdown, and the top 50
  largest files by token count.
- `<trial_dir>/agent/trajectories/trajectory.json` — a schema-valid [ATIF](https://www.harborframework.com/docs/agents)
  trajectory with a single deterministic step (`llm_call_count: 0`, since no
  LLM is involved) whose `final_metrics.extra` carries the summary counts.
- `<trial_dir>/result.json` — Harbor's own per-trial result file. The agent
  populates `AgentContext.metadata["repo_tokenizer"]` with the summary
  counts, so they show up here alongside every other trial's standard
  fields without needing to open a separate file.

**Across the whole benchmark**, run `benchmark_size_stats.py` against the job
directory once `harbor run` finishes:

```bash
python benchmark_size_stats.py jobs/<your-job>
```

This walks every trial under the job, reads each `token_counts.json`, and
writes `jobs/<your-job>/benchmark_size_stats.json` — sitting right next to
Harbor's own `result.json`/`config.json`/`lock.json` for that job — containing
the mean, median, population standard deviation, min, max, and sum for
`total_tokens`, `source_code_tokens`, `total_files`, and `source_code_files`
across every instance, plus a per-instance table sorted by size. It also
prints that table to stdout. Harbor's built-in job metrics (`Mean`/`Max`/...)
only aggregate verifier rewards, not agent-produced numbers like these, which
is why this is a separate script rather than a `--metrics` config.

## Usage

1. Install Harbor and `tiktoken` (this agent's only extra dependency) wherever
   you run `harbor run`:

   ```bash
   uv tool install harbor
   uv pip install tiktoken   # or: pip install tiktoken
   ```

2. Run it against a dataset. `harbor run` imports the agent as a Python
   module (`module.path:ClassName`), so the directory containing
   `tokenizer_agent.py` needs to be importable — the simplest way is to run
   from this directory, or add it to `PYTHONPATH`:

   ```bash
   PYTHONPATH="$(pwd)" harbor run -d "<org/dataset@version>" \
     --agent tokenizer_agent:RepoTokenizerAgent
   ```

   No `-m/--model` flag is needed — the agent doesn't call any LLM. For a
   local dataset directory, swap `-d "<org/dataset@version>"` for
   `-p "<path/to/dataset>"`.

   Optional agent kwargs (via `--ak key=value`):
   - `--ak testbed_dir=/some/other/path` — skip auto-discovery.
   - `--ak encoding_name=o200k_base` — use a different tiktoken encoding.

3. Once the job finishes, aggregate the results:

   ```bash
   python benchmark_size_stats.py jobs/<your-job>
   ```

   (Harbor prints the job directory path when the run completes, e.g.
   `Inspect results by running harbor view jobs/<your-job>`.)

## Sanity check: 10 instances of SWE-bench Verified

A small, fast run to confirm everything is wired up correctly before pointing
this at a full benchmark. `swebench-verified@1.0` is the dataset's actual
registered name in Harbor's registry (check with `harbor dataset list
--legacy` if it ever changes). Requires Docker running locally, since that's
Harbor's default environment backend.

```bash
cd tokenizer-agent   # this directory, so tokenizer_agent.py is importable
PYTHONPATH="$(pwd)" harbor run \
  -d "swebench-verified@1.0" \
  -l 10 \
  -a "tokenizer_agent:RepoTokenizerAgent"
```

- `-l 10` (`--n-tasks`) caps the run to the first 10 tasks. To pin specific
  instances instead, add `-i` (`--include-task-name`) once per instance ID
  (glob patterns work too), e.g. `-i "django__django-11099"`.
- No `-m/--model` flag — the agent makes no LLM calls.
- This writes a job directory under `./jobs/` by default (override with
  `-o/--jobs-dir`).

You can check the command resolves without launching anything (no Docker
needed) with `--print-config`:

```bash
PYTHONPATH="$(pwd)" harbor run -d "swebench-verified@1.0" -l 10 \
  -a "tokenizer_agent:RepoTokenizerAgent" --print-config
```

Once the 10-instance run finishes, aggregate it the same way as any other job:

```bash
python benchmark_size_stats.py jobs/<the-job-that-just-ran>
```

With only 10 instances the mean/median/stdev are just a smoke test, not a
meaningful benchmark-wide estimate — rerun without `-l` (or with a larger
value) for real numbers.
