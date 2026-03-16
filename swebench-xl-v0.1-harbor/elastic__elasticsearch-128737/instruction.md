# Task

## React more promptly to task cancellation while waiting for the cluster to unblock

Both in `TransportLocalClusterStateAction` and `TransportMasterNodeAction` we wait for the cluster to unblock. Currently, if a task gets cancelled while waiting, we don't send a response until the cluster gets unblocked (which could be arbitrarily far in the future) or until the timeout occurs. We should make use of `CancellableTask#addListener` to react more promptly to task cancellation.

Follow-up from https://github.com/elastic/elasticsearch/pull/117230#discussion_r1851909675

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `a84c2519aadcd838a9d4d8b52691241d223c3221`
**Instance ID:** `elastic__elasticsearch-128737`
**Language:** `Java`
