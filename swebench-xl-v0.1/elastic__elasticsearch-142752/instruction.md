# Task

## SearchContextStats.min()/max() leak sentinel values causing overflow in Rounding

### Elasticsearch Version

all

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

all

### Problem Description


ES|QL queries on date fields targeting wide index patterns (e.g. `apm-*,logs-*.otel-*,...`) that match indices with different codecs (e.g. TSDB vs non-TSDB) fail with an `IllegalArgumentException`.

When doc values skippers are used but some segments lack a skipper (TSDB segment vs non-TSDB segment), `DocValuesSkipper` returns `Long.MIN_VALUE`/`Long.MAX_VALUE` as sentinel values. `SearchContextStats` treats these sentinel values as real timestamp values and `Rounding.prepare(min, max)` fails with an overflow.

#### Stack trace

```
Caused by: java.lang.IllegalArgumentException: [9223372036852975808] must be <= [-9223372036852975809]
	at org.elasticsearch.common.LocalTimeOffset.lookup(LocalTimeOffset.java:55)
	at org.elasticsearch.common.Rounding$TimeIntervalRounding.prepareOffsetOrJavaTimeRounding(Rounding.java:1062)
	at org.elasticsearch.common.Rounding$TimeIntervalRounding.prepare(Rounding.java:1055)
	at org.elasticsearch.xpack.esql.expression.function.grouping.Bucket.getDateRounding(Bucket.java:323)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.local.ReplaceDateTruncBucketWithRoundTo.lambda$substitute$3(ReplaceDateTruncBucketWithRoundTo.java:85)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.local.ReplaceDateTruncBucketWithRoundTo.maybeSubstituteWithRoundTo(ReplaceDateTruncBucketWithRoundTo.java:121)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.local.ReplaceDateTruncBucketWithRoundTo.substitute(ReplaceDateTruncBucketWithRoundTo.java:79)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.local.ReplaceDateTruncBucketWithRoundTo.lambda$substitute$1(ReplaceDateTruncBucketWithRoundTo.java:61)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$10(Node.java:268)
```

#### Root cause

`SearchContextStats.min()`/`max()` accept sentinel values like `Long.MIN_VALUE` and `Long.MAX_VALUE` as real values and pass them down to the rounding logic.

### Steps to Reproduce

Still trying to reproduce after getting the stack trace but probably something like:

1. Create a TSDB index and a non-TSDB index, both with a date field
2. Index documents with date values into the TSDB index only
3. Run an ES|QL on date field on a pattern matching both indices

A simpler reproduction might be possible in `SearchContextStatsTests` too.

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `7c8edd29e5a4f1e718fee461258436e79b8fde08`
**Instance ID:** `elastic__elasticsearch-142752`
**Language:** `Java`
