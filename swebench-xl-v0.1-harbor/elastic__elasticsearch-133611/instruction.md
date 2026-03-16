# Task

## Flattened fields fail to reconstruct synthetic source with keys consisting only of dots

### Elasticsearch Version

main (9.1.x)

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

Linux 6.8.0-60-generic #63~22.04.1-Ubuntu

### Problem Description

The flattened types accepts keys that only consist of dots, eg `.` and `..`. But when synthetic source is enabled, the source cannot be reconstructed for objects with these keys.

Field names like this are not allowed as keys in other object types. Ideally, we should consider disallowing such field names in flattened objects. Whether or not, they are disallowed, synthetic source should be able to reconstruct objects that currently contain such keys. 

### Steps to Reproduce

```
curl -X PUT "localhost:9200/my-index" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "mode": "logsdb",
    "index.mapping.source.mode": "synthetic"
  },
  "mappings": {
    "properties": {
        "test": {
            "type": "flattened"
        }
    }
  }
}
' | jq

curl -X POST "localhost:9200/my-index/_doc" -H 'Content-Type: application/json' -d'
{
  "@timestamp": "2025",
  "test": {
      ".": 124
    }
}
' | jq

curl localhost:9200/my-index/_search | jq
```

This search returns a 400 with the following error:
```
{
  "error": {
    "root_cause": [
      {
        "type": "illegal_argument_exception",
        "reason": "fromIndex(0) > toIndex(-1)"
      }
    ],
    "type": "search_phase_execution_exception",
    "reason": "all shards failed",
    "phase": "query",
    "grouped": true,
    "failed_shards": [
      {
        "shard": 0,
        "index": "my-index",
        "node": "SvVEiNpnR3y_4mV4enqKLg",
        "reason": {
          "type": "illegal_argument_exception",
          "reason": "fromIndex(0) > toIndex(-1)",
          "suppressed": [
            {
              "type": "illegal_state_exception",
              "reason": "Failed to close the XContentBuilder",
              "caused_by": {
                "type": "i_o_exception",
                "reason": "Unclosed object or array found"
              }
            }
          ]
        }
      }
    ],
    "caused_by": {
      "type": "illegal_argument_exception",
      "reason": "fromIndex(0) > toIndex(-1)",
      "caused_by": {
        "type": "illegal_argument_exception",
        "reason": "fromIndex(0) > toIndex(-1)",
        "suppressed": [
          {
            "type": "illegal_state_exception",
            "reason": "Failed to close the XContentBuilder",
            "caused_by": {
              "type": "i_o_exception",
              "reason": "Unclosed object or array found"
            }
          }
        ]
      }
    }
  },
  "status": 400
}

```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1b877f4b9d15e5c6ac936263119d71f1e39aa90e`
**Instance ID:** `elastic__elasticsearch-133611`
**Language:** `Java`
