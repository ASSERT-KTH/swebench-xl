# Task

## [ES|QL] Add error message when using inline stats on TS before stats

This commit adds a clearer error message when attempting to use inline stats in a TS query before a stats command (or on its own), which is unsupported at the moment.

Resolves #136092

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `da10e19340314fb6ee92293d97e0651c2cababc3`
**Instance ID:** `elastic__elasticsearch-136348`
**Language:** `Java`
