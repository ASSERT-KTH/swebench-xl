# Task

## GET /_migration/deprecations doesn't check disk watermarks against correct settings values

This change moves the disk watermark check from all nodes to the master node since the check is performed against information in `ClusterInfo`. Also, it changes what setting values are used - using values from the cluster state if they are set, or from node settings otherwise.

There's a potential edge case: in a mixed cluster (e.g. master 9.2.1 (before the fix), other nodes 9.3 (after the fix)), the check wouldn't be performed. However, due to https://github.com/elastic/elasticsearch/issues/137004, the check isn't working in the released versions anyway, so this doesn't make things worse.

Closes #137005

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8c2f569f17430af28c24890056c396ad9c2dd24b`
**Instance ID:** `elastic__elasticsearch-138115`
**Language:** `Java`
