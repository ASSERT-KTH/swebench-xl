# Task

## ES|QL: Optimize vector similarity functions when one arg is a constant

related meta issue: https://github.com/elastic/elasticsearch/issues/125783

The main use case for the vector similarity functions is for doing exact NN search.
In this case one of the arguments will be a vector query, which will always be a constant.
Which means we have an opportunity to further optimize the `SimilarityEvalutator`.

For example, when one argument is a constant there is probably no need to call `EvalOperator.ExpressionEvaluator:::eval` here for each page:

https://github.com/elastic/elasticsearch/blob/e3cef723a636a682707cd149f612521b32529149/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/expression/function/vector/VectorSimilarityFunction.java#L132

We can evaluate only once and then reuse the value.
We have seen that we spend a significant amount a time with `EvalMapper$Literals:::block` and this is the most likely culprit.

The other thing we can do when one arg is a constant, is to stop copying the values in the float array for every row we evaluate:

https://github.com/elastic/elasticsearch/blob/e3cef723a636a682707cd149f612521b32529149/x-pack/plugin/esql/src/main/java/org/elasticsearch/xpack/esql/expression/function/vector/VectorSimilarityFunction.java#L164-L165

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `7f7e4a797ff7d6e4e6459fd88c834286fd40d378`
**Instance ID:** `elastic__elasticsearch-135602`
**Language:** `Java`
