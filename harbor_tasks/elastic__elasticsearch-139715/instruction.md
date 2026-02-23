# Task

## Check field storage when synthetic source is enabled, in tests

Currently, when testing field mappers against synthetic source, we rarely check if fields are stored appropriately and not double stored. This has led to regressions in releases and in serverless that go unnoticed; the most recent example being https://github.com/elastic/elasticsearch/pull/139415. 

`FieldStorageVerifier` aims to help with that by providing a simple API that can be leveraged to verify that a field is stored exactly where we expect it to. The class itself looks for all instances of a given field in a given document. If said instances don't match expectations, it complains.

Example use case:

```
FieldStorageVerifier.forField("name", doc.rootDoc())
    .expectDocValues()
    .verify();
```

Will verify that `name` is only stored in doc_values. If `name` is stored anywhere else, like ignored_source or a `StoredField`, then the verification check will fail. Furthermore, if `name` is stored twice in doc_values, as with fallback fields, the check will also fail. This helps us confirm:
- `name` is not doubled stored
- `name` is stored in the expected place; in this case doc_values

I've updated `TextFieldMapperTests` for now, with more field mappers to follow in future PRs.

This closes https://github.com/elastic/elasticsearch/issues/139550

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4b315bcab0cfc4682a6a5308cc588403f8432563`
**Instance ID:** `elastic__elasticsearch-139715`
**Language:** `Java`
