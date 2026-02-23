# Task

## Esql skip null metrics

Resolves https://github.com/elastic/elasticsearch/issues/129524

This is meant to add a rewrite rule to filter out null metrics.  I'm opening this PR early to collect feedback from the Analytics Engine team on the approach.

This rule scans the query plan to collect all of the metric attributes, creates an isNotNull expression for each, and then combines them into a single filter.  For the initial version of this, we want to process any document that has any of the metrics in question, so we OR the filters together.

Feature Design Questions:
- Should we apply this filter even if the user has other filters or logic dealing with the given metric field?  e.g. if they have a `COALESCE` for that field already in the query?
    - At this point, the rule only collects metrics from `STATS` commands.  So if a field is coalesced and then we compute a statistic on that result, no metric will be collected for it.  This is a little fragile as written here, but it is working and it has tests.
- Is it correct to be OR'ing the filters together?
    - This seems correct.  We want all documents that have a metric value for any of the metrics involved in the query.

Implementation Questions: 
- Where is the correct place in the query planning process to apply this rule?  My instinct is that it should run in the "Finish Analysis" phase of the "Analyzer" step.  As written it should only run once, and it seems like it should run after references and union types have been resolved.  
    - Resolution: I discussed this with Fang, and we decided it was best placed in the substitutions phase of the logical plan optimizer.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `df8cedf9920c8bf710221ca8579bb90f64d4faa0`
**Instance ID:** `elastic__elasticsearch-133087`
**Language:** `Java`
