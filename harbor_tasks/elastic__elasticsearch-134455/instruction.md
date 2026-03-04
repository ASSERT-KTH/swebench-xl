# Task

## ESQL: Make INLINESTATS properly track memory of data passed between phases

When INLINESTATS is executed, it performs a first phase where it only computes the `STATS`, then it stuffs the result thereof into the query plan of the second phase, which uses it to perform an `InlineJoin`.

The memory used for this was not properly tracked; instead we put a 1MB limit in place.

This should be properly tracked with ES|QL's circuit breaking infrastructure, otherwise many parallel INLINESTATS requests could run a node out of memory.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f1bcb0791f7e4051c9d7d0f86a7b1e4b06d7c461`
**Instance ID:** `elastic__elasticsearch-134455`
**Language:** `Java`
