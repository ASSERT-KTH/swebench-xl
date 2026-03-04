# Task

## Avoid storing ignored source for multi-fields

in case of multi-fields, the "parent" field is responsible for tracking the source. Other fields should not track source, e.g. in case of a keyword exceeding the `ignore_above` limit.

This was partially addressed in #129126 but needs to be generalized.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `caff54f13602703b8fa9aaa2f638e4220df31c3b`
**Instance ID:** `elastic__elasticsearch-132962`
**Language:** `Java`
