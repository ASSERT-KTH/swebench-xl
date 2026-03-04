# Task

## Expand verification in synthetic source tests to avoid double storing fields

Currently, we can store fields in many different ways: a stored field, a fallback stored field, ignored source, doc_values, etc. As we've previously seen, when not explicitly checked in tests, this can have unintended consequences on query performance. For example, loading a field via a stored field is a lot more efficient than synthesizing the entire source and loading the field from that. Unfortunately, our tests don't see the difference between the two, unless we explicit add code to verify where the field is being loaded from.

It would be beneficial to have tests verify the expected storage "medium" for a field. Not only will this help us catch latency performance issues before they're shipped, but it can also avoid double storing things.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4b315bcab0cfc4682a6a5308cc588403f8432563`
**Instance ID:** `elastic__elasticsearch-139715`
**Language:** `Java`
