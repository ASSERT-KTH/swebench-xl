# Task

## ESQL: inconsistent logging of partial failures in async vs. sync requests | ESQL: Correctly log errors when storing async results

### Issue 1: ESQL: inconsistent logging of partial failures in async vs. sync requests

Reproducing a known bug, we can run the following query against a local cluster with the csv test data:
```
curl -u elastic:password -H "Content-Type: application/json" "127.0.0.1:9200/_query/async" -d '
{ "wait_for_completion_timeout": "1ms",
  "query": "from employees | eval x = salary::long | stats y = first(x, x)"}'

->
[2026-02-11T16:01:14,549][WARN ][o.e.c.o.Driver           ] [runTask-0] Error running driver [data] java.lang.ArrayIndexOutOfBoundsException: Index 1 out of bounds for length 1
```

```
curl -u elastic:password -H "Content-Type: application/json" "127.0.0.1:9200/_query" -d '
{                                      
  "query": "from employees | eval x = salary::long | stats y = first(x, x)"}'

->
[2026-02-11T16:01:51,019][WARN ][o.e.x.e.a.EsqlResponseListener] [runTask-0] partial failure at path: /_query, params: {} shard [[_na_][employees][0]], reason [java.lang.ArrayIndexOutOfBoundsException: Index 1 out of bounds for length 1


[2026-02-11T16:01:51,019][WARN ][o.e.x.e.a.EsqlResponseListener] [runTask-0] partial failure at path: /_query, params: {} shard [[_na_][employees][0]], reason [java.lang.ArrayIndexOutOfBoundsException: Index 1 out of bounds for length 1

```

---

### Issue 2: ESQL: Correctly log errors when storing async results

Relates https://github.com/elastic/elasticsearch/issues/139883.

We were too noisy and generally logged exceptions during storing of async ESQL results as ERROR. This is getting downgraded to WARN in https://github.com/elastic/elasticsearch/pull/142112.

However, the noise mostly comes from CBEs and rejected store requests because the result sets were too big. These are fine to log as WARN, but now we do not log genuine bugs (e.g. IllegalStateException) as ERROR; this is, however, required to ensure good alerting for bugs in async queries, esp. in Serverless.

We should probably do the same as #140905 and distinguish between exceptions based on their status:
- log 5xx exceptions as ERROR
- log other exceptions as WARN
## Hint: Symbols to Implement

The following symbols need to be created as part of this task:

- Method `storeResultFailureStatus(IllegalStateException)` in `AsyncTaskManagementService`
- Method `storeResultFailureStatus(IllegalArgumentException)` in `AsyncTaskManagementService`
- Method `storeResultFailureStatus(ElasticsearchStatusException)` in `AsyncTaskManagementService`
- Method `storeResultFailureStatus(CircuitBreakingException)` in `AsyncTaskManagementService`

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `fb9b6982c9a19c6a56bc9dfa2ce072bc524dfa49`
**Instance ID:** `elastic__elasticsearch-142401`
**Language:** `Java`
