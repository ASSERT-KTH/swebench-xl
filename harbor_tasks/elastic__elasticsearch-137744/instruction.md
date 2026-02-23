# Task

## Catch DateTimeException in EsqlDataTypeConverter

`DateTimeException` is not a fatal exception, it is an input error, so convert it to `IllegalArgumentException`

Fixes #137741

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4eade64dc6f1beb76d34d0471f80c1c62470ae3c`
**Instance ID:** `elastic__elasticsearch-137744`
**Language:** `Java`
