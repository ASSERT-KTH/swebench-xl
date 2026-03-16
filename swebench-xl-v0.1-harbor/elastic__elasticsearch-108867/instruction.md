# Task

## Failure to merge mappings of field named `properties`

### Elasticsearch Version

8.14.0

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

Darwin

### Problem Description

The new merge algorithm of raw field mappings that was merged through #97317 introduced a new failure when merging mappings of fields named `properties`. See details in the [comment](https://github.com/elastic/elasticsearch/pull/97317#issuecomment-2112857574) posted to the related PR.

### Steps to Reproduce

Merging:
```
  "template": {
    "mappings": {
      "properties": {
        "properties": {
          "properties": {
            "child1": {
              "type": "text"
            }
          }
        }
      }
    }
  }
```
with:
```
  "template": {
    "mappings": {
      "properties": {
        "properties": {
          "properties": {
            "child2": {
              "type": "long"
            }
          }
        }
      }
    }
  }
```
should yield:
```
  "template": {
    "mappings": {
      "properties": {
        "properties": {
          "properties": {
            "child1": {
              "type": "text"
            },
            "child2": {
              "type": "long"
            }
          }
        }
      }
    }
  }
```
but instead yields:
```
  "template": {
    "mappings": {
      "properties": {
        "properties": {
          "properties": {
            "child2": {
              "type": "long"
            }
          }
        }
      }
    }
  }
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `a80b7f62dbc99b3b6a5dc2b8d937ebd9fffbcdcd`
**Instance ID:** `elastic__elasticsearch-108867`
**Language:** `Java`
