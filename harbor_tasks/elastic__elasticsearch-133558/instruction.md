# Task

## Limit size of shardDeleteResults

Modifies `BlobStoreRepository.ShardBlobsToDelete.shardDeleteResults` to have a variable size depending on the remaining heap space rather than a hard-coded 2GB size which caused smaller nodes with less heap space to OOMe.

Relates to #131822
Closes #116379

Closes ES-12540

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d8ae9aecdec0181a1f422609854084f42681c435`
**Instance ID:** `elastic__elasticsearch-133558`
**Language:** `Java`
