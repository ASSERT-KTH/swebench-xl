# Task

## [ES|QL] Better error on some queries missing timestamps

In some queries that drop the timestamp field, we are left with an
UnresolvedTimestamp that we try to fetch `dataType().typeName()` from,
but it fails because `dataType()` is null, resulting in a confusing
error message ("Invalid call to dataType on an unresolved object").
This commit instead appends the message the UnresolvedTimestamp holds
(which contains relevant errors) to the list of failures.

Resolves https://github.com/elastic/elasticsearch/issues/140606

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `929406ed7583ce591a52e27d2ac3574d2af8cf5b`
**Instance ID:** `elastic__elasticsearch-141503`
**Language:** `Java`
