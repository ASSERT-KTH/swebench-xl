# Task

## ESQL: FoldNull can wrongly fold COALESCE to null

Reproducer:
```
ROW x = null
| EVAL z = COALESCE(x, "1")
| EVAL append_coalesce = MV_APPEND("2", COALESCE(x, "1"))
| EVAL append_z = MV_APPEND("2", z)

       x       |       z       |append_coalesce|   append_z    
---------------+---------------+---------------+---------------
null           |1              |null           |[2, 1]   
```
`append_coalesce` should be the same as `append_z`.

Looking at the change logger output, it looks like the problem is inside `FoldNull`:

```
[2025-12-11T10:09:59,716][TRACE][o.e.x.e.o.L.changes      ] [runTask-0] Rule logical.FoldNull applied with change
Limit[1000[INTEGER],false,false]                                                                                      = Limit[1000[INTEGER],false,false]
\_Eval[[COALESCE(x{r}#14,1[KEYWORD]) AS z#17, MVAPPEND(2[KEYWORD],COALESCE(x{r}#14,1[KEYWORD])) AS append_coalesce#20 ! \_Eval[[COALESCE(x{r}#14,1[KEYWORD]) AS z#17, null[KEYWORD] AS append_coalesce#20, MVAPPEND(2[KEYWORD],z{r}#17) AS ap
, MVAPPEND(2[KEYWORD],z{r}#17) AS append_z#23]]                                                                       ! pend_z#23]]
  \_Row[[null[NULL] AS x#14]]                                                                                         =   \_Row[[null[NULL] AS x#14]]
```

We shouldn't have folded to null because `COALESCE(null, "1")` should be `"1"`.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cba13bc83e252cb3b3014cf4e74311b3433c89c1`
**Instance ID:** `elastic__elasticsearch-140028`
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
