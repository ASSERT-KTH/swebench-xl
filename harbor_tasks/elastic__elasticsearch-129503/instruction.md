# Task

## ESQL: LOOKUP JOIN push down optimizations

Compared to `ENRICH` (and other, similar plans like `GROK`, `DISSECT` and `EVAL`), we do not push down `LOOKUP JOIN`s.

That leads to suboptimal plans, e.g. because projections before and after the `LOOKUP JOIN` cannot be combined.

Example:
```
              FROM test
            | LOOKUP JOIN lookup_index1 ON field
            | RENAME foo AS b
            | LOOKUP JOIN lookup_index2 ON field
            | DROP b*
```
The `RENAME foo AS b` in between the `LOOKUP JOIN`s becomes an `EsqlProject`, which cannot be combined with the `EsqlProject` that comes from the `DROP b*` because the `LOOKUP JOIN lookup_index_2` is in the way. As a result, we cannot determine that the field `foo` obtained from the `lookup_index1` is actually dropped and unused in the end.

**Edit:** Let's also double check that there are no other existing optimizer rules that could (somewhat) easily be applied to `LOOKUP JOIN`.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `2502a363de7c42eb72fb78e3d1037f76afa399cc`
**Instance ID:** `elastic__elasticsearch-129503`
**Language:** `Java`
