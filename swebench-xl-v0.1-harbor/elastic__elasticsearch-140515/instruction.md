# Task

## Enforce Limit on Number of IDs in IdsQuery

Elasticsearch is currently vulnerable to OOMs crashes when handling IdQuery requests containing a large amount of IDs. This problem has presented himself in smaller ES nodes (2GB RAM and 1.45 Millions IDs), while in bigger nodes this might not be a problem, because of the already existing 100MB limit to the http request is effectively preventing OOMs by rejecting IdQueries with too many IDs.

To prevent these failures in the future we should enforce a maximum number of allowed IDs, ideally based on the available memory of the node.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `eed907ba00891ffc46c0bb8357582e37141e2416`
**Instance ID:** `elastic__elasticsearch-140515`
**Language:** `Java`
