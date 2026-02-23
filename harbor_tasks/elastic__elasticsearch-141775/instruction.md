# Task

## ESQL: Handle aggs with surrogates in unit tests

Fixes https://github.com/elastic/elasticsearch/issues/139418

Aggs with surrogates were originally ignored in the agg functions unit tests, given their complexity, and integration with planning. This PR updates the test to simulate the bare minimum to execute and test them.

- Most changes are in how the unit tests execute. It's explained in detail here: https://github.com/elastic/elasticsearch/pull/141775/changes?w=1#diff-d530a32f5875f8d0f5919a5220dff51d96929c01f3ecc2649755bd278e26670cR327-R352
- Fix multiple test classes that were never executed to begin with, like AVG, SUM on some special types...

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `3ff07d610b9410253d88e4404bd46cf5737d991e`
**Instance ID:** `elastic__elasticsearch-141775`
**Language:** `Java`
