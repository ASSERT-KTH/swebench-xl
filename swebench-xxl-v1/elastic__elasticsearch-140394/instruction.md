# Task

## Excessive heap usage of post-snapshot-delete index metadata cleanup

Today `RepositoryData#indexMetaDataToRemoveAfterRemovingSnapshots` constructs a `HashMap<IndexId, HashSet<String>>` identifying every index metadata blob to be removed after deleting some collection of snapshots. This data structure can in theory be arbitrarily large, and in practice has been seen to consume many GiBs of heap in a cluster in which snapshotting was disrupted for an extended period of time in a way that prevented snapshots from being deleted and then the disruption was removed.

I believe we don't need to construct this data structure up-front at all, because these days `BlobContainer#deleteBlobsIgnoringIfNotExists` accepts an iterator over blob names from which it constructs the delete-blob requests progressively. It's not essential to deduplicate the blob names since deleting a blob multiple times is acceptable, but it would also seem reasonable to construct each per-index `HashSet<String>` as needed. Note that this would mean retaining `RepositoryData#indexMetaDataGenerations` for longer, past the end of the snapshot delete, so we should make sure there's enough backpressure to stop a buildup of excessively many of these things.

Alternatively, we could generalize `ShardBlobsToDelete` slightly to keep track of both shard-data and index-metadata blobs to be deleted, enforcing a strict bound on the memory footprint of all this data, and preferring to leak some blobs rather than sending the node OOM.
## Hint: Symbols to Implement

The following symbols need to be created as part of this task:

- Class `BlobsToDelete`

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `be581a524408b1b4242456c75824d27791ceee03`
**Instance ID:** `elastic__elasticsearch-140394`
**Language:** `Java`
