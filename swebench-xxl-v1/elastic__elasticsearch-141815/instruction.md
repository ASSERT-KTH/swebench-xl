# Task

## Logging cancellation task with large number of nodes/actions

When canceling a possibly large list of actions / tasks, a possibly large amount of memory might be consumed at times as ES tries to log it by means of its description [CancelTasksRequest#getDescription](https://github.com/elastic/elasticsearch/blob/main/server/src/main/java/org/elasticsearch/action/admin/cluster/node/tasks/cancel/CancelTasksRequest.java#L80).
We should probably make sure the size of the underlying arrays doesn't become too big, and return a subset of the actions/nodes in the description when that's the case.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `96be973fb5687c9837f51352fd7c8c5d2a5894aa`
**Instance ID:** `elastic__elasticsearch-141815`
**Language:** `Java`
