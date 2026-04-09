# Task

## ESQL: nullify not working in STATS with WHERE edge case

Reproducer (make `test` have any mapping, it shouldn't matter):
```
SET unmapped_fields=nullify;
│ FROM test
| EVAL entity.id = \"foo\"
| STATS host.entity.id = VALUES(host.entity.id) WHERE host.entity.id IS NOT NULL
│ BY entity.id

{"error":{"root_cause":[{"type":"verification_exception","reason":"Found 1 problem\nline 1:120: Unknown column [host.entity.id], did you mean [entity.id]?"}],"type":"verification_exception","reason":"Found 1 problem\nline 1:120: Unknown column [host.entity.id], did you mean [entity.id]?"},"status":400}
```

Also happens with `ROW`:

```
SET unmapped_fields=nullify;
│ ROW x = 1
| EVAL entity.id = \"foo\"
| STATS host.entity.id = VALUES(host.entity.id) WHERE host.entity.id IS NOT NULL
│ BY entity.id
```

Somehow, we got an interaction with the `EVAL` - it doesn't repro without that.

Seems to have been introduced by https://github.com/elastic/elasticsearch/pull/141340.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1d95a03766b2814b70c0e5d57d12fa414c35749d`
**Instance ID:** `elastic__elasticsearch-144029`
**Language:** `Java`
