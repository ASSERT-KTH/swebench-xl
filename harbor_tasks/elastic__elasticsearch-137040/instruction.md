# Task

## ESQL: introduce a new interface to declare functions depending on the `@timestamp` attribute

This updates the way the `@timestamp` field is injected into the functions that require it implicitly: these functions no longer need to declare an attribute themselves, the function registry will do it for them.

Followingly, this can be traced from the source and eventually wired into the functions (so that renames no longer be problematic).

Closes #136772

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `772e6a18997f3f5594f783072f7e35dac626d62f`
**Instance ID:** `elastic__elasticsearch-137040`
**Language:** `Java`
