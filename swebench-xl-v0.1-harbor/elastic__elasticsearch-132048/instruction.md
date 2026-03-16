# Task

## [Transform] Stuck in Stopping

There is a chance that a Transform can get stuck in `Stopping` if it fails to update its status and register the indexer thread.
- [TransformTask](https://github.com/elastic/elasticsearch/blob/main/x-pack/plugin/transform/src/main/java/org/elasticsearch/xpack/transform/transforms/TransformTask.java#L303) updates the cluster state with the Transform's persistent Task. If that update fails, the persistent task will remain alive but the Transform indexer thread gets marked as `Stopped`.
- [TransformStats](https://github.com/elastic/elasticsearch/blob/main/x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/transform/transforms/TransformStats.java#L244) displays a `Stopped` indexer as `Stopping`, because the persistent task exists but the indexer thread is not running.

Workaround:
- Stop the Transform with `?force=true`, which will remove the persistent task
- Start the Transform

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4d1b7a69cd93c89a95013d3cb4deda12e22e2ec8`
**Instance ID:** `elastic__elasticsearch-132048`
**Language:** `Java`
