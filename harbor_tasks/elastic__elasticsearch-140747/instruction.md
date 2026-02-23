# Task

## Optimize search shard iterator sort

Moved sorting of search shard iterators from the searchShards function that runs in the transport worker to after the CanMatch phase, which is in the search thread pool. Additionally, sorting only after the filter reduces CPU usage, especially relevant if the shard count is high relative to the result count.

Fixed #135472

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8a38cbbafee64879a0fd20ce16e8546f30057cee`
**Instance ID:** `elastic__elasticsearch-140747`
**Language:** `Java`
