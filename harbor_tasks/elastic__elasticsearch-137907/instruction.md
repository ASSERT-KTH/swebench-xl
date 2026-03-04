# Task

## ES|QL: PruneColumns fails to prune columns when forked

Consider this simple query:
```
FROM employees | KEEP first_name | EVAL x = 1.0 | DROP x
```
In this case, the `PruneColumns` rule will remove `EVAL x` in the first (non-local) logical optimization.
But for this query:
```
FROM employees | KEEP first_name | EVAL x = 1.0 | DROP x 
| FORK (WHERE true) (WHERE true) | WHERE _fork == "fork1" | DROP _fork
```
It will not. The `x` field will eventually get dropped in the local logical optimization, but this might be too late, e.g., when performing the late materialization added in #132757.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4a14f83b1659a4315105e6a77a3c098b709863a4`
**Instance ID:** `elastic__elasticsearch-137907`
**Language:** `Java`
