# Task

## ES|QL: FUSE and MMR require a LIMIT

closes https://github.com/elastic/elasticsearch/issues/141428

For FUSE, we currently have a validation that checks that a PipelineBreaker exists before FUSE, but ideally we should check for LIMIT explicitly.
MMR does not have this validation, although it needs it for the same reasons as FUSE.
FUSE and MMR are meant to be run on the coordinator with a limited number of rows, not as part of a first stage retrieval that searches over all indexed documents.
FUSE and MMR also need to collect all the input rows, before they can output results, making it problematic if they have to deal with an unbounded number of rows.

Instead, we explicitly require a LIMIT to be used before FUSE and MMR.
FUSE had this validation before, but it does not work properly with subqueries which can have multiple branches of execution that have no limit.

This fixes the validation we have for FUSE and adds it to MMR too.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8c9f9b777d9b1c66fa09f0853e66ab7a0809ba33`
**Instance ID:** `elastic__elasticsearch-141523`
**Language:** `Java`
