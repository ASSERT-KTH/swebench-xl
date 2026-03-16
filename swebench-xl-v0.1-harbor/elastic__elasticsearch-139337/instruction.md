# Task

## Empty index name in `index` path param fails request with access denied

When doing index operations like `_search`, `_field_caps` we provide index patterns as a path param. When security is enabled and the index pattern path param contains an empty string then the request fails with HTTP status 403 and a `security_exception` with message `action [indices:data/read/search] is unauthorized for user [elastic]`. The user has `superuser` role but the root cause is a string out of bounds exception with message `String index out of range: 0`.

IMO we should not be throwing index out of bounds exception during index alias resolution and the response should be a validation error instead of access denied similar to what we respond when security is disabled.

Example problem invocation with a empty string as index name:
`POST /test*,,missing*/_search?q=*`
`GET /test*,,missing*/_field_caps`

When security is disabled, the response is with HTTP status 404 and an `index_not_found_exception` with message `no such index []`.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1b26cc5a1b33c876a2567644d09c67e528c2082d`
**Instance ID:** `elastic__elasticsearch-139337`
**Language:** `Java`
