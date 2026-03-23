# Task

## Support friendlier times on `_snapshot/elastic/elasticsearch/_status?human=true`

The [`get snapshot status`](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-snapshot-status) API does support the `?human=true` option, but it doesn't seem to include formatting the `start_time`:

```
$ diff -u <(jq '.snapshots[0].stats' status_20260126133822.json) <(jq '.snapshots[0].stats' status_20260126133745.json)
--- /dev/fd/11  2026-01-26 13:40:11
+++ /dev/fd/12  2026-01-26 13:40:12
@@ -1,16 +1,20 @@
 {
   "incremental": {
     "file_count": 20976,
+    "size": "25.3gb",
     "size_in_bytes": 27198261919
   },
   "processed": {
-    "file_count": 20973,
-    "size_in_bytes": 21420277061
+    "file_count": 17540,
+    "size": "11.5gb",
+    "size_in_bytes": 12394843449
   },
   "total": {
     "file_count": 865606,
+    "size": "9.3tb",
     "size_in_bytes": 10310377190084
   },
   "start_time_in_millis": 1769452628028,
-  "time_in_millis": 75032
+  "time": "38.2s",
+  "time_in_millis": 38218
 }
```

I think it would be a reasonable enhancement to add support for a human readable `start_time` for the overall snapshot, the indices, and their shards; this would match the current handling of `time_in_millis` and `time` at those same levels.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e7f0bdd2acf9dc923b1e3d9da575604c49d2dab0`
**Instance ID:** `elastic__elasticsearch-141479`
**Language:** `Java`
