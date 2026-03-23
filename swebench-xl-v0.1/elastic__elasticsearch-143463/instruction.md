# Task

## ES|QL: illegal_argument_exception - "blocks is empty"

With CSV tests dataset

```
from airport* 
| eval  city_boundary = 791874950, `abbrev` = null, scalerank = null 
| rename country AS rfTayTvLPr |
 stats  rfTayTvLPr = sum(city_boundary) + avg(city_boundary) + avg(city_boundary) by airport 
| limit 386 
| eval  airport = null, VVfKeXqVbnT = \"gbVBNaFobGlCQPIkte\", PJOLpMsn = null, airport = null, airport = rfTayTvLPr, foVaVtSC = rfTayTvLPr + rfTayTvLPr + rfTayTvLPr, `rfTayTvLPr` = 1396716876604474766, iOiARfQkaTW = \"vyrzleIDGZtnEN\", pjBEOZhLZ = -5665028385242339998, airport = 1901277392 
| keep iOiARfQkaTW 
| drop iOiARfQkaTW
```


```

type: "illegal_argument_exception" 
reason: "blocks is empty" 
stack_trace: "java.lang.IllegalArgumentException: blocks is empty
	at org.elasticsearch.compute.data.Page.determinePositionCount(Page.java:149)  
	at org.elasticsearch.compute.data.Page.<init>(Page.java:65)
	at org.elasticsearch.compute.operator.LimitOperator.truncatePage(LimitOperator.java:126)  
	at org.elasticsearch.compute.operator.LimitOperator.addInput(LimitOperator.java:82)  
	at org.elasticsearch.compute.operator.Driver.runSingleLoopIteration(Driver.java:309)  
	at org.elasticsearch.compute.operator.Driver.run(Driver.java:194)
	at org.elasticsearch.compute.operator.Driver$1.doRun(Driver.java:459)  
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

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `42e14a9b4a80589500a04393f4d6f5f75d096cde`
**Instance ID:** `elastic__elasticsearch-143463`
**Language:** `Java`
