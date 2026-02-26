# Task

## Excessive heap usage of post-snapshot-delete index metadata cleanup

Today `RepositoryData#indexMetaDataToRemoveAfterRemovingSnapshots` constructs a `HashMap<IndexId, HashSet<String>>` identifying every index metadata blob to be removed after deleting some collection of snapshots. This data structure can in theory be arbitrarily large, and in practice has been seen to consume many GiBs of heap in a cluster in which snapshotting was disrupted for an extended period of time in a way that prevented snapshots from being deleted and then the disruption was removed.

I believe we don't need to construct this data structure up-front at all, because these days `BlobContainer#deleteBlobsIgnoringIfNotExists` accepts an iterator over blob names from which it constructs the delete-blob requests progressively. It's not essential to deduplicate the blob names since deleting a blob multiple times is acceptable, but it would also seem reasonable to construct each per-index `HashSet<String>` as needed. Note that this would mean retaining `RepositoryData#indexMetaDataGenerations` for longer, past the end of the snapshot delete, so we should make sure there's enough backpressure to stop a buildup of excessively many of these things.

Alternatively, we could generalize `ShardBlobsToDelete` slightly to keep track of both shard-data and index-metadata blobs to be deleted, enforcing a strict bound on the memory footprint of all this data, and preferring to leak some blobs rather than sending the node OOM.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `be581a524408b1b4242456c75824d27791ceee03`
**Instance ID:** `elastic__elasticsearch-140394`
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
