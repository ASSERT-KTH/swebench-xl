# Task

## LifecyclePolicyUsgeCalculator incorrectly fails assertion

If I make a request to the `_ilm/policy` API as a user with permission to see system data streams, LifecyclePolicyUsgeCalculator incorrectly throws an AssertionError if assertions are enabled.
Steps to reproduce:
(1) Start the server with assertions enabled
(2) Impersonate fleet to create the .fleet-action-results data stream (a system data stream that we have a built-in template for):
```
curl -u "elastic-admin:elastic-password" -X POST "localhost:9200/.fleet-actions-results/_doc?pretty" \     
     -H 'Content-Type: application/json' \
     -H 'X-Elastic-Product-Origin: fleet' \
     -H '_system_index_access_allowed: true' \
     -H '_external_system_index_access_origin: fleet' \
     -d'
{
  "@timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
  "action_id": "sample-action-123",
  "agents": ["agent-uuid-456"],
  "status": "success",
  "message": "Sample result for testing purposes"
}
'
```
(3) Impersonate fleet to try to fetch ilm policies (or just start kibana, because it makes a similar request):
```
curl -u "elastic-admin:elastic-password" "localhost:9200/_ilm/policy" \
     -H 'X-Elastic-Product-Origin: fleet' \
     -H '_system_index_access_allowed: true' \
     -H '_external_system_index_access_origin: fleet'
```
The server crashes with:
```
[2026-03-04T09:46:46,697][ERROR][o.e.b.ElasticsearchUncaughtExceptionHandler] [runTask-0] fatal error in thread [elasticsearch[runTask-0][management][T#2]], exiting java.lang.AssertionError: Data stream [.fleet-actions-results] has no matching template
        at org.elasticsearch.xcore@9.4.0-SNAPSHOT/org.elasticsearch.xpack.core.ilm.LifecyclePolicyUsageCalculator.<init>(LifecyclePolicyUsageCalculator.java:83)
        at org.elasticsearch.ilm@9.4.0-SNAPSHOT/org.elasticsearch.xpack.ilm.action.TransportGetLifecycleAction.localClusterStateOperation(TransportGetLifecycleAction.java:113)
        at org.elasticsearch.ilm@9.4.0-SNAPSHOT/org.elasticsearch.xpack.ilm.action.TransportGetLifecycleAction.localClusterStateOperation(TransportGetLifecycleAction.java:42)
        at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.action.support.local.TransportLocalProjectMetadataAction.localClusterStateOperation(TransportLocalProjectMetadataAction.java:59)
        at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.action.support.local.TransportLocalClusterStateAction.lambda$innerDoExecute$0(TransportLocalClusterStateAction.java:92)
        at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.action.ActionRunnable$4.doRun(ActionRunnable.java:101)
        at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
        at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
        at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
        at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
        at java.base/java.lang.Thread.run(Thread.java:1474)
```
The reason is that LifecyclePolicyUsageCalculator [fetches the names of all data streams](https://github.com/elastic/elasticsearch/blob/v9.3.1/x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/ilm/LifecyclePolicyUsageCalculator.java#L75) that the user is allowed to see, and then blows up if it [cannot find the template](https://github.com/elastic/elasticsearch/blob/v9.3.1/x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/ilm/LifecyclePolicyUsageCalculator.java#L81) for any data stream. But system data streams have their templates stored [differently](https://github.com/elastic/elasticsearch/blob/v9.3.1/server/src/main/java/org/elasticsearch/action/admin/indices/rollover/MetadataRolloverService.java#L325-L329).
It might be easiest to just remove this assertion. Otherwise, we probably need to find the data stream object to see if it is a system data stream.

The impact of this one is that you cannot fetch any ILM policies if the cluster has a system data stream AND you are calling the `GET _ilm/policy` API using the `X-Elastic-Product-Origin` header for a user who can see one of those data streams AND you have assertions enabled. So the impact is probably pretty small in practice.

Caused by #106953

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `2441ae030e6bf255aa92d127138f77b4b9f536a1`
**Instance ID:** `elastic__elasticsearch-143710`
**Language:** `Java`
