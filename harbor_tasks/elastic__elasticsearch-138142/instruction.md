# Task

## Ensure shard movement is always recorded for hotspot mitigation

We should record the movement even if the shard has no write load. This ensures hot-spot migitation happens only once every ClusterInfo polling cycle as we agreed.

Resolves: #138137

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `770c3344d0ec733b550d8b7fb937bc310a8604e1`
**Instance ID:** `elastic__elasticsearch-138142`
**Language:** `Java`
