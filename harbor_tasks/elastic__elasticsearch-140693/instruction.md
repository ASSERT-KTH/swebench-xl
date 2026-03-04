# Task

## Examine a Panama Vector implementation of Fast codePointCount

The changes in #140388 use SWAR techniques to processes 8 bytes at once. If this is performance critical, let's evaluate writing an implementation using the Panama Vector API, so that we can leverage wider registers/instructions.

A useful place to start is to look at how `ESVectorUtil::indexOf` is implemented. I would expect`codePointCount` to be implemented in a similar way.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ad866649260c6a9fbf73c2a016cd4b91f687b6e1`
**Instance ID:** `elastic__elasticsearch-140693`
**Language:** `Java`
