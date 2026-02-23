# Task

## Add histogram as a metric type of an exponential histogram

This PR introduces the `time_series_metric` parameter to the `exponential_histogram` mapper to allow a user to define it as a metric.

Furthermore, we introduce a new non scalar time series metric: `histogram`. Currently, the `histogram` metric type is not protected by a feature flag but it's only used by the `exponential_histogram` type which is behind a feature flag.


Resolves: https://github.com/elastic/elasticsearch/issues/138161

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `0fb42ed2338627e9639d0f57856b037951c08336`
**Instance ID:** `elastic__elasticsearch-138366`
**Language:** `Java`
