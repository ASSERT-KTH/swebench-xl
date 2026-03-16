# Task

## [ILM] Avoid race condition between shrinking and ILM itself

In the ILM Shrink action, ILM performs (among others) the following steps:
https://github.com/elastic/elasticsearch/blob/0ae817e5b60d3801cb02a2b7586573dd8ca72b1d/x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/ilm/ShrinkAction.java#L174-L176
The `ShrinkStep` copies the ILM policy name in the shrink request:
https://github.com/elastic/elasticsearch/blob/0ae817e5b60d3801cb02a2b7586573dd8ca72b1d/x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/ilm/ShrinkStep.java#L85
However, when the allocation of the shards of the shrunken index takes "some" time (which is not unexpected for larger shards), which is what the second step waits for, ILM starts executing the policy on the shrunken index _before_ the ILM execution state has been copied to that index (step three). This means ILM will start executing the policy from the beginning for the shrunken index, causing the `WaitForRolloverReadyStep` to fail [here](https://github.com/elastic/elasticsearch/blob/0ae817e5b60d3801cb02a2b7586573dd8ca72b1d/x-pack/plugin/core/src/main/java/org/elasticsearch/xpack/core/ilm/WaitForRolloverReadyStep.java#L104-L116), instead of proceeding in the `shrink` action.

This is not necessarily harmful, it's just "noisy" - there is no data loss, it only produces some error logs and possibly a `yellow` health API status.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `2407358fe06935f5f8df7e634a16bc9bb9ac33d5`
**Instance ID:** `elastic__elasticsearch-129455`
**Language:** `Java`
