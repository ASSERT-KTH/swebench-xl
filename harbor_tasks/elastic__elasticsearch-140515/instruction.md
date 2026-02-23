# Task

## Ids Query: Use max result window as upper limit

This can serve as a relatively simple protection against specifying too many ids. Does not take memory account, only the max result window setting, which could also be set too high, but defaults to 10k.

Closes #138758

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `eed907ba00891ffc46c0bb8357582e37141e2416`
**Instance ID:** `elastic__elasticsearch-140515`
**Language:** `Java`
