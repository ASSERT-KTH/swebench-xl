# Task

## PromQL: wire range selector duration to window for `TimeSeriesAggregateFunction`s

Today, we require that all range selectors align with the `step`. That's because our bucketing by step effectively creates a range vector per bucket: we get all values per time series for each bucket.

For example:

```
PROMQL step=1m sum(rate(http_requests_total[1m]))
```

To remove this restriction, we need to wire the range selector duration to the recently added window for `TimeSeriesAggregateFunction`s (see #138139 and #138456).

This will allow queries like the following to run, where the step (1m) is different from the range vector duration (5m):

```
PROMQL step=1m sum(rate(http_requests_total[5m]))
```

Note that not all `TimeSeriesAggregateFunction`s support windows, yet.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `7f8715b3684ea8d09c3cc570bd6cc424caa9d2cf`
**Instance ID:** `elastic__elasticsearch-140099`
**Language:** `Java`
