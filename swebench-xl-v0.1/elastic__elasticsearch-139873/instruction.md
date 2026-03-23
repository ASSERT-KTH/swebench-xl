# Task

## PromQL: add support for parameters in PromQL query

For example:

```
PROMQL step=?_step rate(http_requests_total[?_step])
```

This should work already: `step=?_step`. Parameters are resolved with `ExpressionBuilder#paramByNameOrPosition`.

This isn't supported yet: `rate(http_requests_total[?_step])`. We get an ANTLR ParsingException (`no viable alternative at input 'rate(http_requests_total[?'`) here because the PromQL grammar doesn't support parameters.

The quick and dirty workaround would be to replace parameters in the opaque `promqlQuery` string before invoking the PromQL parser:

https://github.com/elastic/elasticsearch/blob/99ced4f765e22df3c11dc092032618bf2da1892c/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/parser/LogicalPlanBuilder.java#L1284-L1290

Another option is to adjust the PromQL grammar itself to add support for parameters. This lets us control in a more fine-grained way where we support double and single params. That's likely a bit more involved and we'll need to re-implement things in `PromqlExpressionBuilder` but my first instinct is that this is a the cleaner solution.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f4bb553fff4e7c4187924e4eb272e27dc6217c40`
**Instance ID:** `elastic__elasticsearch-139873`
**Language:** `Java`
