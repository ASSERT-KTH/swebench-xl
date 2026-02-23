# Task

## Panama vector implementation of codePointCount

Add Panama SIMD implementation of codePointCount. Keep SWAR version from https://github.com/elastic/elasticsearch/pull/140388 as fallback if SIMD not available. This results in a very large speedup on long strings, for example those over 100 bytes. Lucene's UnicodeUtil.codePointCount remains faster for small strings, so continue to use this version if byte length is below a threshold.

Fixes https://github.com/elastic/elasticsearch/issues/140567

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ad866649260c6a9fbf73c2a016cd4b91f687b6e1`
**Instance ID:** `elastic__elasticsearch-140693`
**Language:** `Java`
