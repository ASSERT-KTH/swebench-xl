# Task

## `date` field types fail to index specific malformed data even with `ignore_malformed` enabled

### Elasticsearch Version

8.14

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

-

### Problem Description

As noticed in #109410 if a value of `date` or `date_nanos` field is an object, indexing such value will fail even with `ignore_malformed` enabled. This behavior differs from other field types like numbers.

### Steps to Reproduce

```
PUT /my_index
{
  "mappings": {
      "properties": {
          "date": {
              "type": "date",
              "ignore_malformed": true
          }
        }
    }
  }
}

// OK
PUT my_index/_doc/1
{
  "date": "hello"
}

// Fails
PUT my_index/_doc/2
{
  "date": {"string": "hello"}
}
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ac50d22735ccc81dd3aad144b4d43858761e8fa0`
**Instance ID:** `elastic__elasticsearch-143533`
**Language:** `Java`
