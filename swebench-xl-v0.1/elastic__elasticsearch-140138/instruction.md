# Task

## PromQL: apply same default limit as TS

For the TS|STATS command, we're adding a default limit of 1M. When using PromQL, we apply the generic default limit of ES|QL. Let's treat PromQL the same way as TS|STAS when it comes to the limit.

Code pointer:

https://github.com/elastic/elasticsearch/blob/1fbb4114706bb8719e3ab15e017f5a2ec29dfae6/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/analysis/Analyzer.java#L1577-L1594

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `aa56256c71f9911707112748963ec68f0f35d7b1`
**Instance ID:** `elastic__elasticsearch-140138`
**Language:** `Java`
