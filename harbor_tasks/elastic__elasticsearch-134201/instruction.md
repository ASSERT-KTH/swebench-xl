# Task

## ESQL: Ensure we fail nicely for invalid INLINESTATS queries

Examples:
- INLINESTATS with CATEGORIZE (c.f. https://github.com/elastic/elasticsearch/issues/124717)
- INLINESTATS with SORT (#113727)
- ~INLINESTATS with no aggregates, e.g. `INLINESTATS BY group, expr = foo(...)`~
- ~INLINESTATS in CCQ scenarios (c.f. #124748)~

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `18037bb05c91e05cddb707b993382ed5ad14ded4`
**Instance ID:** `elastic__elasticsearch-134201`
**Language:** `Java`
