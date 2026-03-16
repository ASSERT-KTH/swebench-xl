# Task

## Disallow bare `{agg}_over_time` with grouping attributes | Disallow sorting between `TS` and `STATS`

### Issue 1: Disallow bare `{agg}_over_time` with grouping attributes

`{agg}_over_time` and `rate` are applied per `_tsid`. Grouping on dimensions, in addition to time bucket, requires an outer agg to provide the aggregation function. For instance, the following query is not allowed:

```
TS metrics | STATS rate(requests) BY host, TBUCKET(1 hour)
```

In this case, we need to return an error explaining that either an outer agg needs to be provided, or grouping attributes need to be stripped.



---

### Issue 2: Disallow sorting between `TS` and `STATS`

Evaluation of `rate` and `{agg}_over_time` functions relies on scanning data ordered by `[tsid, @timestamp]`. Changing the order may lead to producing wrong results, so sort operations should not be allowed in this context. The `STATS` output can be sorted without restrictions.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `9c96b944b21306794c370395a3b26fbb3dc5d562`
**Instance ID:** `elastic__elasticsearch-134413`
**Language:** `Java`
