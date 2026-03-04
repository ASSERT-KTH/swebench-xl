# Task

## ESQL: bug in ReplaceAliasingEvalWithProject: optimized incorrectly due to missing references

Once more! Straight from the generative tests (already shrunk):
```
row vKBRQmBiqSe = 1
| eval  HqAogEZW = RAZdNDZEWAnqxF,  kfkZrDpdlGhS = vKBRQmBiqSe, vKBRQmBiqSe = 4191264652016276724
| enrich languages_policy on HqAogEZW
| rename language_name as message
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `34145ed1d1ff9f06f225ae57c15c938f3797aacc`
**Instance ID:** `elastic__elasticsearch-137025`
**Language:** `Java`
