# Task

## ES|QL: Better error messages for FUSE when required columns are missing

FUSE by default looks for the `_id`, `_index`, `_score` and `_fork` columns.
When one of these are missing, because we don't have `METADATA _id, _index, _score` or don't use FORK, we return the standard error message when `UnresolvedAttributes` are left in the analyzed plan.

For example:
```
FROM wikipedia
| FORK (WHERE title:"Europe")
       (WHERE content:"Europe")
| FUSE
```

Errors:

```
line 5:3: Unknown column [_id]
line 5:3: Unknown column [_index]
line 5:3: Unknown column [_score]"""
```

we can improve these messages to explain that FUSE could not find a column to score on, to group by etc

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `099e10f53e165d56d16f37d700ed26a76bb7ddcd`
**Instance ID:** `elastic__elasticsearch-141592`
**Language:** `Java`
