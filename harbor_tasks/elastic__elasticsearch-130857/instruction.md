# Task

## Computing IndicesQueryCache stats is O(N²) in shard count

We loop over all shards in `org.elasticsearch.indices.IndicesService#statsByShard` calling `indexShardStats` for each one, but then further down the stack in `org.elasticsearch.indices.IndicesQueryCache#getStats` we loop over all the shards again in order to compute the portion of the shared RAM usage to attribute to the current shard. These days a node can hold many thousands of shards, so this duplicated work consumes quite some resources.

We have the same loop in `org.elasticsearch.action.admin.cluster.stats.TransportClusterStatsAction#nodeOperation`.

We have _effectively_ the same loop in `org.elasticsearch.action.admin.indices.stats.TransportIndicesStatsAction#shardOperation`, but this one is trickier because the outer loop is within `TransportBroadcastByNodeAction` which doesn't currently have a facility for sharing any context between invocations on different shards.

Relates #77466.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b00329c6e6f7dfcb4dc7ecdc1c974b5fd3744770`
**Instance ID:** `elastic__elasticsearch-130857`
**Language:** `Java`
