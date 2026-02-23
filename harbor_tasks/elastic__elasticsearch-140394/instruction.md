# Task

## Limit heap used tracking `IndexMetadata` deletions

In #133558 we imposed a limit on the heap used to keep track of
shard-level blobs to clean up after the commit of a snapshot deletion.
This commit makes use of the same mechanism to track `IndexMetadata`
blobs for future deletion.

Closes #140018

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `be581a524408b1b4242456c75824d27791ceee03`
**Instance ID:** `elastic__elasticsearch-140394`
**Language:** `Java`
