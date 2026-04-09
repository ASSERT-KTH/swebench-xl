# Task

## ESQL: INLINE STATS with aggs of constants failure

### Description

The following queries fail with the stacktrace below, a common criteria being aggregations of constants:

```
from employees | inline stats  x = min(123) | keep x
from employees | inline stats  x = min(123) + max(123) | keep x
from employees | inline stats  x = min(123) + max(123), y = max(languages) | keep x
from employees | inline stats  x = min(null) + median(null), y = present(languages) | keep x
SET unmapped_fields="nullify";from employees | inline stats  x = min(foobar) + median(foobar), y = present(languages) | keep x
SET unmapped_fields="nullify";from languages_lookup_non_unique_key,clientips | inline stats  x = min(foobar) + median(foobar), zQnmhGlViL = present(language_code) | keep x, `env`, env
```

```
java.lang.IllegalStateException: Expected to replace a single StubRelation in the plan, but none found
        at org.elasticsearch.xpack.esql.plan.logical.join.InlineJoin.replaceStub(InlineJoin.java:114)
        at org.elasticsearch.xpack.esql.optimizer.rules.logical.PropagateInlineEvals.rule(PropagateInlineEvals.java:90)
        at org.elasticsearch.xpack.esql.optimizer.rules.logical.PropagateInlineEvals.rule(PropagateInlineEvals.java:33)
        at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$10(Node.java:268)
        at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:244)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `df16cba3b96fbf18311dff00d64f184c8a7844d3`
**Instance ID:** `elastic__elasticsearch-142882`
**Language:** `Java`
