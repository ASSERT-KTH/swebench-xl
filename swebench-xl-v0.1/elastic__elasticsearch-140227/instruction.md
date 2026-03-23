# Task

## ESQL: TS Command, grouping on value that is sometimes null causes unexpected partial results

In this query:
```
ts k8* 
| STATS count(rate(network.total_cost)) 
BY region, bucket(@timestamp,1hour)
```
`region:keyword` is not present in the `k8s-downsampled` index, which I suspect is the source of this error.


Error:
```
    java.lang.AssertionError: unexpected partial results: _clusters={details={(local)={_shards={total=2, failed=2, successful=0, skipped=0}, took=267, indices=k8*, failures=[{node=null, reason={reason=class org.elasticsearch.compute.data.DocBlock cannot be cast to class org.elasticsearch.compute.data.BytesRefBlock (org.elasticsearch.compute.data.DocBlock and org.elasticsearch.compute.data.BytesRefBlock are in unnamed module of loader java.net.URLClassLoader @2213639b), type=class_cast_exception}, index=k8s, shard=0}], status=partial}}}
    Expected: (null or is <false>)
         but: was <true>
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `70c3ef7a0780ccffaa955f39ed69c5696ef6b418`
**Instance ID:** `elastic__elasticsearch-140227`
**Language:** `Java`
