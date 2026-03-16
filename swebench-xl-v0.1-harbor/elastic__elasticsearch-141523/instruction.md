# Task

## ES|QL: FUSE unbounded input with subqueries

For FUSE, we currently have a validation that check that a PipelineBreaker exists before FUSE.
Ideally we should check for LIMIT specifically.

The problem is that the current check does not account when a non-unary plan is used before FUSE, because we use `forEachUp`:

https://github.com/elastic/elasticsearch/blob/bc134a8b7fb2d31d6d96c8edc79e9a3ff2158572/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plan/logical/fuse/FuseScoreEval.java#L168-L184

Because subqueries don't have an implicit LIMIT, this check can pass if at least one of the subqueries has a LIMIT.

For example, for this query, we don't return a validation error, when we clearly should because the first subquery is unbounded:

```
FROM (FROM books METADATA _score, _id, _index | EVAL x="1"),
     (FROM books METADATA _score, _id, _index | LIMIT 3 | EVAL x = "2")
| FUSE LINEAR GROUP BY x  WITH {"normalizer": "minmax"}
| KEEP x, title, _score
```

Because we are using linear combination with a score normalizer, the operator needs to collect all the input pages, before it can output rows. This can lead to circuit breaker exception in case we have too many pages coming from the first subquery.

FUSE was always meant to be used on a limited number of rows, because it implements hybrid search ranking algorithms that are applied after a first stage retrieval.
FUSE is not meant to be used on potentially the whole corpus of documents coming from an index.

As a side note, MMR will have a similar problem.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8c9f9b777d9b1c66fa09f0853e66ab7a0809ba33`
**Instance ID:** `elastic__elasticsearch-141523`
**Language:** `Java`
