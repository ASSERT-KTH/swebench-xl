# Task

## ESQL: unmapped_fields="nullify"/"load" shouldn't nullify/load metadata, esp. _score

```sql
SET unmapped_fields=\"nullify\";
FROM employees
| LIMIT 1
| KEEP _score

    _score     
---------------
null
```

It doesn't make good sense to treat metadata the same way as regular fields, and therefore we also shouldn't nullify it. If a query has a `KEEP _id` and `_id` is missing, the user has to add `METADATA _id` to the `FROM`; nullifying this just hides a mistake.

Nullifying `_score` particularly just hides the fact that the query didn't actually perform any search.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `0da8e46bbd554752031ec0a94ced4c34603ff7dc`
**Instance ID:** `elastic__elasticsearch-143155`
**Language:** `Java`
