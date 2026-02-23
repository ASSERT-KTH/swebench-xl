# Task

## More validation for time-series aggregations

Add validations to reject the following queries until supported:

1. Limit and sort cannot be used to alter the time-series source:
   - `TS metrics | LIMIT ... | STATS ...`
   - `TS metrics | SORT BY ... | STATS ...`

2. Over-time aggregation without an outer aggregation (to be supported soon):
   - `TS metrics | STATS rate(requests)`
   - `TS metrics | STATS last_over_time(requests)`

3. Reject lookup join, enrich, change point before the first stats.

Closes #134366
Closes #134372

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `9c96b944b21306794c370395a3b26fbb3dc5d562`
**Instance ID:** `elastic__elasticsearch-134413`
**Language:** `Java`
