# Task

## ES|QL TOP_SNIPPETS multi-valued field support

ES|QL functions [do not support multi-valued fields by default](https://www.elastic.co/docs/reference/query-languages/esql/esql-multivalued-fields#esql-multivalued-fields-functions) However we believe that multi-valued fields should be supported in ES|QL when using the `TOP_SNIPPETS` function. 

Refer to `TO_LOWER` as an example of a regular function that supports multi-valued input.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e41e1efb5d9eb722b88c19ba805142ea3d6c3e0c`
**Instance ID:** `elastic__elasticsearch-142117`
**Language:** `Java`
