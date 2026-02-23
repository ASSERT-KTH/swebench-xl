# Task

## Do not use Min or Max as Top's surrogate when there is an outputField

## Why

Now that we have added `outputField` to `Top`, we should not be using `Max` or `Min` when there is an `outputField` because those expressions do not take an `outputField`.

This was causing some test flakiness. The tests were not failing consistently because this only happens for a limit of 1 (and limit is also randomized in the tests).

Closes #134083

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1de87568927ab954a966a2c6a94abb9a68d0485e`
**Instance ID:** `elastic__elasticsearch-138380`
**Language:** `Java`
