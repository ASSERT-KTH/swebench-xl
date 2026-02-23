# Task

## ESQL: Multiple patterns for grok command

Closes https://github.com/elastic/elasticsearch/issues/132486

This PR adds the ability to specify multiple grok patterns as part of a single grok command. Consistent with the grok processor for ingest pipelines, they are tried in order, the first matching one is actually applied:

```
POST _query
{
  "query": """
    ROW col1="123 This is a test" | GROK col1 "%{UUID:def}", "%{WORD:xxx}"
  """
}
```

returns

```
       col1       |      def      |      xxx
------------------+---------------+---------------
123 This is a test|null           |123
```

It's not allowed to have different types for the same semantic names in different patterns:

```
POST _query
{
  "query": """
    ROW col1="123 This is a test" | GROK col1 "%{UUID:def}", "%{INT:def}"
  """
}
```

returns

```
{"error":{"root_cause":[{"type":"parsing_exception","reason":"line 1:33: Invalid GROK pattern [(?:%{UUID:def})|(?:%{INT:def})]: the attribute [def] is defined multiple times with different types"}],"type":"parsing_exception","reason":"line 1:33: Invalid GROK pattern [(?:%{UUID:def})|(?:%{INT:def})]: the attribute [def] is defined multiple times with different types"},"status":400}
```

This can be considered syntactic sugar over a more complex manual pattern.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `0dcf3ed2e37c12b5829108a3551b1f468349a5d7`
**Instance ID:** `elastic__elasticsearch-136541`
**Language:** `Java`
