# Task

## ESQL: Provide appropriate messages when can't execute INLINESTATS

This adds the guards to reject queries that INLINESTATS cannot currently execute:
- SORT with no LIMIT before INLINESTATS
- CATEGORIZE with INLINESTATS.

Closes #124725

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `18037bb05c91e05cddb707b993382ed5ad14ded4`
**Instance ID:** `elastic__elasticsearch-134201`
**Language:** `Java`
