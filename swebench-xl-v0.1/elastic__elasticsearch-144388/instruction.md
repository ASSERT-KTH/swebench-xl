# Task

## ESQL: change point value must be numeric for a NULL data type

### Description

```
SET unmapped_fields="nullify";
from employees | change_point foo
```

Or, simpler:

```
from *
| eval foo = null, @timestamp = @timestamp::datetime
| change_point foo
```

returns 

```
change point value [foo] must be numeric",
```

but if I do

```
from *
| eval foo = null::int, @timestamp = @timestamp::datetime
| change_point foo
```
seems to be fine.

The error message is confusing and/or wrong:
- it should either accept a `NULL` data type and return `null` or something similar + warning
- or it should say what kind of numerics it's accepting and what it actually got
For example, `grok` / `dissect` say something like this: `Grok only supports KEYWORD or TEXT values, found expression [foo] type [NULL]"`

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `453425a8c66272cbbc65a67d638128b3621aebfd`
**Instance ID:** `elastic__elasticsearch-144388`
**Language:** `Java`
