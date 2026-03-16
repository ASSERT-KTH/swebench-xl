# Task

## ESQL: Remote ENRICH needs to check for upstream FORKs

Looking at `Enrich#postAnalysisPlanVerification`, there doesn't seem to be anything that prevents a `FORK` upstream from remote-only `ENRICH`; however, I believe `FORK` requires merging on the coordinator, so a remote-only `ENRICH` doesn't make sense.

Cc @smalyshev , @ioanatia

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `178c0c9ae47d28388687bcdcb035c792dd22a0e1`
**Instance ID:** `elastic__elasticsearch-131945`
**Language:** `Java`
