# Task

## Improving statsByShard performance when the number of shards is very large

This fixes IndicesService.statsByShard() so that it no longer has O(N^2) performance (where N is the number of shards in the cache). It does this by pre-computing the total number of objects in the cache and the total number of shards represented in the cache, so that these don't have to be calculated for each shard.

Closes https://github.com/elastic/elasticsearch/issues/97222

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b00329c6e6f7dfcb4dc7ecdc1c974b5fd3744770`
**Instance ID:** `elastic__elasticsearch-130857`
**Language:** `Java`
