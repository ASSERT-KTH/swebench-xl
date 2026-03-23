# Task

## ESQL: full-text function not considering a RENAMEd valid searchable field

### Description

```
from message_types
 | rename type AS id
 | where match_phrase(id, "world hello")
```

results in 

```
[MatchPhrase] function cannot operate on [id], which is not a field from an index mapping
```

but the simplified query

```
from message_types
 | where match_phrase(type, "world hello")
```

doesn't throw any verification errors.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ca1ec7d7c8dbb2b613e581d6d68ecf77c2e51eb1`
**Instance ID:** `elastic__elasticsearch-143893`
**Language:** `Java`
