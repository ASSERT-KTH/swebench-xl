# Task

## `GET /_migration/deprecations` doesn't report node deprecations if low watermark exceeded | `GET /_migration/deprecations` doesn't report node-level failures properly

### Issue 1: `GET /_migration/deprecations` doesn't report node deprecations if low watermark exceeded

This seemingly-innocuous code ...

https://github.com/elastic/elasticsearch/blob/aced42f487634fec9b270a234cbad510f3a4cbc6/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/TransportNodeDeprecationCheckAction.java#L145-L147

... doesn't work because `issues` came from `Stream#toList` and is therefore immutable. Instead it throws a UOE:

```
java.lang.UnsupportedOperationException: null
        at java.util.ImmutableCollections.uoe(ImmutableCollections.java:159) ~[?:?]
        at java.util.ImmutableCollections$AbstractImmutableCollection.add(ImmutableCollections.java:164) ~[?:?]
        at org.elasticsearch.xpack.deprecation.TransportNodeDeprecationCheckAction.nodeOperation(TransportNodeDeprecationCheckAction.java:146) ~[?:?]
        at org.elasticsearch.xpack.deprecation.TransportNodeDeprecationCheckAction.nodeOperation(TransportNodeDeprecationCheckAction.java:110) ~[?:?]
        at org.elasticsearch.xpack.deprecation.TransportNodeDeprecationCheckAction.nodeOperation(TransportNodeDeprecationCheckAction.java:43) ~[?:?]
        at org.elasticsearch.action.support.nodes.TransportNodesAction.nodeOperationAsync(TransportNodesAction.java:261) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.action.support.nodes.TransportNodesAction$NodeTransportHandler.lambda$messageReceived$0(TransportNodesAction.java:277) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.action.ActionListener.run(ActionListener.java:454) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.action.support.nodes.TransportNodesAction$NodeTransportHandler.messageReceived(TransportNodesAction.java:275) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.transport.RequestHandlerRegistry.processMessageReceived(RequestHandlerRegistry.java:86) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.transport.TransportService$6.doRun(TransportService.java:1078) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1044) ~[elasticsearch-8.19.5.jar:?]
        at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27) ~[elasticsearch-8.19.5.jar:?]
        at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090) ~[?:?]
        at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614) ~[?:?]
        at java.lang.Thread.run(Thread.java:1474) ~[?:?]
```

Such node-level failures do not propagate back to the API response, they're just logged and then [silently dropped](https://github.com/elastic/elasticsearch/issues/137010) here:

https://github.com/elastic/elasticsearch/blob/aced42f487634fec9b270a234cbad510f3a4cbc6/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecker.java#L53-L56

This sort of node-level failure is more likely than you might think because we report low watermark violations [far too liberally](https://github.com/elastic/elasticsearch/issues/137005).

---

### Issue 2: `GET /_migration/deprecations` doesn't report node-level failures properly

As mentioned in https://github.com/elastic/elasticsearch/issues/137004, we log (but otherwise ignore) node-level failures to check for deprecations:

https://github.com/elastic/elasticsearch/blob/aced42f487634fec9b270a234cbad510f3a4cbc6/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecker.java#L53-L56

This is very problematic since it means users may incorrectly believe their cluster to be ready to upgrade, only to discover during the upgrade that it is now broken. If the response to the API is incomplete then users need to know about it.

It's probably a bad idea to report the details at `DEBUG`, and even worse we actually only report the result of `failure.toString()` which is something useless like `Failed node [RiRNhBZARO-v7peMV0rQDg] org.elasticsearch.action.FailedNodeException: Failed node [RiRNhBZARO-v7peMV0rQDg]` rather than reporting the whole stack trace:

```diff
diff --git a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecker.java b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecker.java
index a2e9ed12a229..53bd7e492d17 100644
--- a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecker.java
+++ b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/NodeDeprecationChecker.java
@@ -52,7 +52,9 @@ public class NodeDeprecationChecker {
                         .collect(Collectors.toList());
                     logger.warn("nodes failed to run deprecation checks: {}", failedNodeIds);
                     for (FailedNodeException failure : response.failures()) {
-                        logger.debug("node {} failed to run deprecation checks: {}", failure.nodeId(), failure);
+                        logger.atDebug()
+                            .withThrowable(failure)
+                            .log("node {} failed to run deprecation checks: {}", failure.nodeId(), failure.getMessage());
                     }
                 }
                 l.onResponse(reduceToDeprecationIssues(response));
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `0051df80d66012a9d45b93b06a56ea153b1cbe66`
**Instance ID:** `elastic__elasticsearch-137964`
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
