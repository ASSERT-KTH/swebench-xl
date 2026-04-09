# Task

## ESQL: prune more unneeded columns

### Description

A query like:
```
FROM employees
| DISSECT first_name "%{msg}"
| EVAL salaryK = salary / 1000
| KEEP emp_no
```
will produce a plan like:
```
EsqlProject[[emp_no{f}#249]]
\_Dissect[first_name{f}#251,Parser[pattern=%{msg}, appendSeparator=, parser=org.elasticsearch.dissect.DissectParser@4187c918],[msg{r}#242]]
  \_Limit[1000[INTEGER],false]
    \_EsRelation[employees][emp_no{f}#249, first_name{f}#251, salary{f}#250]
```

The `salaryK` / `EVAL` is dropped, but `DISSECT` isn't. This is to investigate dropping more computation that's eventually discarded anyways.

Laterally: `salary` seems to still be loaded, might need a side issue.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ed27c61c556b0f17a9bfe37d7c3f87d084edf48b`
**Instance ID:** `elastic__elasticsearch-140982`
**Language:** `Java`
