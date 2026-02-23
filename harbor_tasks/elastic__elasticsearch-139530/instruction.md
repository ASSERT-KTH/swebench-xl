# Task

## Add sort field usage to telemetry

Adds tracking for the `sort` section in a query and leverages the extended reporting added in https://github.com/elastic/elasticsearch/pull/135306 to record the particular type of sort used. 

An alternative option was to raise `sort` to a top level field in the `SearchUsageStats` class along with queries, rescorers and retrievers but sort does not feel special enough to be a top level field and using extended data solves the problem of passing the sort type.


Closes https://github.com/elastic/elasticsearch/issues/139513

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f7364e143f8af03779893d4f2b430b2c82eb1b38`
**Instance ID:** `elastic__elasticsearch-139530`
**Language:** `Java`
