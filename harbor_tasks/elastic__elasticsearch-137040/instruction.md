# Task

## ESQL: Introduce TimestampAware interface/contract

### Description

Timeseries related functions require access to the timestamp field (typically `@timestamp`). Currently, the functions declare a `UnresolvedAttribute(@timestamp)` inside their constructor:
```java
public MyTimeFunction(Source source, Expression field) {
     // delegate to the actual constructor using an UnresolvedAttribute
     this(source, field, new UnresolvedAttribute(source, field, MetadataAttribute.TIMESTAMP_FIELD);
}

public MyTimeFunction(Source source, Expression field, Expression timestamp) {
   ...
}
```

so that the `Analyzer` injects it however this has several disadvantages:
- it hardcodes the field name which makes the resolution fail in case of a rename for example `ts indices-* | rename x = @timestamp | ...`
- if the public constructor is called after the analysis phase, the plan becomes invalid

An improved approach is to be explicit about the dependency and instruct the planner to deal with across the entire query in a holistic fashion.
One approach is to introduce a dedicated `TimestampAwareBuilder` (similar to `ConfigurationAware` ) to handle the constructor reference or simply rely on the `TimestampAware`  interface to mark the consumer and (potentially a (a `TimestampSource` for the provider  to clearly indicate the `@timestamp` either through a dedicated method or through its type/"flag" similar to MetadataAttribute but not by name since it's an actual user facing field).

```java
// consumer interface
public interface TimestampAware {
      Expression timestamp();
}
```
In the function registry define

```java
protected interface TimestampAwareBuilder<T> {
    T build(Source source, Expression field, Expression timestamp);
}

// which would be fed into the function definition:
def(MyTimeFunction.class, time(MyTimeFunction::new, "myTimeFunction"))
```
An alternative to `TimestampAwareBuilder` is to check if the target function implements `TimestampAware` interface and if so, look at the constructor field of time Expression based on the  `@Param` annotation information. The former should be more reliable since it applies to all constructors whereas `@Param` is used for documentation purposes.

The advantage of this approach is the resolution and supplying of the timestamp is externalized from the function into the registry which can wire the field directly similar to the approach taken with `Configuration`.
It's up to the instantiators of the function to supply the timestamp instead of the function itself, the current situation.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `772e6a18997f3f5594f783072f7e35dac626d62f`
**Instance ID:** `elastic__elasticsearch-137040`
**Language:** `Java`
