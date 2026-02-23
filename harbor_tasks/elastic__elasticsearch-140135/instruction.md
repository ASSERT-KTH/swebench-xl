# Task

## Add support for top-level arithmetic ops to TS|STATS

This is what's happening at a high level:
* `TranslateTimeSeriesAggregate` now not only handles `AggregateFunctions`, but all `Functions`, including `BinaryScalarFunction`s
* Going into `TranslateTimeSeriesAggregate`, the aggregates are not be split up into evals anymore. The `TranslateTimeSeriesAggregate` rule now runs earlier in the optimizer (before `ReplaceAggregateNestedExpressionWithEval` and friends). 
  * Enables adding all `TimeSeriesAggregateFunction`s to the first aggregation phase, without some `TimeSeriesAggregateFunction`s being placed in nested `Eval`s.
  * Also ensures sure we can properly insert the default `last_over_time` function for expressions like `foo + 1` or `max(foo + 1)`, before the inner `foo + 1` is extracted into an eval.
* Nested expressions in the groupings of the `TimeSeriesAggregate` are still be replaced with an eval to make time bucket handling easier. 
* Extracts the injection of the default `last_over_time` function outside of `TranslateTimeSeriesAggregate` and into the analysis phase, so that `InsertFromAggregateMetricDouble` runs after the insertion of `last_over_time`. If it would execute later, the `last_over_time` function can't be resolved for downsampling indices where metrics are of type `aggregate_metric_double`. It needs to run after field resolution as the injection of the default inner agg is type-dependent - we have a different strategy for histograms.
* `TimeSeriesGroupByAll` has been moved from the initialize to the resolution phase of the analyzer - after `InsertDefaultInnerTimeSeriesAggregate`, so that it can take that into account. That also fixes a missing reference issue in the nested eval for queries like `network.total_bytes_in * 8`.


Queries that are supported now but weren't before:
* Bare metric (with group-by-all)
  * `TS k8s | STATS network.cost`
* Group by all now supports post processing
  * `TS k8s | STATS network.cost | SORT network.cost`
  * Previously, there was a bug that complained about missing references as the id of the alias changed
* Top-level arithmetic operations between metric and scalar
  * `TS k8s | STATS 10 + max(10 + network.total_bytes_in)`
  * Also supports implicit last_over_time and group-by-all
  * `TS k8s | STATS network.total_bytes_in * 8`
* Top-level arithmetic operations between metric and metric
  * Also supports implicit last_over_time and group-by-all
  * `TS k8s | STATS in_n_out=network.eth0.rx + network.eth0.tx`
  * `TS k8s | STATS max(last_over_time(network.eth0.tx::double) /  (last_over_time(network.eth0.tx::double) + last_over_time(network.eth0.rx::double)))`


closes https://github.com/elastic/elasticsearch/issues/139570, https://github.com/elastic/elasticsearch/issues/138702, https://github.com/elastic/elasticsearch/issues/139580


Child PRs
- https://github.com/elastic/elasticsearch/pull/140130
- https://github.com/elastic/elasticsearch/pull/140248
- https://github.com/elastic/elasticsearch/pull/140270
- https://github.com/elastic/elasticsearch/pull/140090

PromQL support will be added in a follow-up:
- https://github.com/elastic/elasticsearch/pull/140541

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e4590010f0a9d1d1cd88b5cbc046014aa333e5c7`
**Instance ID:** `elastic__elasticsearch-140135`
**Language:** `Java`
