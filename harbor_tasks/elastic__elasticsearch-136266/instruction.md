# Task

## ES|QL: fix Page.equals()

Two pages with `positionCount=0` should be considered not equal if they have different number/type of blocks.

This change also makes `equals()` coherent with `hashCode()`, that already accounted for blocks

Fixes: https://github.com/elastic/elasticsearch/issues/135977
Fixes: https://github.com/elastic/elasticsearch/issues/135990

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f74e8e460c86a54fa051d8cd52d44fbb1c78ea99`
**Instance ID:** `elastic__elasticsearch-136266`
**Language:** `Java`
