# Task

## ES|QL: fix null folding of nested COALESCE

COALESCE can't be folded if one of the children is null, even if it's nested inside other expressions.
The same applies to all the functions that don't have `Nullability.TRUE` (eg. `Case` and `MvUnion`)

Fixes: https://github.com/elastic/elasticsearch/issues/139344

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cba13bc83e252cb3b3014cf4e74311b3433c89c1`
**Instance ID:** `elastic__elasticsearch-140028`
**Language:** `Java`
