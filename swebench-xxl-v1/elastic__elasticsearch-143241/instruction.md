# Task

## IOOB in native code for byte vectors

### Elasticsearch Version

9.4+

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

any

### Problem Description

Getting an IOOB in native code paths when executing search/merge over a larger vector space.



### Steps to Reproduce

We have seen this occur with the byte_vector nightly benchmark, but not reliably reproducible yet.

### Logs (if relevant)

```
org.apache.lucene.index.MergePolicy$MergeException: java.lang.IndexOutOfBoundsException: Range [0, 0 + 2048) out of bounds for length -152026096
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.index.engine.InternalEngine$5.doRun(InternalEngine.java:3085)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
Caused by: java.lang.IndexOutOfBoundsException: Range [0, 0 + 2048) out of bounds for length -152026096
	at java.base/jdk.internal.util.Preconditions.outOfBounds(Preconditions.java:100)
	at java.base/jdk.internal.util.Preconditions.outOfBoundsCheckFromIndexSize(Preconditions.java:118)
	at java.base/jdk.internal.util.Preconditions.checkFromIndexSize(Preconditions.java:397)
	at java.base/java.util.Objects.checkFromIndexSize(Objects.java:417)
	at org.elasticsearch.nativeaccess@9.4.0-SNAPSHOT/org.elasticsearch.nativeaccess.jdk.JdkVectorLibrary$JdkVectorSimilarityFunctions.checkBulkOffsets(JdkVectorLibrary.java:299)
	at org.elasticsearch.simdvec@9.4.0-SNAPSHOT/org.elasticsearch.simdvec.internal.Similarities.dotProductI8BulkWithOffsets(Similarities.java:237)
	at org.elasticsearch.simdvec@9.4.0-SNAPSHOT/org.elasticsearch.simdvec.internal.ByteVectorScorerSupplier$MaxInnerProductSupplier.bulkScoreFromSegment(ByteVectorScorerSupplier.java:308)
	at org.elasticsearch.simdvec@9.4.0-SNAPSHOT/org.elasticsearch.simdvec.internal.ByteVectorScorerSupplier.bulkScoreFromOrds(ByteVectorScorerSupplier.java:64)
	at org.elasticsearch.simdvec@9.4.0-SNAPSHOT/org.elasticsearch.simdvec.internal.ByteVectorScorerSupplier$1.bulkScore(ByteVectorScorerSupplier.java:153)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswGraphSearcher.searchLevel(HnswGraphSearcher.java:340)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswGraphBuilder.addGraphNodeInternal(HnswGraphBuilder.java:255)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswGraphBuilder.addGraphNode(HnswGraphBuilder.java:222)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswConcurrentMergeBuilder$ConcurrentMergeWorker.addGraphNode(HnswConcurrentMergeBuilder.java:204)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswGraphBuilder.addVectors(HnswGraphBuilder.java:210)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswConcurrentMergeBuilder$ConcurrentMergeWorker.run(HnswConcurrentMergeBuilder.java:184)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.util.hnsw.HnswConcurrentMergeBuilder.lambda$build$0(HnswConcurrentMergeBuilder.java:90)
	at java.base/java.util.concurrent.FutureTask.run(FutureTask.java:328)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.search.TaskExecutor$Task.run(TaskExecutor.java:173)
	at org.apache.lucene.core@10.3.2/org.apache.lucene.search.TaskExecutor.lambda$invokeAll$1(TaskExecutor.java:98)
	at org.elasticsearch.server@9.4.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingRunnable.run(ThreadContext.java:1047)
	... 3 more
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `246fcfd9e3c7b3658a8ad0ecd71557173bc6bfd6`
**Instance ID:** `elastic__elasticsearch-143241`
**Language:** `Java`
