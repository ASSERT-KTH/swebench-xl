# Task

## ESQL: TS command ignores aliases in BY

Reproduces with the csv data set:
```
TS k8s | STATS max_bytes=max(to_long(network.total_bytes_in)) BY foobar = cluster

   max_bytes   |    cluster    
---------------+---------------
10797          |qa             
7403           |staging        
10277          |prod  
```
The aliasing of `cluster` to `foobar` is being ignored. The second column should be called `foobar`.
```
TS k8s | STATS max_bytes=max(to_long(network.total_bytes_in)) BY foobar = cluster | keep max_bytes, foobar

   max_bytes   |    cluster    
---------------+---------------
10797          |qa             
7403           |staging        
10277          |prod  

{"error":{"root_cause":[{"type":"illegal_state_exception","reason":"Found 1 problem\nline 1:1: Plan [Project[[max_bytes{r}#397, foobar{r}#394]]] optimized incorrectly due to missing references [foobar{r}#394]"}],"type":"illegal_state_exception","reason":"Found 1 problem\nline 1:1: Plan [Project[[max_bytes{r}#397, foobar{r}#394]]] optimized incorrectly due to missing references [foobar{r}#394]"},"status":500}
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `5e1d131cde2f5265280171987f6150b817100e49`
**Instance ID:** `elastic__elasticsearch-143489`
**Language:** `Java`
