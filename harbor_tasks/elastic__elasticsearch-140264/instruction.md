# Task

## [Native] BBQ Int4 to 1-bit dot product functions

This PR introduces the scaffolding needed for native dot product of a int4 query vector against 1-bit vectors, in BBQ.
The native function implementations already have optimized, platform specific versions, as the Panama versions were faster than vanilla native implementations:
- for ARM we have a NEON implementation (largely lifted from https://github.com/elastic/elasticsearch/pull/134623, thanks @iverase)
- on x64:
   - for AVX2, I used a combination of lookup tables and shuffling, as described in ["Faster Population Counts Using AVX2 Instructions"](https://arxiv.org/abs/1611.07612 and https://github.com/WojciechMula/sse-popcount)
   - for AVX-512, I used the `vpopcntq`, 512-bit wide popcount (very likely, the same that Panama translates to), plus some better prefetching.

The speedup is between none and 20% better for single scoring, and between 20-40% better for bulk scoring. This is without score adjustment, which is still done Java side (with Panama). That would be tackled in a follow-up, and it is expected to give it a bit more performance boost.

Benchmarks for various architectures and vendors can be found below.

Closes https://github.com/elastic/elasticsearch/issues/128523

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `95b72907fe83c51445c9c07226795c8f092d366c`
**Instance ID:** `elastic__elasticsearch-140264`
**Language:** `Java`
