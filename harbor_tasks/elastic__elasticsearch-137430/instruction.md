# Task

## ES|QL - Full text functions accept null as field parameter

Closes https://github.com/elastic/elasticsearch/issues/136608

Full text functions that take a field as a parameter should allow null as a field parameter. This is necessary as the field may not be present on an index mapping, and the local optimizer replaces it by null.

We allow null as a field in FullTextFunctions, meaning that they are nullable and will be replaced by `NULL`.

This PR also refactors full text functions that depend on a single field (`MATCH`, `MATCH_PHRASE`, `KNN`) to use a common superclass (`SingleFieldFullTextFunction`) that contains the common field logic.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ffa76e57d6ea7e5e9e02b7a44e2a55bf4e3e5d6d`
**Instance ID:** `elastic__elasticsearch-137430`
**Language:** `Java`
