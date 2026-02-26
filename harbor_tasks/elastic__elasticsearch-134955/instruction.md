# Task

## Transforms will infinitely queue PIT closures causing a "PIT storm"

### Elasticsearch Version

8.16+

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

_any_

### Problem Description

Transforms when using point-in-time (PIT) search will create multiple PITs over the lifetime of a single transform pivot page. 

If there is any failure, or a new search is initiated, or the scheduled pivot completes, it will request the PITs to be deleted.

However, it will not wait for these PITs to be deleted before scheduling again or continuing with another set of searches. Consequently, its possible for many transforms, in quick succession, could create MANY PITs and cause a significant queue of close pit requests which can cause pressure on the system.

Transforms should wait for all its close-pit requests to complete before continuing its execution paths. Since close-pit "should" be fast, this should be OK. However, if close pit is slow, we want transforms to be naturally throttled to prevent a PIT storm.

### Steps to Reproduce

Have many transforms with PIT involved pointing at the same index patterns that point at hundreds of shards on single nodes
Have fast transform frequency
Watch it burn

### Current Workaround

PIT can be disabled for a transform:
```
POST _transform/<transform id>/_update
{
  "settings": {
    "use_point_in_time": false
  }
}
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1904abbb730ec6bfc47a58425a3949664013ed55`
**Instance ID:** `elastic__elasticsearch-134955`
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
