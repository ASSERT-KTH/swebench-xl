# Task

## Add recover_failure_document processor to restore failurestore docs to original form

In our docs at https://www.elastic.co/docs/manage-data/data-store/data-streams/failure-store-recipes#create-a-pipeline-to-convert-failure-documents we currently describe how to remediate documents from the failure store using a Painless script. 

To make things less error-prone, this PR encapsulates this functionality into a processor.

e.g.
```
POST localhost:9200/_ingest/pipeline/_simulate
{
    "pipeline": {
        "processors": [
            {
                "recover_failure_document": {}
            }
        ]
    },
    "docs": [
        {
            "_index": ".fs-my-datastream-ingest-2025.05.09-000001",
            "_id": "HnTJs5YBwrYNjPmaFcri",
            "_score": 1,
            "_source": {
                "@timestamp": "2025-05-09T06:41:24.775Z",
                "document": {
                    "index": "my-datastream-ingest",
                    "source": {
                        "@timestamp": "2025-04-21T00:00:00Z",
                        "counter_name": "test"
                    }
                },
                "error": {
                    "type": "illegal_argument_exception",
                    "message": "field [counter] not present as part of path [counter]",
                    "stack_trace": "j.l.IllegalArgumentException: field [counter] not present as part of path [counter] at o.e.i.IngestDocument.getFieldValue(IngestDocument.java: 202 at o.e.i.c.SetProcessor.execute(SetProcessor.java: 86) 14 more",
                    "pipeline_trace": [
                        "complicated-processor"
                    ],
                    "pipeline": "complicated-processor",
                    "processor_type": "set",
                    "processor_tag": "copy to new counter again"
                }
            }
        }
    ]
}
```
returns the following response:
```
{
    "docs": [
        {
            "doc": {
                "_index": "my-datastream-ingest",
                "_version": "-3",
                "_id": "HnTJs5YBwrYNjPmaFcri",
                "_source": {
                    "@timestamp": "2025-04-21T00:00:00Z",
                    "counter_name": "test"
                },
                "_ingest": {
                    "pre_recovery": {
                        "@timestamp": "2025-05-09T06:41:24.775Z",
                        "_index": ".fs-my-datastream-ingest-2025.05.09-000001",
                        "document": {
                            "index": "my-datastream-ingest"
                        },
                        "_id": "HnTJs5YBwrYNjPmaFcri",
                        "error": {
                            "pipeline": "complicated-processor",
                            "processor_type": "set",
                            "processor_tag": "copy to new counter again",
                            "pipeline_trace": [
                                "complicated-processor"
                            ],
                            "stack_trace": "j.l.IllegalArgumentException: field [counter] not present as part of path [counter] at o.e.i.IngestDocument.getFieldValue(IngestDocument.java: 202 at o.e.i.c.SetProcessor.execute(SetProcessor.java: 86) 14 more",
                            "type": "illegal_argument_exception",
                            "message": "field [counter] not present as part of path [counter]"
                        },
                        "_version": -3
                    },
                    "timestamp": "2025-09-04T22:32:12.800709Z"
                }
            }
        }
    ]
}
```


Using this processor for an invalid failure-doc results in an error, e.g.:

```
POST localhost:9200/_ingest/pipeline/_simulate

{
    "pipeline": {
        "processors": [
            {
                "recover_failure_document": {}
            }
        ]
    },
    "docs": [
        {
            "_index": ".fs-my-datastream-ingest-2025.05.09-000001",
            "_id": "HnTJs5YBwrYNjPmaFcri",
            "_score": 1,
            "_source": {
                "@timestamp": "2025-05-09T06:41:24.775Z",
                "error": {
                    "type": "illegal_argument_exception",
                    "message": "field [counter] not present as part of path [counter]",
                    "stack_trace": "j.l.IllegalArgumentException: field [counter] not present as part of path [counter] at o.e.i.IngestDocument.getFieldValue(IngestDocument.java: 202 at o.e.i.c.SetProcessor.execute(SetProcessor.java: 86) 14 more",
                    "pipeline_trace": [
                        "complicated-processor"
                    ],
                    "pipeline": "complicated-processor",
                    "processor_type": "set",
                    "processor_tag": "copy to new counter again"
                }
            }
        }
    ]
}
```
returns

```
{
    "docs": [
        {
            "error": {
                "root_cause": [
                    {
                        "type": "illegal_argument_exception",
                        "reason": "field [document] not present as part of path [document]"
                    }
                ],
                "type": "illegal_argument_exception",
                "reason": "field [document] not present as part of path [document]"
            }
        }
    ]
}
```

Closes [#132940](https://github.com/elastic/elasticsearch/issues/132940)

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `41fea9d8a715b1e2ffb668c3cf54c6c9645f0331`
**Instance ID:** `elastic__elasticsearch-133360`
**Language:** `Java`
