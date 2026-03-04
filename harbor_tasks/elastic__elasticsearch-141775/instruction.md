# Task

## Add support for evaluating surrogate based aggregations in AbstractAggregationTestCase

In https://github.com/elastic/elasticsearch/pull/110579 we excluded surrogate-based aggregations from actually being evaluated in `AbstractAggregationTestCase`. As now in the meantime with `aggregate_metric_double`, `exponential_histogram` and `tdigest` a lot more surrogate-based aggregations have been implemented, we should revisit this and try to enable the evaluation in the tests.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `3ff07d610b9410253d88e4404bd46cf5737d991e`
**Instance ID:** `elastic__elasticsearch-141775`
**Language:** `Java`
