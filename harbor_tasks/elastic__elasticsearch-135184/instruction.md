# Task

## Bug fix, last optimised value in `ESUTF8StreamJsonParser` kept old value.

In https://github.com/elastic/elasticsearch/pull/134790 we introduced a bug that was caught by our tests.;

The problem manifested itself when a multi field mapper would call `getText()` which would set `_tokenIncomplete` to false after the `getOptimisedText()`. This would evaluate the condition `_currToken == JsonToken.VALUE_STRING && _tokenIncomplete && stringEnd > 0` to false and the `lastOptimisedValue` would not be reset.

We changed the code to always reset the `lastOptimisedValue` when a `next*()` method is called. 

Furthermore, we introduced a randomised unit test that creates two `XContentParser`s and runs one as a baseline using none of the optimised code and the other one is accessing both optimised and non optimised in a random pattern. This test was able to catch both #134770 & #135256.

Fixes #135256

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `651314e8b9f7de8f67992e9e1559069a9e9ecbf4`
**Instance ID:** `elastic__elasticsearch-135184`
**Language:** `Java`
