# Task

## Revisit automatic rollover criteria for tiny retentions

### Description

Currently when using DLM, the rollover criteria have an "automatic" part which adjusts the `max_age` depending on the retention of the data stream itself:

- If retention is null aka infinite (default), max_age will be 30 days
- If retention is configured to anything lower than 14 days, max_age will be 1 day
- If retention is configured to anything lower than 90 days, max_age will be 7 days
- If retention is configured to anything greater than 90 days, max_age will be 30 days

This works well for data stream data, which usually has a long-ish retention. However, in the case of the failure store, it's possible that we may only want to keep data for 1 day, in which case we're potentially keeping up to 50gb of failures in the "hot" tier when it could be moved off. Some users may only want to keep failures for a few hours.

We should consider whether we should adjust these criteria to have a smaller `max_age` for tiny retentions (something like rolling over every 6 hours for a 1 day retention, for example).

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d9783aded0854f34276f3a1ed4ec371b11303440`
**Instance ID:** `elastic__elasticsearch-134941`
**Language:** `Java`
