# Task

## Requests with LIMIT 0 are not executed when the TS command is used

### Elasticsearch Version

9.3

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

Darwin Kernel Version 25.3.0

### Problem Description

When executing a query using the TS command with `STATS dimension_field`, a _timeseries column is added in runtime and is taken into account when validating the output. 

It turns out that "LIMIT 0" is a corner case in which we replace the entire plan with a different one (LocalRelation) so that there is no TimeSeriesAggregate and a verification step fails.

### Steps to Reproduce

Query:
```
TS kibana_sample_data_logstsdb | STATS bytes_counter BY meow = BUCKET(@timestamp, 50, ?_tstart, ?_tend) | limit 0
```

Output:
```
Output has changed from [[bytes_counter{r}#30886, meow{r}#30884]] to [[bytes_counter{r}#30886, _timeseries{r}#30894, meow{r}#30884]]
```

Expected output: a list of columns

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `89888b20b4bd0597c38303a0f50acf387ee91c1a`
**Instance ID:** `elastic__elasticsearch-144031`
**Language:** `Java`
