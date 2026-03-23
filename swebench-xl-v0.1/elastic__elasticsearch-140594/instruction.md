# Task

## PromQL: Improve function input type validation range vector / instant vector

In #140571 we caught an issue caused by using incompatible input type on PromQL function. 
PromQL has two primary concepts: range vectors and instant vectors and functions can operate on one or another. Right now, we don’t have any way to validate a given function is applied on a correct vector type. 

Example: 
This query is invalid:
```
avg(network.bytes_in[10m])
```
The valid one would be this:
```
avg(network.bytes_in)
```
The avg function needs an instant vector as an argument, not a range vector.

If we had a better definition of which inputs and outputs a PromQL function expects, we could properly verify this and also generate documentation from it.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e0a15c4ec6c6ce200e28cb3e420c7c91ea69441a`
**Instance ID:** `elastic__elasticsearch-140594`
**Language:** `Java`
