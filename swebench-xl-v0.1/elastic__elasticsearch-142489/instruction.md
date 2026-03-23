# Task

## ESQL: Incorrect ExchangeExecs in node reduce plan

This is a follow-up to an issue discovered in #141082. It seems that the `ExchangeExec` in `ComputeService.reductionPlan` is created using the old output attributes rather than the new one, and because the Exchange wrapping happens after the local optimization, we don't have a consistency check that verifies this isn't happening.

This is technically *fine*, since in reality the exchanges just pipe whatever pages they get, ignoring their declared output, but it *is* messy and should be fixed. In addition, we should add a consistency check (that only runs during tests) to ensure this doesn't happen again.

Possible lead: https://github.com/elastic/elasticsearch/blob/abce9512a7d0c84f2839391f86a52f009a3b73d9/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/plugin/LateMaterializationPlanner.java#L131
though there may be other places.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `774543ebfc068f1565e3ae06a6018c98135983ec`
**Instance ID:** `elastic__elasticsearch-142489`
**Language:** `Java`
