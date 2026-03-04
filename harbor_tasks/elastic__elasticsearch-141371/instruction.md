# Task

## ESQL: subqueries on indices with no fields fail

### Description

Having an index with no fields[*], the following query fails:
```
FROM
    (FROM nofields),
    (FROM nofields)
```

with `ESQL request failed with status [INTERNAL_SERVER_ERROR]: org.elasticsearch.xpack.esql.rule.RuleExecutionException: Rule execution limit [100] reached`

due to ever applying `analysis.Analyzer$ResolveRefs`:
```
[TRACE][o.e.x.e.a.A.changes      ] [runTask-0] Rule analysis.Analyzer$ResolveRefs applied with change
UnionAll[[]]                                        = UnionAll[[]]
|_Project[[<no-fields>{r$}#2]]                      = |_Project[[<no-fields>{r$}#2]]
| \_Project[[<no-fields>{r$}#2]]                    = | \_Project[[<no-fields>{r$}#2]]
|   \_Project[[<no-fields>{r$}#2]]                  = |   \_Project[[<no-fields>{r$}#2]]
|     \_Project[[<no-fields>{r$}#2]]                = |     \_Project[[<no-fields>{r$}#2]]
|       \_Subquery[]                                ! |       \_Project[[<no-fields>{r$}#2]]
|         \_EsRelation[nofields][<no-fields>{r$}#2] ! |         \_Subquery[]
\_Project[[<no-fields>{r$}#2]]                      ! |           \_EsRelation[nofields][<no-fields>{r$}#2]
  \_Project[[<no-fields>{r$}#2]]                    ! \_Project[[<no-fields>{r$}#2]]
    \_Project[[<no-fields>{r$}#2]]                  !   \_Project[[<no-fields>{r$}#2]]
      \_Project[[<no-fields>{r$}#2]]                !     \_Project[[<no-fields>{r$}#2]]
        \_Subquery[]                                !       \_Project[[<no-fields>{r$}#2]]
          \_EsRelation[nofields][<no-fields>{r$}#2] !         \_Project[[<no-fields>{r$}#2]]
                                                    !           \_Subquery[]
                                                    !             \_EsRelation[nofields][<no-fields>{r$}#2]
```

[*] nofields:
```
PUT /nofields
{
    "mappings": {
        "dynamic": false
    }
}
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4a9d1b27718efd484d09c7aac3f62fcecc5d123c`
**Instance ID:** `elastic__elasticsearch-141371`
**Language:** `Java`
