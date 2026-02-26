# Task

## ES|QL: FUSE unbounded input with subqueries

For FUSE, we currently have a validation that check that a PipelineBreaker exists before FUSE.
Ideally we should check for LIMIT specifically.

The problem is that the current check does not account when a non-unary plan is used before FUSE, because we use `forEachUp`:

https://github.com/elastic/elasticsearch/blob/bc134a8b7fb2d31d6d96c8edc79e9a3ff2158572/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/fuse/FuseScoreEval.java#L168-L184

Because subqueries don't have an implicit LIMIT, this check can pass if at least one of the subqueries has a LIMIT.

For example, for this query, we don't return a validation error, when we clearly should because the first subquery is unbounded:

```
FROM (FROM books METADATA _score, _id, _index | EVAL x="1"),
     (FROM books METADATA _score, _id, _index | LIMIT 3 | EVAL x = "2")
| FUSE LINEAR GROUP BY x  WITH {"normalizer": "minmax"}
| KEEP x, title, _score
```

Because we are using linear combination with a score normalizer, the operator needs to collect all the input pages, before it can output rows. This can lead to circuit breaker exception in case we have too many pages coming from the first subquery.

FUSE was always meant to be used on a limited number of rows, because it implements hybrid search ranking algorithms that are applied after a first stage retrieval.
FUSE is not meant to be used on potentially the whole corpus of documents coming from an index.

As a side note, MMR will have a similar problem.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8c9f9b777d9b1c66fa09f0853e66ab7a0809ba33`
**Instance ID:** `elastic__elasticsearch-141523`
**Language:** `Java`

You can execute bash commands and edit files to implement the necessary changes.

## Recommended Workflow

This workflows should be done step-by-step so that you can iterate on your 
changes and any possible problems.

1. Analyze the codebase by finding and reading relevant files
2. Create a script to reproduce the issue
3. Edit the source code to resolve the issue
4. Verify your fix works by running your script again
5. Test edge cases to ensure your fix is robust
6. Submit your changes and finish your work by issuing the following command: 
`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.
   Do not combine it with any other command. <important>After this command, you 
cannot continue working on this task.</important>

## Important Rules

1. Every response must contain exactly one action
2. The action must be enclosed in triple backticks
3. Directory or environment variable changes are not persistent. Every action is
executed in a new subshell.
   However, you can prefix any action with `MY_ENV_VAR=MY_VALUE cd 
/path/to/working/dir && ...` or write/load environment variables from files

<system_information>
Linux 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun  5 
18:30:46 UTC 2025 x86_64
</system_information>

## Formatting your response

Here is an example of a correct response:

<example_response>
THOUGHT: I need to understand the structure of the repository first. Let me 
check what files are in the current directory to get a better understanding of 
the codebase.

```bash
ls -la
```
</example_response>

## Useful command examples

### Create a new file:

```bash
cat <<'EOF' > newfile.py
import numpy as np
hello = "world"
print(hello)
EOF
```

### Edit files with sed:```bash
# Replace all occurrences
sed -i 's/old_string/new_string/g' filename.py

# Replace only first occurrence
sed -i 's/old_string/new_string/' filename.py

# Replace first occurrence on line 1
sed -i '1s/old_string/new_string/' filename.py

# Replace all occurrences in lines 1-10
sed -i '1,10s/old_string/new_string/g' filename.py
```

### View file content:

```bash
# View specific lines with numbers
nl -ba filename.py | sed -n '10,20p'
```

### Any other command you want to run

```bash
anything
```
