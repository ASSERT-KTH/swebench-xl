# Task

## Add warnings for lookup join after sort

### Elasticsearch Version

main

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

mac

### Problem Description

Add warnings for lookup join after sort as the lookup join will not preserve the order. 
Exception, if there is a sort after the lookup join and before the lookup join no warning is needed because the sort after will fix the order. 

### Steps to Reproduce

```
FROM test
| SORT x
| LOOKUP JOIN lookup_table ON key
| LIMIT 10
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `333357a5b17a5155bcdeb16c8ebe8f202cc71244`
**Instance ID:** `elastic__elasticsearch-141482`
**Language:** `Java`
