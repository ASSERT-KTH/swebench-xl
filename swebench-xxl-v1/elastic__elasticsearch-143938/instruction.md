# Task

## ESQL: illegal query_string option [boost]

### Description

```
from employees | where qstr("world", {"boost": 1})
```

```
        "type": "illegal_argument_exception",
        "reason": "illegal query_string option [boost]",
        "stack_trace": "java.lang.IllegalArgumentException: illegal query_string option [boost]\r\n\tat org.elasticsearch.xpack.esql.core.querydsl.query.QueryStringQuery.lambda$asBuilder$23(QueryStringQuery.java:98)\r\n\tat java.base/java.util.HashMap.forEach(HashMap.java:1430)\r\n\tat org.elasticsearch.xpack.esql.core.querydsl.query.QueryStringQuery.asBuilder(QueryStringQuery.java:94)
```

even though `boost` seems to be an allowed option.
```
from employees | where qstr("world", {"booooooost": 1})
```

suggests this list of options: 

```
default_operator, fuzzy_max_expansions, analyze_wildcard, rewrite, minimum_should_match, default_field, phrase_slop, boost, fuzzy_prefix_length, time_zone, allow_leading_wildcard, quote_analyzer, quote_field_suffix, max_determinized_states, auto_generate_synonyms_phrase_query, lenient, analyzer, enable_position_increments]"
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ec61d8856b7a98b9ca87d2a2ab9db661c0969bc9`
**Instance ID:** `elastic__elasticsearch-143938`
**Language:** `Java`
