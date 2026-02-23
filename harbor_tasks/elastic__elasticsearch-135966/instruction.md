# Task

## [ML] Ensure queued AbstractRunnables are notified when executor stops

AbstractProcessWorkerExecutorService.notifyQueueRunnables() was making an incorrect assumption that all AbstractRunnables that were submitted for execution would be queued as AbstractRunnables. However, PriorityProcessWorkerExecutorService wraps AbstractRunnables in OrderedRunnable before queueing them, and since OrderedRunnable is not an AbstractRunnable, these were skipped when notifyQueueRunnables() drained the queue, leading to potential hangs.

- Refactor notifyQueueRunnables() to allow PriorityProcessWorkerExecutorService to notify the AbstractRunnable contained within queued OrderedRunnables
- Ensure that notifyQueueRunnables() is called and the executor marked as shut down if an exception is thrown from start()
- Add unit tests

Closes #134651

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e47b044350304ad67d26f816453ccca3e492da85`
**Instance ID:** `elastic__elasticsearch-135966`
**Language:** `Java`
