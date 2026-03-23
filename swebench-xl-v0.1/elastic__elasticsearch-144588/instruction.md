# Task

## Failure in ExponentialHistogramPercentilesAggregatorTests.testCustomPercentiles

### CI Link

https://gradle-enterprise.elastic.co/s/pvktqhbmurnds/tests/task/:x-pack:plugin:analytics:test/details/org.elasticsearch.xpack.analytics.aggregations.metrics.ExponentialHistogramPercentilesAggregatorTests/testCustomPercentiles?top-execution=1

### Repro line

./gradlew ":x-pack:plugin:analytics:test" --tests "org.elasticsearch.xpack.analytics.aggregations.metrics.ExponentialHistogramPercentilesAggregatorTests.testCustomPercentiles" -Dtests.seed=7C531DAE615C757 -Dtests.locale=es-SV -Dtests.timezone=SystemV/CST6CDT -Druntime.java=25	

### Does it reproduce?

Yes

### Applicable branches

main

### Failure history

https://gradle-enterprise.elastic.co/scans/tests?search.startTimeMax=1773964799999&search.startTimeMin=1773273600000&search.timeZoneId=Europe%2FLondon&tests.container=org.elasticsearch.xpack.analytics.aggregations.metrics.ExponentialHistogramPercentilesAggregatorTests&tests.test=testCustomPercentiles

### Failure excerpt

```
java.lang.AssertionError: Percentiles should be non-decreasing
        at __randomizedtesting.SeedInfo.seed([7C531DAE615C757:BEBBB6D444D49997]:0)
        at org.junit.Assert.fail(Assert.java:89)
        at org.junit.Assert.assertTrue(Assert.java:42)
        at org.elasticsearch.xpack.analytics.aggregations.metrics.ExponentialHistogramPercentilesAggregatorTests.lambda$testCustomPercentiles$17(ExponentialHistogramPercentilesAggregatorTests.java:138)
        at org.elasticsearch.search.aggregations.AggregatorTestCase.testCase(AggregatorTestCase.java:881)
        at org.elasticsearch.xpack.analytics.aggregations.metrics.ExponentialHistogramPercentilesAggregatorTests.testCase(ExponentialHistogramPercentilesAggregatorTests.java:204)
        at org.elasticsearch.xpack.analytics.aggregations.metrics.ExponentialHistogramPercentilesAggregatorTests.testCustomPercentiles(ExponentialHistogramPercentilesAggregatorTests.java:130)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `880df183fc6e8bcf9b2369ba41a8a94010128df5`
**Instance ID:** `elastic__elasticsearch-144588`
**Language:** `Java`
