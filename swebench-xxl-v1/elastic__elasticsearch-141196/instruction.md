# Task

## ESQL TS Command: Bucketing on renamed timestamp field causing error

Query:
```
ts k8s 
| eval YzNluaodioCG = @timestamp 
| stats  swvhdBekIkO = min(last_over_time(network.total_bytes_out))  by LhjIiNjP = bucket(YzNluaodioCG,1hour)
;
```

```
      - type: "esql_illegal_argument_exception"
        reason: "expected named expression for grouping; got Bucket{field=YzNluaodioCG{r}#3,\
          \ buckets=PT1H, from=null, to=null} AS LhjIiNjP#6"
        stack_trace: "org.elasticsearch.xpack.esql.EsqlIllegalArgumentException: expected\
          \ named expression for grouping; got Bucket{field=YzNluaodioCG{r}#3, buckets=PT1H,\
          \ from=null, to=null} AS LhjIiNjP#6\n\tat org.elasticsearch.xpack.esql.optimizer.rules.logical.TranslateTimeSeriesAggregate.rule(TranslateTimeSeriesAggregate.java:295)\n\
          \tat org.elasticsearch.xpack.esql.optimizer.rules.logical.TranslateTimeSeriesAggregate.rule(TranslateTimeSeriesAggregate.java:156)\n\
          \tat org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$ParameterizedOptimizerRule.lambda$apply$1(OptimizerRules.java:107)\n\
          \tat org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformUp$13(Node.java:273)\n\
          \tat org.elasticsearch.xpack.esql.core.tree.Node.transformUp(Node.java:268)\n\
          \tat org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformUp$12(Node.java:266)\n\
          \tat org.elasticsearch.xpack.esql.core.tree.Node.transformChildren(Node.java:291)\n\
          \tat org.elasticsearch.xpack.esql.core.tree.Node.transformUp(Node.java:266)\n\
          \tat org.elasticsearch.xpack.esql.core.tree.Node.transformUp(Node.java:273)\n\
          \tat org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$ParameterizedOptimizerRule.apply(OptimizerRules.java:107)\n\
          \tat org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$ParameterizedOptimizerRule.apply(OptimizerRules.java:92)\n\
          \tat org.elasticsearch.xpack.esql.rule.ParameterizedRuleExecutor.lambda$transform$0(ParameterizedRuleExecutor.java:29)\n\

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `206b12ae8e618d66d84ea5e7fda8a80a9eb3e15c`
**Instance ID:** `elastic__elasticsearch-141196`
**Language:** `Java`
