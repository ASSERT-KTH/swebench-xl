# Task

## NPE in ESQL LIMIT with parameter

Since https://github.com/elastic/elasticsearch/pull/128464

A query like `ROW a=1 | LIMIT null` ends up with:

```
java.lang.NullPointerException: Cannot invoke "Object.getClass()" because "val" is null
        at org.elasticsearch.xpack.esql.parser.LogicalPlanBuilder.visitLimitCommand(LogicalPlanBuilder.java:407)
```

Same with:

```
{
  "query": "ROW a=1 | LIMIT ?",
  "params": [
    null
  ]
}
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8bcb0c4c652a9e102a0831ea1ebad7d73a18d78e`
**Instance ID:** `elastic__elasticsearch-130914`
**Language:** `Java`
