# Task

## `DataCountsReporter` holds intrinsic lock while waiting for persistence, blocking job stats reads

### Summary
`DataCountsReporter.writeUnreportedCounts()` is `synchronized` and can block on `JobDataCountsPersister.persistDataCounts(..., mustWait=true)` which waits on latches. While this thread is waiting, it holds the `DataCountsReporter` intrinsic lock, blocking other threads that call `synchronized` methods on the same instance—most notably `runningTotalStats()`, which is used to serve `_ml/anomaly_detectors/_stats` / `GetJobsStats` requests (management threadpool). This shows up as intrinsic lock contention and parked threads in `CountDownLatch.await()`.

### Evidence / symptoms
Representative stack trace from a thread such as `ml_job_comms`:

- `DataCountsReporter.writeUnreportedCounts(DataCountsReporter.java:263)`
- `JobDataCountsPersister.persistDataCounts(JobDataCountsPersister.java:105)`
- `CountDownLatch.await(...)`

This indicates the thread is waiting for a previous counts persist to finish and/or waiting for its own persist callback to count down the latch, while still inside the `synchronized` method.

### Impact
- Increased latency / stalls when retrieving job stats (`GetJobsStats`, Kibana polling, monitoring collectors), because those code paths call `DataCountsReporter.runningTotalStats()` (also `synchronized`) and must wait for the lock.
- Contention is amplified when counts persistence is slow/backed up (e.g., slow results index writes, retries, shard issues, threadpool pressure), or when `writeUnreportedCounts()` is called frequently (e.g., `flushJob()`, `close()`).

### Key code references
- `DataCountsReporter.writeUnreportedCounts()` is `synchronized` and calls a potentially blocking persistence with `mustWait=true`:
  - `x-pack/plugin/ml/src/main/java/org/elasticsearch/xpack/ml/job/process/DataCountsReporter.java`
- `DataCountsReporter.runningTotalStats()` is also `synchronized` and is called to serve job stats:
  - `AutodetectCommunicator.getDataCounts()` → `runningTotalStats()`
  - `TransportGetJobsStatsAction` executes on the `MANAGEMENT` threadpool and uses `processManager.getStatistics()` which fetches `communicator.getDataCounts()`
- `JobDataCountsPersister.persistDataCounts()` waits on per-job latches (`previousLatch.await()`, `latch.await()`):
  - `x-pack/plugin/ml/src/main/java/org/elasticsearch/xpack/ml/job/persistence/JobDataCountsPersister.java`

### Why this looks like a bug / outlier
Elsewhere in the codebase, similar “wait for async work to finish” logic often avoids holding an intrinsic lock during blocking waits by copying the awaited handle under lock and waiting outside, e.g.:
- `ShortCircuitingRenormalizer.waitUntilIdle()` captures the latch in a synchronized block and calls `await()` outside the lock.

`DataCountsReporter` differs because the same lock gates both:
- waiting for persistence (`writeUnreportedCounts()`), and
- answering stats reads (`runningTotalStats()` used by management/stats APIs).

### Suggested resolution
Refactor `DataCountsReporter.writeUnreportedCounts()` to avoid blocking while holding the `DataCountsReporter` intrinsic monitor, e.g.:

- **Snapshot-under-lock, persist outside lock**:
  - Under `synchronized (this)`, copy `unreportedStats` to a local variable (and possibly set a state flag).
  - Release the lock.
  - Call `persistDataCounts(..., mustWait=true)` outside the lock.
  - Re-acquire lock to clear `unreportedStats` (or update it if persistence failed / was superseded).

Possible approaches:
- Replace the `synchronized` + field pattern with an `AtomicReference<DataCounts>` for `unreportedStats`, using CAS to avoid races.
- Keep `synchronized` but only for short critical sections; never call `await()` or persistence while holding the lock.

### Why the change is safe / desirable
- Preserves intent: ensure unreported counts are persisted eventually and serialized per job.
- Removes lock coupling between persistence delays and stats-read paths.
- Prevents management/stat requests from being blocked by slow indexing / retry backpressure in the results index.
- Aligns with safer concurrency patterns used elsewhere (capture awaited state under lock, wait outside).

### Reproduction / how to observe
- Force slow ML results index writes (e.g., heavy indexing load, shard relocation, delayed writes).
- Trigger frequent `flushJob()` and/or job close while concurrently polling job stats (`_ml/anomaly_detectors/_stats`).
- Observe thread dumps showing:
  - `ml_job_comms` parked in `JobDataCountsPersister.persistDataCounts` awaiting a latch inside `DataCountsReporter.writeUnreportedCounts()`, and
  - management threads blocked trying to enter `DataCountsReporter.runningTotalStats()`.

### Acceptance criteria
- `DataCountsReporter` no longer holds its monitor while waiting for persistence completion.
- Under persistence backpressure, stats reads do not block on `DataCountsReporter`’s intrinsic lock (or are significantly reduced), and thread dumps no longer show `runningTotalStats()` blocked behind `writeUnreportedCounts()` waiting on a latch.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `3ff6d2d3c1624fff18afdf6d9d5d63a684c8b6cf`
**Instance ID:** `elastic__elasticsearch-141519`
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
