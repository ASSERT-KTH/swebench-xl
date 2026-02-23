# Task

## Ensure integer sorts are rewritten to long sorts for BWC indexes

Older indexes used long sorts for integer fields, and we need to ensure that
sorts against these fields do not conflict.  Recent refactoring in 
IndexNumericSortField missed a case where this could happen.

Closes #139127
Closes #139128

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `a0ee98ca7580948520308aa9486ae9b09f7b94d2`
**Instance ID:** `elastic__elasticsearch-139293`
**Language:** `Java`
