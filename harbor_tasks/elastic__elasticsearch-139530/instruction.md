# Task

## Add telemetry to track usage of sort

### Description

In particular usage of [script based sorting](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/sort-search-results#script-based-sorting) is of interest.

Search usage is collated in [SearchStatsUsage](https://github.com/elastic/elasticsearch/blob/main/server/src/main/java/org/elasticsearch/action/admin/cluster/stats/SearchUsageStats.java) which would be an appropriate place to track sort usage

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f7364e143f8af03779893d4f2b430b2c82eb1b38`
**Instance ID:** `elastic__elasticsearch-139530`
**Language:** `Java`
