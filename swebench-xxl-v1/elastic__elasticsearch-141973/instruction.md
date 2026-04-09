# Task

## NPE: Cannot invoke "Object.hashCode()" because "pk" is null

### Elasticsearch Version

serverless

### Problem Description

Somehow a null field name can get through query validation and result in the following stack trace:

```
java.lang.NullPointerException: Cannot invoke "Object.hashCode()" because "pk" is null
	at java.base/java.util.ImmutableCollections$MapN.probe(ImmutableCollections.java:1572)
	at java.base/java.util.ImmutableCollections$MapN.get(ImmutableCollections.java:1486)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.index.mapper.FieldTypeLookup.get(FieldTypeLookup.java:167)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.index.mapper.MappingLookup.getFieldType(MappingLookup.java:442)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.index.query.QueryRewriteContext.fieldType(QueryRewriteContext.java:303)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.index.query.QueryRewriteContext.getFieldType(QueryRewriteContext.java:294)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.search.collapse.CollapseBuilder.build(CollapseBuilder.java:205)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.search.SearchService.parseSource(SearchService.java:1817)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.search.SearchService.createContext(SearchService.java:1425)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.search.SearchService.executeQueryPhase(SearchService.java:885)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.search.SearchService.lambda$executeQueryPhase$7(SearchService.java:726)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionRunnable$3.accept(ActionRunnable.java:79)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionRunnable$3.accept(ActionRunnable.java:76)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionRunnable$4.doRun(ActionRunnable.java:101)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1113)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
```

### Steps to Reproduce

Unfortunately reproduction steps are not known at this point.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `78bf3d432e1a7e58356c9257c4e773608c74ddb9`
**Instance ID:** `elastic__elasticsearch-141973`
**Language:** `Java`
