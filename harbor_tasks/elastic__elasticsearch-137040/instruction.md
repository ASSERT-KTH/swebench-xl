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

You can execute bash commands and edit files to implement the necessary changes.

## Recommended Workflow

This workflows should be done step-by-step so that you can iterate on your 
changes and any possible problems.

1. Analyze the codebase by finding and reading relevant files
2. Create a script to reproduce the issue
3. Edit the source code to resolve the issue
4. Verify your fix works by running your script again
5. Test edge cases to ensure your fix is robust
6. Submit your changes and finish your work by issuing the following command: 
`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.
   Do not combine it with any other command. <important>After this command, you 
cannot continue working on this task.</important>

## Important Rules

1. Every response must contain exactly one action
2. The action must be enclosed in triple backticks
3. Directory or environment variable changes are not persistent. Every action is
executed in a new subshell.
   However, you can prefix any action with `MY_ENV_VAR=MY_VALUE cd 
/path/to/working/dir && ...` or write/load environment variables from files

<system_information>
Linux 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun  5 
18:30:46 UTC 2025 x86_64
</system_information>

## Formatting your response

Here is an example of a correct response:

<example_response>
THOUGHT: I need to understand the structure of the repository first. Let me 
check what files are in the current directory to get a better understanding of 
the codebase.

```bash
ls -la
```
</example_response>

## Useful command examples

### Create a new file:

```bash
cat <<'EOF' > newfile.py
import numpy as np
hello = "world"
print(hello)
EOF
```

### Edit files with sed:```bash
# Replace all occurrences
sed -i 's/old_string/new_string/g' filename.py

# Replace only first occurrence
sed -i 's/old_string/new_string/' filename.py

# Replace first occurrence on line 1
sed -i '1s/old_string/new_string/' filename.py

# Replace all occurrences in lines 1-10
sed -i '1,10s/old_string/new_string/g' filename.py
```

### View file content:

```bash
# View specific lines with numbers
nl -ba filename.py | sed -n '10,20p'
```

### Any other command you want to run

```bash
anything
```
