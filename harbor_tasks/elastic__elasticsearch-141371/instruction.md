# Task

## [ES|QL] Fix Analyzer infinite loop for subquery referencing indices with empty mappings

Fix #141029 

After fixing the infinite loop in `Analyzer`, subquery referencing indices with empty mappings behave the same as when there is no subquery https://github.com/elastic/elasticsearch/issues/111545, this is a separate issue that needs to be addressed.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4a9d1b27718efd484d09c7aac3f62fcecc5d123c`
**Instance ID:** `elastic__elasticsearch-141371`
**Language:** `Java`
