# Task

## ESQL: multi_match with a lookup index fails with AssertionError

### Description

```
from languages*
| keep language_code_long, language_code
| mv_expand language_code 
| where NOT multi_match("test", language_code_long)
```

results in

```
fatal error in thread [elasticsearch[test-cluster-0][esql_worker][T#1]], exiting java.lang.AssertionError: LuceneQueryExpressionEvaluator expects a DocBlock
	at org.elasticsearch.compute.lucene.query.LuceneQueryEvaluator.executeQuery(LuceneQueryEvaluator.java:73)
	at org.elasticsearch.compute.lucene.query.LuceneQueryExpressionEvaluator.eval(LuceneQueryExpressionEvaluator.java:40)
	at org.elasticsearch.xpack.esql.evaluator.EvalMapper$BooleanLogic$1BooleanLogicExpressionEvaluator.eval(EvalMapper.java:119)
	at org.elasticsearch.compute.operator.FilterOperator.process(FilterOperator.java:43)
	at org.elasticsearch.compute.operator.AbstractPageMappingOperator.getOutput(AbstractPageMappingOperator.java:89)
	at org.elasticsearch.compute.operator.Driver.runSingleLoopIteration(Driver.java:295)
	at org.elasticsearch.compute.operator.Driver.run(Driver.java:194)
	at org.elasticsearch.compute.operator.Driver$1.doRun(Driver.java:464)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.compute.operator.DriverScheduler$1.doRun(DriverScheduler.java:57)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
```

Might be the same issue as https://github.com/elastic/elasticsearch/issues/129778

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `c065bf4af1e532615042cbf889d80fb3c0136219`
**Instance ID:** `elastic__elasticsearch-143249`
**Language:** `Java`
