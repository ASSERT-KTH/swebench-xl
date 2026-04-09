# Task

## Sort TS output by timestamp desc

When no STATS or SORT commands are included in a query with `TS`, the output should be sorted by timestamp desc. This way, it'll provide the most recent data points across all time series - as opposed to passing through the index sort config `[_tsid, @timestamp desc]` that likely returns many data points for a handful of time series.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `170df56ea7dcc63a6f158e303a803c4b807092d0`
**Instance ID:** `elastic__elasticsearch-141619`
**Language:** `Java`
