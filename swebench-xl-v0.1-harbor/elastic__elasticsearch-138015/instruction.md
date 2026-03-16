# Task

## DELETE _all fails if an index is deleted during the request

### Elasticsearch Version

9.x, main

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

N/A

### Problem Description

**Current behaviour**

Request `DELETE /_all` might fail if another process deletes one of the resolved indices while it is running.

**Expected behaviour**

Request `DELETE /_all` should be resilient to another process deleting one of the resolved indices considering that the user did not specify which indices to delete.


### Steps to Reproduce

We saw this while debugging #136585 but it doesn't reproduce locally.

We believe a test that forces the following sequence of events should be able to reproduce this:
- Create 2 indices.
- Request for all indices to be deleted, but add a delay after [the index resolution](https://github.com/elastic/elasticsearch/blob/569c1fc1cde793d943b1161e915727ec48d6ae25/server/src/main/java/org/elasticsearch/action/admin/indices/delete/TransportDeleteIndexAction.java#L100).
- Take advantage of the delay and delete one of the two indices.
- The above will ensure that the delete index cluster update task will actually run on a new cluster state without one of the two indices. 
- Then when the cluster update will try to [resolve the project via the index name](https://github.com/elastic/elasticsearch/blob/f0f641086f0fdfb8506e2ab19f47e3c8505c436e/server/src/main/java/org/elasticsearch/cluster/metadata/MetadataDeleteIndexService.java#L148) we get an `IndexNotFoundException`.

### Logs (if relevant)

```
[2025-10-30T20:45:58,426][ERROR][o.e.t.InternalTestCluster][node_t1][transport_worker][T#1] ---- initial wiping of indices failed
  org.elasticsearch.transport.RemoteTransportException: [node_t0][127.0.0.1:19841][indices:admin/delete]
  Caused by: org.elasticsearch.index.IndexNotFoundException: no such index [[tpspdlrtri/0KOiMkdbSDuzTk1Z_mx7Hw]] and index [[tpspdlrtri/0KOiMkdbSDuzTk1Z_mx7Hw]] does not exist in any project
   at org.elasticsearch.cluster.metadata.Metadata.lambda$projectFor$13(Metadata.java:1876) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  at java.util.Optional.orElseThrow(Optional.java:403) ~[?:?]
  at org.elasticsearch.cluster.metadata.Metadata.projectFor(Metadata.java:1875) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
        at org.elasticsearch.cluster.metadata.MetadataDeleteIndexService.deleteIndices(MetadataDeleteIndexService.java:148) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.metadata.MetadataDeleteIndexService$1.executeTask(MetadataDeleteIndexService.java:67) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.metadata.MetadataDeleteIndexService$1.executeTask(MetadataDeleteIndexService.java:61) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.SimpleBatchedAckListenerTaskExecutor.execute(SimpleBatchedAckListenerTaskExecutor.java:64) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.service.MasterService.innerExecuteTasks(MasterService.java:1100) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  	at org.elasticsearch.cluster.service.MasterService.executeTasks(MasterService.java:1063) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  	at org.elasticsearch.cluster.service.MasterService.executeAndPublishBatch(MasterService.java:246) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.service.MasterService$BatchingTaskQueue$Processor.lambda$run$2(MasterService.java:1710) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.action.ActionListener.run(ActionListener.java:465) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.service.MasterService$BatchingTaskQueue$Processor.run(MasterService.java:1707) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.cluster.service.MasterService$5.lambda$doRun$0(MasterService.java:1308) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  	at org.elasticsearch.action.ActionListener.run(ActionListener.java:465) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  	at org.elasticsearch.cluster.service.MasterService$5.doRun(MasterService.java:1287) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
   	at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1076) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  	at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27) ~[elasticsearch-9.3.0-SNAPSHOT.jar:9.3.0-SNAPSHOT]
  	at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090) ~[?:?]
   	at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614) ~[?:?]
  	at java.lang.Thread.run(Thread.java:1474) ~[?:?]
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `6aa1eb43278ab13a9522a6947a6e04650d83eb9f`
**Instance ID:** `elastic__elasticsearch-138015`
**Language:** `Java`
