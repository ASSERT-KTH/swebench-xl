# Task

## Add coerce support for histogram and exponential_histogram field mappers

We want to allow switching to the `exponential_histogram` field type for OTLP ingestion use cases without breaking backwards compatibility.
This can cause two kinds of problems:
 * exponential-histogram JSON documents are attempted to be ingested into indices which use the `histogram` type: This can happen e.g. if the index template for a data stream has been adjusted, but a rollover has not happened yet
 * histogram JSON documents are attempted to be ingested into indices using the `exponential_histogram` type: Happens for example due to older OpenTelemetry collector versions running in parallel with newer ones, which already adjusted the field type


We decided on adding support for [coerce](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/coerce) to the `histogram` and `exponential_histogram` field mappers to cover these use cases:
 * [x] accept exponential histogram fields on `histogram` fields and convert them to T-Digest for `coerce` https://github.com/elastic/elasticsearch/pull/137191
 * [x] accept histogram fields (assuming T-Digest content) on `exponential_histogram` fields and convert them to exponential histograms for `coerce` #137944

The `histogram` field type content can be either T-Digests or HDR histograms. We decided on assuming T-Digest to implement this feature for the following reasons:
 * T-Digest and exponential histograms support negative values, while HDR histograms do not
 * T-Digest is the kind used in classic Elastic APM and the current EDOT Collector (OTLP ingest)

For the conversion from exponential histogram to T-Digest we'll use the same algorithm already implemented by the elasticsearch OTLP metrics endpoint. For the conversion from T-Digest to exponential histograms, we'll use an algorithm which ideally inverts this conversion, introducing as little error as possible.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `2512d079948a33d9a6aa66d8992ab24e23ae479b`
**Instance ID:** `elastic__elasticsearch-137944`
**Language:** `Java`
