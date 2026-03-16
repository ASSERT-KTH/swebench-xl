# Task

## Allow other index types to be updated to disk_bbq

### Description

once the format of disk_bbq is no longer behind a feature flag, we should allow other index formats to be merged into disk_bbq allowing for updates. 

My intuition here is that we allow updates from *flat, *hnsw, -> disk_bbq. 

Additionally, I would also think we should allow `disk_bbq` updates to particular settings (e.g. target cluster size).

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `079355a4d0ce7a359946d6969ab63eb6b39a3077`
**Instance ID:** `elastic__elasticsearch-131760`
**Language:** `Java`
