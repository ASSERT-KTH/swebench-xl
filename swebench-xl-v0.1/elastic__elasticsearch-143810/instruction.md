# Task

## ESQL: disallow unmapped_fields="load" with full-text search/`MATCH`

While it's logical that we cannot run a full-text search on an unmapped field, ~maybe~ we should fail queries with `unmapped_fields="load"` rather than just returning an empty set.

To repro, unmap the `version` field (of type `version`) from the `apps` index
```
{
    "dynamic" :  false,
    "properties" : {
        "id" : {
            "type" : "integer"
        },
        "name" : {
            "type" : "keyword"
        }
    }
}
```
and run this altered version of `match-operator.testMatchVersionFieldAsString`:
```
testMatchVersionFieldAsString
required_capability: match_operator_colon
required_capability: match_additional_types

SET unmapped_fields="load";
from apps 
| where version:"2.1" 
| keep name, version;

name:keyword | version:keyword
bbbbb        | 2.1
;


Expected more data but no more entries found after [0]
Data mismatch:

Actual:
name:keyword | version:keyword

Expected:
name:keyword | version:keyword
bbbbb   
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cdaa5c75b9ef044eb4c6fcb30e7f1bb5c37bf717`
**Instance ID:** `elastic__elasticsearch-143810`
**Language:** `Java`
