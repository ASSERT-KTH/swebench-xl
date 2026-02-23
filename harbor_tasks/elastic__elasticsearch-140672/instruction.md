# Task

## [ES|QL] Implementing rerank on multi values.

## Summary

This PR changes how the ES|QL `RERANK` command handles input fields for reranking. 
Multi-value fields are now processed natively, with each value sent individually to the reranking model.

Closes: https://github.com/elastic/elasticsearch/issues/136865

## Functional Changes

### Multi-value field handling
When a rerank field contains multiple values (e.g., a multi-valued `author` field), each value is now sent separately to the inference service for scoring and the max score is returned. 
Previously, vlaues fields were combined into a single YAML document before being sent to the model.

Example:

```
FROM books
| WHERE title:"Leo Tolstoy"
| RERANK "Leo Tolstoy" ON author WITH { "inference_id" : "my_reranker" }}
```

If a document has author: ["John Hockenberry", "Leo Tolstoy", "Pat Conroy"], each author value is now scored independently rather than being formatted as a YAML list. 

### Rerank fields restricted to string types only

The RERANK command now only accepts string fields. Numeric and boolean fields are no longer supported as rerank inputs.

### Can use an expression without a name as a RERANK field

In previous version it was required to specify the name of the computed field when using and expression as a rerank field:

```
| RERANK "my query" ON truncated_description = SUBSTRING(description, 0, 100)
```

Now that we do not use an intermediary YAML, it is not necessary anymore and you can use the expression directly:

```
| RERANK "my query" ON SUBSTRING(description, 0, 100)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `a00bdaa4540a020b9fffcdb28e19c393f6734175`
**Instance ID:** `elastic__elasticsearch-140672`
**Language:** `Java`
