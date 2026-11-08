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
| `tokenizer_core.py` | The shared tokenization core (walk/skip-list/chunking logic), ported from `tokenizer copy.py`. No Harbor dependency. |
| `tokenizer_agent.py` | The Harbor agent (`RepoTokenizerAgent`). Run this via `harbor run` against a Harbor dataset/environment. |
| `benchmark_size_stats.py` | Aggregates a job's per-instance results into mean/median/stdev. |
| `file_type_breakdown.py` | Groups a job's per-instance `by_extension` counts into file-type categories (source code, other code, docs, config/build, localization, data/fixtures, ...) per instance, per repo and per benchmark. Output lives in `results/file_types/`. |
| `file_type_report.py` | Writes the file-type report ([`results/file_types/README.md`](results/file_types/README.md)) and CSVs from those JSONs. |
| `jobs/` | The raw Harbor job output behind every number in `results/` — see [Raw run data](#raw-run-data). |
| `plot_token_size_boxplot.py` | Reads every `results/*.json` and prints a copy-paste-ready pgfplots figure: one horizontal boxplot (min/25th/median/75th/max) per benchmark, benchmarks on the y-axis, token count on a log-scale x-axis. |
| `tokenizer copy.py` | The original standalone tokenization script this agent's algorithm is ported from. Kept as-is for reference; not used by Harbor. |

## How it works

For each trial, `RepoTokenizerAgent.run()`:

1. **Locates the task's working directory** inside the environment — the
   `TESTBED_DIR` env var if set, else `/testbed` (the conventional path for
   file-graded, SWE-bench-style tasks) if present, else the agent user's
   default working directory (via `pwd -P`). Override explicitly with the
   `testbed_dir` agent kwarg if a task uses a different layout.
2. **Downloads that directory to the host** by archiving it inside the
   environment (skipping VCS/dependency/build noise — `.git`, `node_modules`,
   `venv`, `build`, `dist`, ...) and extracting that archive locally. This
   works against any Harbor environment backend (local Docker, remote
   sandboxes, etc.), not just ones with a directly mounted filesystem.
   Extraction uses tarfile's `"tar"` filter rather than Harbor's own
   `download_dir_with_exclusions` (which uses the stricter `"data"` filter):
   some repos ship test fixtures with a symlink to an absolute path on
   purpose (e.g. Helm's chart-loader tests symlink to `/dev/null` to test
   that case), and `"data"` refuses to extract those, failing the trial with
   `tarfile.AbsoluteLinkError` before tokenization even starts. Safe to
   relax here since we generate the archive ourselves from a container we
   already control — see `_download_repo` in `tokenizer_agent.py`.
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
     --agent tokenizer_agent:RepoTokenizerAgent \
     --disable-verification
   ```

   No `-m/--model` flag is needed — the agent doesn't call any LLM. For a
   local dataset directory, swap `-d "<org/dataset@version>"` for
   `-p "<path/to/dataset>"`.

   **`--disable-verification` is recommended.** This agent never attempts the
   task, so every trial's verifier reward is guaranteed to be a failing
   `0.0` regardless — running the task's test suite just to confirm that
   costs real time (and, for repos like SWE-bench's larger scientific-Python
   ones, it can dominate the run). Skipping it doesn't lose you anything this
   agent's stats depend on: `token_counts.json` and
   `AgentContext.metadata["repo_tokenizer"]` are both written during the
   agent phase, before verification would even run. The only visible effect
   is `result.json`'s `verifier_result` becoming `null` instead of a `0.0`
   reward.

   Note: `harbor job resume` (see below) doesn't expose this as a flag — to
   apply it to a resumed job you have to hand-edit `verifier: {"disable":
   true}` into that job's `config.json` before resuming.

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
  -a "tokenizer_agent:RepoTokenizerAgent" \
  --disable-verification
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

## Raw run data

`jobs/` holds the complete Harbor job directories of the runs that produced
`results/`, one per benchmark:

| Benchmark | Job directory | Original job name | Instances | Results |
| --- | --- | --- | ---: | --- |
| SWE-bench Verified | `jobs/verified` | `2026-08-31__12-35-16` | 500 | `results/verified.json` |
| SWE-bench Pro | `jobs/pro` | `2026-08-31__17-03-08` | 731 | `results/pro.json` |
| SWE-bench XL | `jobs/xl` | `2026-09-01__16-19-17` | 180 | `results/xl.json` |
| DeepSWE (DataCurve) | `jobs/deepswe` | `2026-08-31__16-09-55` | 113 | `results/deepswe.json` |

The directories were renamed from Harbor's timestamped job names after the
runs, so the `job_dir` field in `results/<benchmark>.json` and the job/trial
names inside Harbor's own `config.json`/`result.json` files still use the
original names.

Each job directory has Harbor's job-level `config.json`/`result.json`/
`job.log` plus one directory per instance (trial) containing:

- `agent/token_counts.json` — the raw measurement (totals, per-extension
  counts, 50 largest files) that every number in `results/` is computed from.
- `agent/trajectories/trajectory.json`, `config.json`, `result.json`,
  `lock.json`, `trial.log` — Harbor's record of the trial, including the exact
  task/dataset ref and Docker image used.
- `verifier/` (Verified only, which ran before `--disable-verification` was
  added) and `artifacts/`.

To recompute the published stats from it:

```bash
python benchmark_size_stats.py jobs/<benchmark> -o results/<benchmark>.json
```

This reproduces the published files exactly, except that it also adds a
`total_characters` field, which only the XL run recorded (it is `0` for the
other benchmarks).

## Token counts per file type

`results/file_types/<benchmark>.json` breaks the numbers in
`results/<benchmark>.json` down by file type. It is computed from the
`token_counts.json` files of the *same* jobs (no re-tokenization), so totals
are identical; the script asserts that every instance's categories sum to its
`total_tokens`/`total_files` and that `source_code` equals
`source_code_tokens`/`source_code_files`.

It is computed from the job directories in [`jobs/`](#raw-run-data):

```bash
python file_type_breakdown.py jobs/<benchmark> -o results/file_types/<benchmark>.json
```

DeepSWE instance ids don't encode the repository, so for it also pass
`--task-defs <dir>` with the job's task definitions downloaded at the refs it
ran against (see the script's docstring for the one-liner).

Then `python file_type_report.py` writes the report,
[`results/file_types/README.md`](results/file_types/README.md) (category
definitions, every extension per category, and the tables), plus CSVs for
figures.

Each JSON contains the extension -> category mapping used, benchmark-wide
stats per category (`tokens`, `files`, per-instance `token_share`, and the
size-weighted `pooled_token_share`), the same stats per repository, and every
instance's category counts plus its raw `by_extension` counts. Categories are
defined by file extension alone.
