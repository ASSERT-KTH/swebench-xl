# Task

## Add `histogram` as a new time series metric

### Description

We would like to introduce `histogram` as a new time series metric type next to `counter` and `gauge`. A time series metric histogram can be either of type `histogram` or `exponential_histogram`.

A sample configuration of such metric would like:

```
       "latency": {
          "type": "exponential_histogram",
          "time_series_metric": "histogram"
        },
```

Furthermore, these metrics need to be able to be downsampled with both sampling methods.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `0fb42ed2338627e9639d0f57856b037951c08336`
**Instance ID:** `elastic__elasticsearch-138366`
**Language:** `Java`
