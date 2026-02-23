# Task

## ES|QL completion command constant folding

## Summary

This PR implements constant folding support for ESQL `COMPLETION` inference plans, allowing completion operations with constant prompts to be evaluated at optimization time rather than at query execution time.

Closes #136863

## Technical Details
- A CompletionFunction as a internal primitive only and  is not exposed to users.
- During the analysis phase in Analyzer::resolveInferencePlan where foldable Completion plans are converted to Eval nodes with CompletionFunction expressions

```
FROM books
| COMPLETION "Translate this text" WITH { "inference_id": "my-model" }
```

is internally rewritten into

```
FROM books
| EVAL completion=COMPLETION("Translate this text", "my-model")
```

- The pre-optimizer uses the InferenceFunctionEvaluator which handles the actual execution of the inference using CompletionOperator

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `6e29516862a3908800148e35a27e74e4c4c6c98f`
**Instance ID:** `elastic__elasticsearch-138112`
**Language:** `Java`
