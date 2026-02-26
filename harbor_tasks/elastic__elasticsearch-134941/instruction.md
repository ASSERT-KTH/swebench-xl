# Task

## Revisit automatic rollover criteria for tiny retentions

### Description

Currently when using DLM, the rollover criteria have an "automatic" part which adjusts the `max_age` depending on the retention of the data stream itself:

- If retention is null aka infinite (default), max_age will be 30 days
- If retention is configured to anything lower than 14 days, max_age will be 1 day
- If retention is configured to anything lower than 90 days, max_age will be 7 days
- If retention is configured to anything greater than 90 days, max_age will be 30 days

This works well for data stream data, which usually has a long-ish retention. However, in the case of the failure store, it's possible that we may only want to keep data for 1 day, in which case we're potentially keeping up to 50gb of failures in the "hot" tier when it could be moved off. Some users may only want to keep failures for a few hours.

We should consider whether we should adjust these criteria to have a smaller `max_age` for tiny retentions (something like rolling over every 6 hours for a 1 day retention, for example).

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d9783aded0854f34276f3a1ed4ec371b11303440`
**Instance ID:** `elastic__elasticsearch-134941`
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
