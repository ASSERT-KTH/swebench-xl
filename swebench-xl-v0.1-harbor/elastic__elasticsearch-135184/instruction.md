# Task

## ESUTF8StreamJsonParser does not reset correctly the last optimised value.

### Elasticsearch Version

main, 9.1, 8.19

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

n/a

### Problem Description

The last optimised value does not get properly reset and its reused later in different fields. 

### Steps to Reproduce

``` 
# Create an index with the following mapping:
PUT /my-index
{
  "mappings": {
    "_data_stream_timestamp": {
      "enabled": true
    },
    "properties": {
      "@timestamp": {
        "type": "date"
      },
      "my-funky-field": {
        "type": "keyword",
        "fields": {
          "subfield_text": {
            "type": "text"
          }
        }
      },
      "my-poor-field": {
        "type": "ip"
      }
    }
  }
}

# Index the following document
POST /my-index/_doc
{
  "@timestamp": "2024-01-01T10:00:52.000Z",
  "my-funky-field": "14`\\%+",
  "my-poor-field": [
      "184.123.133.116"
    ]
}
```
Then we see the error:
```
"caused_by": {
      "type": "illegal_argument_exception",
      "reason": "'14`\\%+' is not an IP string literal."
    }
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `651314e8b9f7de8f67992e9e1559069a9e9ecbf4`
**Instance ID:** `elastic__elasticsearch-135184`
**Language:** `Java`
