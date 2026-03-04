# Task

## Transforms will infinitely queue PIT closures causing a "PIT storm"

### Elasticsearch Version

8.16+

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

_any_

### Problem Description

Transforms when using point-in-time (PIT) search will create multiple PITs over the lifetime of a single transform pivot page. 

If there is any failure, or a new search is initiated, or the scheduled pivot completes, it will request the PITs to be deleted.

However, it will not wait for these PITs to be deleted before scheduling again or continuing with another set of searches. Consequently, its possible for many transforms, in quick succession, could create MANY PITs and cause a significant queue of close pit requests which can cause pressure on the system.

Transforms should wait for all its close-pit requests to complete before continuing its execution paths. Since close-pit "should" be fast, this should be OK. However, if close pit is slow, we want transforms to be naturally throttled to prevent a PIT storm.

### Steps to Reproduce

Have many transforms with PIT involved pointing at the same index patterns that point at hundreds of shards on single nodes
Have fast transform frequency
Watch it burn

### Current Workaround

PIT can be disabled for a transform:
```
POST _transform/<transform id>/_update
{
  "settings": {
    "use_point_in_time": false
  }
}
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1904abbb730ec6bfc47a58425a3949664013ed55`
**Instance ID:** `elastic__elasticsearch-134955`
**Language:** `Java`
