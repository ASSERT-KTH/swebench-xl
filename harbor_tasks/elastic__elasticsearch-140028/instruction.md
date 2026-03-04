# Task

## ESQL: FoldNull can wrongly fold COALESCE to null

Reproducer:
```
ROW x = null
| EVAL z = COALESCE(x, "1")
| EVAL append_coalesce = MV_APPEND("2", COALESCE(x, "1"))
| EVAL append_z = MV_APPEND("2", z)

       x       |       z       |append_coalesce|   append_z    
---------------+---------------+---------------+---------------
null           |1              |null           |[2, 1]   
```
`append_coalesce` should be the same as `append_z`.

Looking at the change logger output, it looks like the problem is inside `FoldNull`:

```
[2025-12-11T10:09:59,716][TRACE][o.e.x.e.o.L.changes      ] [runTask-0] Rule logical.FoldNull applied with change
Limit[1000[INTEGER],false,false]                                                                                      = Limit[1000[INTEGER],false,false]
\_Eval[[COALESCE(x{r}#14,1[KEYWORD]) AS z#17, MVAPPEND(2[KEYWORD],COALESCE(x{r}#14,1[KEYWORD])) AS append_coalesce#20 ! \_Eval[[COALESCE(x{r}#14,1[KEYWORD]) AS z#17, null[KEYWORD] AS append_coalesce#20, MVAPPEND(2[KEYWORD],z{r}#17) AS ap
, MVAPPEND(2[KEYWORD],z{r}#17) AS append_z#23]]                                                                       ! pend_z#23]]
  \_Row[[null[NULL] AS x#14]]                                                                                         =   \_Row[[null[NULL] AS x#14]]
```

We shouldn't have folded to null because `COALESCE(null, "1")` should be `"1"`.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cba13bc83e252cb3b3014cf4e74311b3433c89c1`
**Instance ID:** `elastic__elasticsearch-140028`
**Language:** `Java`
