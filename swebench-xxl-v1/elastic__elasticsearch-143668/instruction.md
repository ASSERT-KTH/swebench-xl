# Task

## ESQL: zero_terms_query is not accepted for MATCH even though it should be accepted

### Description

```
from employees
| where match(first_name, "foo", {"zero_terms_query": "all"})
```

results in 

```
"type": "illegal_argument_exception",
"reason": "illegal match option [zero_terms_query]",
"stack_trace": "org.elasticsearch.ElasticsearchException$1: illegal match option [zero_terms_query]
```

While writing 

```
from employees
| where match(first_name, "foo", {"foobar": "all"})
```

will have an error that mention `zero_terms_query` as being accepted:

```
"reason": "Found 1 problem\nline 3:9: Invalid option [foobar] in [match(first_name, \"foo\", {\"foobar\": \"all\"})], expected one of [auto_generate_synonyms_phrase_query, minimum_should_match, prefix_length, lenient, zero_terms_query, analyzer, fuzzy_transpositions, fuzzy_rewrite, fuzziness, max_expansions, boost, operator]",
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e186163fd04d66ccdddda64c2716ce832f9f7465`
**Instance ID:** `elastic__elasticsearch-143668`
**Language:** `Java`
