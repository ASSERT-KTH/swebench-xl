# Task

## Filter out null metric values

Aggregations involving time-series should only process documents where values for metric fields are not null. This is in line with PromQL that implicitly selects time-series containing values and tracks the ones with no recent data as stale.

A workaround is to explicitly filter out null values, e.g.

```
TS my-metrics
 | WHERE cpu_usage IS NOT NULL
 | STATS max(avg_over_time(cpu_usage)) BY TBUCKET(1 hour), hostname
```

Still, adding `WHERE <metric> IS NOT NULL` for all metrics in all queries is fairly verbose and redundant. It should be implicitly applied within the `TS` command scope.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `df8cedf9920c8bf710221ca8579bb90f64d4faa0`
**Instance ID:** `elastic__elasticsearch-133087`
**Language:** `Java`
