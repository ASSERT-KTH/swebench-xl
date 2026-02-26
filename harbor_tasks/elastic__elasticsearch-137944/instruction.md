# Task

## Add coerce support for histogram and exponential_histogram field mappers

We want to allow switching to the `exponential_histogram` field type for OTLP ingestion use cases without breaking backwards compatibility.
This can cause two kinds of problems:
 * exponential-histogram JSON documents are attempted to be ingested into indices which use the `histogram` type: This can happen e.g. if the index template for a data stream has been adjusted, but a rollover has not happened yet
 * histogram JSON documents are attempted to be ingested into indices using the `exponential_histogram` type: Happens for example due to older OpenTelemetry collector versions running in parallel with newer ones, which already adjusted the field type


We decided on adding support for [coerce](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/coerce) to the `histogram` and `exponential_histogram` field mappers to cover these use cases:
 * [x] accept exponential histogram fields on `histogram` fields and convert them to T-Digest for `coerce` https://github.com/elastic/elasticsearch/pull/137191
 * [x] accept histogram fields (assuming T-Digest content) on `exponential_histogram` fields and convert them to exponential histograms for `coerce` #137944

The `histogram` field type content can be either T-Digests or HDR histograms. We decided on assuming T-Digest to implement this feature for the following reasons:
 * T-Digest and exponential histograms support negative values, while HDR histograms do not
 * T-Digest is the kind used in classic Elastic APM and the current EDOT Collector (OTLP ingest)

For the conversion from exponential histogram to T-Digest we'll use the same algorithm already implemented by the elasticsearch OTLP metrics endpoint. For the conversion from T-Digest to exponential histograms, we'll use an algorithm which ideally inverts this conversion, introducing as little error as possible.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `2512d079948a33d9a6aa66d8992ab24e23ae479b`
**Instance ID:** `elastic__elasticsearch-137944`
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
