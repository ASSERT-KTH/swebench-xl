# Task

## [ML] Inconsistent validation of detectors between Java and C++

*Original comment by @davidkyle:*

The x-pack plugin allows you to use the `non_null_sum` function with an `over_field`

But when you open the job autodetect rejects this configuration
```
EMAIL REDACTED Function non_null_sum() cannot be used with an 'over' field
EMAIL REDACTED Failed to process token 'non_null_sum(derivative)'
```

`bool CFieldConfig::isPopulation(EFunction function)` returns false for this function 

Resolve this conflict.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `9ea48832198e5c40aa651142bdaeb36d8139aca2`
**Instance ID:** `elastic__elasticsearch-139946`
**Language:** `Java`
