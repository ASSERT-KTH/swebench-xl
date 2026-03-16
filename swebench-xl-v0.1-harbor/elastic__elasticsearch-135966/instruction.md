# Task

## [ML] Reindex hangs when deployment forcefully shuts down

### Elasticsearch Version

latest

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

ECH

### Problem Description

While reindexing data using a semantic text field in the destination index, the reindex task can hang when a deployment is stopped upon assignment rebalancing.

### Steps to Reproduce

1. Create an ECH cluster with 2 ML nodes (2 zones) 8 GB nodes
2. Upload the marco data set (https://github.com/elastic/stack-docs/blob/main/docs/en/stack/ml/nlp/data/msmarco-passagetest2019-unique.tsv) or use the example data shipped with Kibana
3. Create an index `test-data` from the test data
4. Create an inference endpoint for elser
```
PUT _inference/sparse_embedding/test
{
  "service": "elasticsearch",
  "service_settings": {
    "model_id": ".elser_model_2_linux-x86_64",
    "num_threads": 1,
    "num_allocations": 2,
    "adaptive_allocations": {
      "enabled": false
    }
  }
}
```

This will force one allocation to be on each node.

We can ensure this has happened by checking the node stats: `GET _ml/trained_models/_stats`. We should see one allocation on each node.

5. Create the destination index

```
PUT dest-index
{
  "mappings": {
    "properties": {
      "column2": {
        "type": "text",
        "copy_to": "infer_field"
      },
      "infer_field": {
        "type": "semantic_text",
        "inference_id": "test"
      }
    }
  }
}
``` 

6. Perform a reindex from `test-data` to `dest-index`

```
POST _reindex?wait_for_completion=false
{
  "source": {
    "index": "test-data",
    "size": 1000
  },
  "dest": {
    "index": "dest-index"
  },
  "max_docs": 2000
}
```

Make sure to save the task id for reference later

7. Force the deployment on one of the nodes to stop by reducing the allocation count

```
PUT _inference/sparse_embedding/test/_update
{
  "service_settings": {
    "model_id": ".elser_model_2_linux-x86_64",
    "num_threads": 1,
    "num_allocations": 1
  }
}
```

This should cause the deployment to stop on one of the nodes but remain on the other one.

8. Observe that the inference counts are still increasing on the deployment that still exists

Poll `GET _ml/trained_models/_stats` a few times and ensure the `inference_stats.inference_count` is still increasing.

9. Note that the reindex task does not complete

Once it stops increasing, the reindex task will not complete with failures, instead when we retrieve the task it will show that it is not completed.

It'll likely show something like this

```
GET /_tasks/{task_id}
```

```
{
  "completed": false,
  "task": {
    "node": "nrA_ZbXYQCWyggxOpCoKUA",
    "id": 3167795,
    "type": "transport",
    "action": "indices:data/write/reindex",
    "status": {
      "total": 2000,
      "updated": 0,
      "created": 0,
      "deleted": 0,
      "batches": 1,
      "version_conflicts": 0,
      "noops": 0,
      "retries": {
        "bulk": 0,
        "search": 0
      },
      "throttled_millis": 0,
      "requests_per_second": -1,
      "throttled_until_millis": 0
    },
    "description": "reindex from [test-data] to [dest-index]",
    "start_time_in_millis": 1757692996623,
    "running_time_in_nanos": 2927073854341,
    "cancellable": true,
    "cancelled": false,
    "headers": {
      "trace.id": "464fbe4a5ac684bdd31f2e2df0e246b5"
    }
  }
}
```

In addition to this, there won't be any documents in the destination index.

### Logs (if relevant)

There should be logs like this showing that some requests were skipped because the deployment was forcefully shutdown

```
[instance-0000000003] [test] clearing [52] requests pending results
[instance-0000000003] [inference process] notifying [35] queued requests that have not been processed before shutdown
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e47b044350304ad67d26f816453ccca3e492da85`
**Instance ID:** `elastic__elasticsearch-135966`
**Language:** `Java`
