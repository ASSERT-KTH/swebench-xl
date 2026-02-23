# Task

## ES|QL: fix folding of case() function with date period and time duration

Temporal amounts (`date_period`, `time_duration`) don't have an associated `ElementType` (yet), so we can't use evaluators to fold `case()` when they are involved. We have to do it manually.

Fixes: https://github.com/elastic/elasticsearch/issues/138415

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b3b7f97b07904b3b17d49af1ce9d7a2035fb3672`
**Instance ID:** `elastic__elasticsearch-141157`
**Language:** `Java`
