# Task

## KQL  - Prevent boolean operators from being used as literals in tests

The KqlParserBooleanQueryTests were failing because the random query generator could pick boolean operators (AND, OR, NOT) as query terms. This would result in queries like "mapped_string":"AND AND NOT", which the parser would interpret as a MatchQueryBuilder instead of the expected BoolQueryBuilder, causing assertion failures.

 Fixes #133863
 Fixes #133871

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cce52ddb0c051225a681aa83beb6891e7484a2fc`
**Instance ID:** `elastic__elasticsearch-134328`
**Language:** `Java`
