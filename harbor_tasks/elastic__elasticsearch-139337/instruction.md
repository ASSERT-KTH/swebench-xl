# Task

## Consistently prevent using exclusion prefix on its own

The dash character is used as a prefix to signify index exclusion. It should not be used on its own. For example, an expression like `*,-` should be invalid. However, today this is handled differently depending on whether security is enabled or disabled. When security is enabled, the standalone exclusion char is ignored and the expression is handled as just `*`. But when security is disabled, the expression encounters an IndexNotFoundException.

This PR fixes the inconsistency by always throwing InvalidIndexNameException. In addition, this PR also fixes #45504 by ensuring InvalidIndexNameException is thrown for empty index name instead of IndexOutOfBoundsException.

Resolves: #45504

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1b26cc5a1b33c876a2567644d09c67e528c2082d`
**Instance ID:** `elastic__elasticsearch-139337`
**Language:** `Java`
