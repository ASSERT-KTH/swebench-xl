# Task

## Aggs: InternalFilter cannot be cast to class InternalMultiBucketAggregation, missing validation

Stacktrace:
```
Failed to execute phase [fetch], 
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.AbstractSearchAsyncAction.onPhaseFailure(AbstractSearchAsyncAction.java:624)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.SearchQueryThenFetchAsyncAction.onPhaseFailure(SearchQueryThenFetchAsyncAction.java:81)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.FetchSearchPhase$1.onFailure(FetchSearchPhase.java:88)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:29)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1067)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1095)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:619)
	at java.base/java.lang.Thread.run(Thread.java:1447)
Caused by: java.lang.ClassCastException: class org.elasticsearch.search.aggregations.bucket.filter.InternalFilter cannot be cast to class org.elasticsearch.search.aggregations.InternalMultiBucketAggregation (org.elasticsearch.search.aggregations.bucket.filter.InternalFilter and org.elasticsearch.search.aggregations.InternalMultiBucketAggregation are in module org.elasticsearch.server@9.2.0 of loader 'app')
	at org.elasticsearch.server@9.2.0/org.elasticsearch.search.aggregations.pipeline.BucketScriptPipelineAggregator.reduce(BucketScriptPipelineAggregator.java:52)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.search.aggregations.InternalAggregation.reducePipelines(InternalAggregation.java:119)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.search.aggregations.bucket.InternalSingleBucketAggregation.reducePipelines(InternalSingleBucketAggregation.java:142)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.search.aggregations.InternalAggregations.lambda$maybeExecuteFinalReduce$0(InternalAggregations.java:197)
	at java.base/java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:215)
	at java.base/java.util.AbstractList$RandomAccessSpliterator.forEachRemaining(AbstractList.java:722)
	at java.base/java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:570)
	at java.base/java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:560)
	at java.base/java.util.stream.ReduceOps$ReduceOp.evaluateSequential(ReduceOps.java:921)
	at java.base/java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:265)
	at java.base/java.util.stream.ReferencePipeline.collect(ReferencePipeline.java:727)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.search.aggregations.InternalAggregations.maybeExecuteFinalReduce(InternalAggregations.java:198)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.search.aggregations.InternalAggregations.topLevelReduce(InternalAggregations.java:187)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.QueryPhaseResultConsumer.aggregate(QueryPhaseResultConsumer.java:412)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.QueryPhaseResultConsumer.reduce(QueryPhaseResultConsumer.java:250)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.FetchSearchPhase.innerRun(FetchSearchPhase.java:96)
	at org.elasticsearch.server@9.2.0/org.elasticsearch.action.search.FetchSearchPhase$1.doRun(FetchSearchPhase.java:83)
```

Reproduce with:
```
{
  "size": 0,
  "aggs": {
    "by_birth_year": {
      "filter": {
        "term": {
          "gender": "M"
        }
      },
      "aggs": {
        "sum_languages": {
          "sum": {
            "field": "languages"
          }
        },
        "squared": {
          "bucket_script": {
            "buckets_path": {
              "sum_languages": "sum_languages"
            },
            "script": "params.sum_languages * params.sum_languages"
          }
        }
      }
    }
  }
}
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `3fea67d11674b98af10747da06fa4772ffcf7dba`
**Instance ID:** `elastic__elasticsearch-132320`
**Language:** `Java`
