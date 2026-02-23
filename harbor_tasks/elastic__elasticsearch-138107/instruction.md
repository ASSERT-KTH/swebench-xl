# Task

## ESQL: Make function tests with timezone or locale use random configurations

Closes https://github.com/elastic/elasticsearch/issues/107997

Since configurations were fully randomized, some tests requiring specific locales or timezones were changed to use a static config.

In this PR, those tests were updated to still use a random configuration, but override the single parameter they need to be static as part of the test case.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `c086b07d45cb291778daf22fe94e67481062f8a2`
**Instance ID:** `elastic__elasticsearch-138107`
**Language:** `Java`
