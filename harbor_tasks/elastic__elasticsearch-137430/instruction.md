# Task

## ESQL: MATCH function failing on locally missing field

### Description

A query like `FROM ... | WHERE MATCH(first_name, ...)` will currently fail to be planned, if `first_name` is `null` locally.
The failure is a `org.elasticsearch.xpack.esql.VerificationException` : `"[MATCH] function cannot operate on [first_name], which is not a field from an index mapping"`.
The reason is the way the planning goes with the locally null fields, replacing all found `FieldAttribute`s with `null` of the type in `ReplaceFieldWithConstantOrNull`:
```
  1> [2025-10-15T04:22:54,014][TRACE][o.e.x.e.o.L.changes      ][testMatchOnMissingField] Rule local.ReplaceFieldWithConstantOrNull applied with change
  1> Limit[1000[INTEGER],false]                                                  = Limit[1000[INTEGER],false]
  1> \_Filter[MATCH(first_name{f}#4,value[KEYWORD])]                             ! \_Filter[MATCH(null[KEYWORD],value[KEYWORD])]
  1>   \_EsRelation[test][_meta_field{f}#9, emp_no{f}#3, first_name{f}#4, gen..] !   \_Project[[_meta_field{f}#9, emp_no{f}#3, first_name{r}#4, gender{f}#5, hire_date{f}#10, job{f}#11, job.raw{f}#12, langu
  1>                                                                             ! ages{f}#6, last_name{f}#7, long_noidx{f}#13, salary{f}#8]]
  1>                                                                             !     \_Eval[[null[KEYWORD] AS first_name#4]]
  1>                                                                             !       \_EsRelation[test][_meta_field{f}#9, emp_no{f}#3, first_name{f}#4, gen..]
```

A fix could be to adjust the rule, but adjusting the function to allow `null`s is probably better.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ffa76e57d6ea7e5e9e02b7a44e2a55bf4e3e5d6d`
**Instance ID:** `elastic__elasticsearch-137430`
**Language:** `Java`
