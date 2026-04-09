# Task

## ESQL: ROW not allowing using of previously-declared fields

While a query like this with EVAL works:
```
ROW x = 0 | EVAL x = 4, y = 2, z = x + y
```

This same query with ROW fails:
```
ROW x = 4, y = 2, z = x + y
```

With:
```
Unknown column [x], Unknown column [y]
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d19e1139060ee08d49986d675c63a0d7992cb77f`
**Instance ID:** `elastic__elasticsearch-140217`
**Language:** `Java`
