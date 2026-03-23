# Task

## ESQL: INLINE STATS null grouping/joining

### Description

There's a difference between how `STATS` behaves compared to `INLINE STATS` caused by `null` grouping/joining that we should look into:
```
ROW x = 1
| STATS c = COUNT(*) BY n = null
| KEEP c, n
| LIMIT 1
```
yields:
```
       c       |       n       
---------------+---------------
1              |null           
```

However,
```
ROW x = 1
| INLINE STATS c = COUNT(*) BY n = null
| KEEP c, n
| LIMIT 1
```
yields:
```
       c       |       n       
---------------+---------------
null           |null           
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ff7d81aa094f1181494f7b6412a8490eb12c7c67`
**Instance ID:** `elastic__elasticsearch-140027`
**Language:** `Java`
