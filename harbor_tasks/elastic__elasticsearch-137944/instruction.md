# Task

## Implement coerce for exponential_histogram field type

Closes #136605.

Also fixes a small bug in the T-Digest -> exponential histogram conversion: When parsing T-Digests, we do allow the count associated with a centroid to be zero, while we don't allow the same thing for exponential histograms. This PR adds a fix for correctly handling this case in the conversion code alongside with a test.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `2512d079948a33d9a6aa66d8992ab24e23ae479b`
**Instance ID:** `elastic__elasticsearch-137944`
**Language:** `Java`
