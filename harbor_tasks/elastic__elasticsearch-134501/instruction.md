# Task

## Increase default limit for time-series results beyond 10000

ES|QL allows for up to 10000 results be default. This is too restrictive for time-series queries, where every time-series appears as a separate row, and results may cover days' worth of data.

Unless the compute engine lifts this limitation across the board, we want to use a different limit by default for the `TS` command - shooting for 1,000,000 results by default initially.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `47acb9a03aabbb35c9575cce1a6132ee1ad7a0a5`
**Instance ID:** `elastic__elasticsearch-134501`
**Language:** `Java`
