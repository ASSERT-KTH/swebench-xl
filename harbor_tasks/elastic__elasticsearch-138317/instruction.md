# Task

## Reinstate and test the native int7u bulk dot product

This commit reinstates, fixes, and tests the native int7u bulk dot product #138239 

The issue with the original change is that `size_t` is 64 bit, while we pass a 32 bit `int` from java. This is also arguably an issue with the other native definitions, but doesn't cause an issue because of position in the declaration (last). We should fix these declarations, but as a separate PR.

closes #138302

Relates to https://github.com/elastic/elasticsearch/issues/139059

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `816d5015b6ab5c49bd0cdc00c7e1ed1c1a966780`
**Instance ID:** `elastic__elasticsearch-138317`
**Language:** `Java`
