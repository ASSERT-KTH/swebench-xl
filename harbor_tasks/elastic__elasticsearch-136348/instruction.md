# Task

## INLINE STATS and TS command has confusing output

### Description

There was an [issue](https://github.com/elastic/elasticsearch/issues/134212) and PR for limiting the support of `inline stats` and `ts` commands combination, but it seems there are some combinations of commands that have an unexpected outcome:

- `ts k8s | inline stats  max_bytes=max(to_long(network.total_bytes_in)) BY cluster`
works
- `ts k8s | inline stats max(60 * rate(network.total_bytes_in)), max(network.bytes_in)` 
outputs `time_series aggregate[rate(network.total_bytes_in)] can only be used with the TS command`
- `TS k8s metadata _tsid | inline STATS  cnt = count_distinct(_tsid) BY cluster, pod` 
works
- `TS k8s | INLINE STATS max_cost=max(last_over_time(network.cost)) BY cluster, time_bucket = bucket(@timestamp,1minute)` 
outputs `time_series aggregate[last_over_time(network.cost)] can only be used with the TS command`
- `TS k8s | INLINE STATS max_bytes=max(to_long(network.total_bytes_in)) BY cluster | SORT max_bytes DESC | keep max*, cluster` 
works.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `da10e19340314fb6ee92293d97e0651c2cababc3`
**Instance ID:** `elastic__elasticsearch-136348`
**Language:** `Java`
