# Task

## Address es819 tsdb doc values format performance bug

* The DISIAccumulator should only be used during merging.
* The tmp files created by DISIAccumulator and OffsetsAccumulator shouldn't use mmap based lucene directory.

Closes #135340

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `bc7da67cd9b6a5fad54c52ee27fb0d0ea6435137`
**Instance ID:** `elastic__elasticsearch-135505`
**Language:** `Java`
