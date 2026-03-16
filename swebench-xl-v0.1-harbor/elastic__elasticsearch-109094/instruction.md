# Task

## TSDB rollover logs should default to Debug

### Description

We have adopted TSDB widely. One of the most common log messages are these TSDB logs:

> [elasticsearch.server][INFO] [.ds-metrics-prometheus.collector-default-2024.04.03-000867] updating [index.time_series.end_time] from [2024-04-04T08:03:44.000Z] to [2024-04-04T08:08:43.000Z]

They don't really add much value from an end-user perspective. I thus believe those should be logged at debug level only.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d367c117937865bdbe9a06b7638b1ba7f308be5f`
**Instance ID:** `elastic__elasticsearch-109094`
**Language:** `Java`
