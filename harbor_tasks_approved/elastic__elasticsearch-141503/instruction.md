# Task

## ESQL TS Command: "Invalid call to dataType on an unresolved object ?@timestamp"

Query:
```
ts d*,k8s*
| keep network.total_bytes_in 
| stats  `network.total_bytes_in` = count(*), nSAYaRUAR = count(*)
;
```

Error:
```
            "type" : "unresolved_exception",
            "reason" : "Invalid call to dataType on an unresolved object ?@timestamp",
            "stack_trace" : "org.elasticsearch.xpack.esql.core.capabilities.UnresolvedException: Invalid call to dataType on an unresolved object ?@timestamp
	 org.elasticsearch.xpack.esql.core.expression.UnresolvedAttribute.dataType(UnresolvedAttribute.java:121)
	 org.elasticsearch.xpack.esql.plan.logical.TimeSeriesAggregate.postAnalysisVerification(TimeSeriesAggregate.java:240)
	 org.elasticsearch.xpack.esql.analysis.Verifier.lambda$planCheckers$6(Verifier.java:233)
	 org.elasticsearch.xpack.esql.analysis.Verifier.lambda$verify$0(Verifier.java:113)
	 java.base/java.util.ArrayList.forEach(ArrayList.java:1604)
	 org.elasticsearch.xpack.esql.analysis.Verifier.lambda$verify$1(Verifier.java:113)
	 org.elasticsearch.xpack.esql.core.tree.Node.forEachDown(Node.java:72)
	 org.elasticsearch.xpack.esql.core.tree.Node.forEachDown(Node.java:76)
	 org.elasticsearch.xpack.esql.analysis.Verifier.verify(Verifier.java:107)
	 org.elasticsearch.xpack.esql.analysis.Analyzer.verify(Analyzer.java:268)
	 org.elasticsearch.xpack.esql.analysis.Analyzer.analyze(Analyzer.java:264)
	 org.elasticsearch.xpack.esql.session.EsqlSession.analyzedPlan(EsqlSession.java:1139)
	 org.elasticsearch.xpack.esql.session.EsqlSession.analyzeWithRetry(EsqlSession.java:1090)
	 org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$17(EsqlSession.java:701)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `929406ed7583ce591a52e27d2ac3574d2af8cf5b`
**Instance ID:** `elastic__elasticsearch-141503`
**Language:** `Java`
