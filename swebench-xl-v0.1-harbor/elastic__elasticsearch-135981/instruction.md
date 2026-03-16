# Task

## Fix aggregations on dimension fields

The following query is not supported:

```
TS kibana_sample_data_logstsdb 
| STATS results = count(agent.keyword) by TBUCKET(1day)
```

`Unexpected error from Elasticsearch: unresolved_exception - Invalid call to dataType on an unresolved object ?LASTOVERTIME_$1`

The issue is that we try to use `last_over_time` implicitly, even though `agent.keyword` is a dimension. Here, this should work as a regular agg in `FROM`.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `c19d4d704f7ccf2e378ffb64bc4d0ba5ce4ab49f`
**Instance ID:** `elastic__elasticsearch-135981`
**Language:** `Java`
