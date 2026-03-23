# Task

## ES|QL: complaining about mapping conflicts on passthrough fields incorrectly recognizing as [object] type

### Elasticsearch Version

Serverless

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

--

## Problem Description

### Context

For OTel data the `attributes.*` [fields are defined as passthrough type](https://github.com/elastic/elasticsearch/blob/ad6d82f1a638948eeadab0702a199e5cc1c9c681/x-pack/plugin/otel-data/src/main/resources/component-templates/otel%40mappings.yaml#L23).

That implies that all fields under `attributes.*` should have `subobjects: false`.
So, there shouldn't be any issues when both attributes `attributes.foo` and `attributes.foo.bar` exist and we want to query them.

### Problem

When there is an attribute with a name that equals the namespace of another attribute it leads to a mapping conflict issue when querying it in ESQL:

<img width="701" height="480" alt="Image" src="https://github.com/user-attachments/assets/7cdb1f96-991c-4669-ae46-2a9640a2449c" />

For example, if we have two different docs with different attributes in different datastreams:

- `attributes.foo`          --> e.g. in data stream `logs-test_1.otel-default`
- `attributes.foo.bar`   --> e.g. in data stream `logs-test_2.otel-default`

and we execute an ES|QL query like:

```
FROM logs-test* | WHERE attributes.foo IS NOT NULL
```

it throws an error like the above. i.e. it thinks that `attributes.foo` is an `[object]` though it actually can never be an object because of the passthrough type of `attributes`.

Interestingly this DOES NOT HAPPEN if the query uses the implicit alias of that passthrough field. i.e. this query works:

```
FROM logs-test* | WHERE foo IS NOT NULL
```

Also, it DOES NOT HAPPEN if those two docs are in the same datastream.

## Steps to Reproduce

### Step 1: Index the documents

#### Two docs into different indices / datastreams

```
POST /logs-test_1.otel-default/_doc?refresh
{
    "attributes": {
        "foo": "abc"
    }
}
```

```
POST /logs-test_2.otel-default/_doc?refresh
{
    "attributes": {
        "foo.bar": "xyz"
    }
}
```

#### Two docs into the same index / datastream

```
POST /logs-test_3.otel-default/_doc?refresh
{
    "attributes": {
        "foo": "abc"
    }
}
```

```
POST /logs-test_3.otel-default/_doc?refresh
{
    "attributes": {
        "foo.bar": "xyz"
    }
}
```

### Step 2: Execute ES|QL queries

#### This query fails

```
POST /_query?error_trace
{
  "query": "FROM logs-test* | WHERE attributes.foo IS NOT NULL"
}
```

<details>
<summary>
Error stack trace on this query
</summary>

```
{
  "error": {
    "root_cause": [
      {
        "type": "verification_exception",
        "reason": """Found 1 problem
line 1:25: Cannot use field [attributes.foo] due to ambiguities being mapped as [2] incompatible types: [keyword] in [.ds-logs-test_1.otel-default-2026.03.13-000001, .ds-logs-test_3.otel-default-2026.03.13-000001], [object] in [.ds-logs-test_2.otel-default-2026.03.13-000001]""",
        "stack_trace": """org.elasticsearch.xpack.esql.VerificationException: Found 1 problem
line 1:25: Cannot use field [attributes.foo] due to ambiguities being mapped as [2] incompatible types: [keyword] in [.ds-logs-test_1.otel-default-2026.03.13-000001, .ds-logs-test_3.otel-default-2026.03.13-000001], [object] in [.ds-logs-test_2.otel-default-2026.03.13-000001]
	at org.elasticsearch.xpack.esql.analysis.Analyzer.verify(Analyzer.java:280)
	at org.elasticsearch.xpack.esql.analysis.Analyzer.analyze(Analyzer.java:274)
	at org.elasticsearch.xpack.esql.session.EsqlSession.analyzedPlan(EsqlSession.java:1291)
	at org.elasticsearch.xpack.esql.session.EsqlSession.analyzeWithRetry(EsqlSession.java:1240)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$20(EsqlSession.java:800)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:109)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:103)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:66)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$19(EsqlSession.java:796)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.enrich.EnrichPolicyResolver.resolvePolicies(EnrichPolicyResolver.java:133)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$18(EsqlSession.java:788)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.xpack.esql.session.EsqlSession.preAnalyzeExternalSources(EsqlSession.java:858)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$17(EsqlSession.java:785)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:1360)
	at org.elasticsearch.xpack.esql.session.EsqlSession.preAnalyzeLookupIndices(EsqlSession.java:814)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$16(EsqlSession.java:784)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:1360)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$forAll$34(EsqlSession.java:1358)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$preAnalyzeMainIndices$30(EsqlSession.java:1162)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.IndexResolver.lambda$doResolveIndices$4(IndexResolver.java:243)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:223)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:217)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$RunBeforeActionListener.onResponse(ActionListenerImplementations.java:350)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.mergeIndexResponses(TransportFieldCapabilitiesAction.java:612)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.lambda$doExecuteForked$7(TransportFieldCapabilitiesAction.java:376)
	at org.elasticsearch.base@9.4.0/org.elasticsearch.core.AbstractRefCounted$1.closeInternal(AbstractRefCounted.java:125)
	at org.elasticsearch.base@9.4.0/org.elasticsearch.core.AbstractRefCounted.decRef(AbstractRefCounted.java:77)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.RefCountingRunnable.close(RefCountingRunnable.java:122)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.RunOnce.run(RunOnce.java:44)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.RequestDispatcher.innerExecute(RequestDispatcher.java:177)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.RequestDispatcher$1.doRun(RequestDispatcher.java:146)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:549)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:545)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractThrottledTaskRunner$1.doRun(AbstractThrottledTaskRunner.java:140)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
"""
      }
    ],
    "type": "verification_exception",
    "reason": """Found 1 problem
line 1:25: Cannot use field [attributes.foo] due to ambiguities being mapped as [2] incompatible types: [keyword] in [.ds-logs-test_1.otel-default-2026.03.13-000001, .ds-logs-test_3.otel-default-2026.03.13-000001], [object] in [.ds-logs-test_2.otel-default-2026.03.13-000001]""",
    "stack_trace": """org.elasticsearch.xpack.esql.VerificationException: Found 1 problem
line 1:25: Cannot use field [attributes.foo] due to ambiguities being mapped as [2] incompatible types: [keyword] in [.ds-logs-test_1.otel-default-2026.03.13-000001, .ds-logs-test_3.otel-default-2026.03.13-000001], [object] in [.ds-logs-test_2.otel-default-2026.03.13-000001]
	at org.elasticsearch.xpack.esql.analysis.Analyzer.verify(Analyzer.java:280)
	at org.elasticsearch.xpack.esql.analysis.Analyzer.analyze(Analyzer.java:274)
	at org.elasticsearch.xpack.esql.session.EsqlSession.analyzedPlan(EsqlSession.java:1291)
	at org.elasticsearch.xpack.esql.session.EsqlSession.analyzeWithRetry(EsqlSession.java:1240)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$20(EsqlSession.java:800)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:109)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:103)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:66)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$19(EsqlSession.java:796)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.enrich.EnrichPolicyResolver.resolvePolicies(EnrichPolicyResolver.java:133)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$18(EsqlSession.java:788)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.xpack.esql.session.EsqlSession.preAnalyzeExternalSources(EsqlSession.java:858)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$17(EsqlSession.java:785)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:1360)
	at org.elasticsearch.xpack.esql.session.EsqlSession.preAnalyzeLookupIndices(EsqlSession.java:814)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$16(EsqlSession.java:784)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:279)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:1360)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$forAll$34(EsqlSession.java:1358)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$preAnalyzeMainIndices$30(EsqlSession.java:1162)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.IndexResolver.lambda$doResolveIndices$4(IndexResolver.java:243)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:223)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:217)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$RunBeforeActionListener.onResponse(ActionListenerImplementations.java:350)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.mergeIndexResponses(TransportFieldCapabilitiesAction.java:612)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.lambda$doExecuteForked$7(TransportFieldCapabilitiesAction.java:376)
	at org.elasticsearch.base@9.4.0/org.elasticsearch.core.AbstractRefCounted$1.closeInternal(AbstractRefCounted.java:125)
	at org.elasticsearch.base@9.4.0/org.elasticsearch.core.AbstractRefCounted.decRef(AbstractRefCounted.java:77)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.RefCountingRunnable.close(RefCountingRunnable.java:122)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.RunOnce.run(RunOnce.java:44)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.RequestDispatcher.innerExecute(RequestDispatcher.java:177)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.RequestDispatcher$1.doRun(RequestDispatcher.java:146)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:549)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:545)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractThrottledTaskRunner$1.doRun(AbstractThrottledTaskRunner.java:140)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
"""
  },
  "status": 400
}
```

</details>

#### These queries work as expected


Querying the first attribute through the alias:

```
POST /_query?error_trace
{
  "query": "FROM logs-test* | WHERE attributes.foo IS NOT NULL"
}
```

Querying the second attribute:

```
POST /_query?error_trace
{
  "query": "FROM logs-test* | WHERE attributes.foo.bar IS NOT NULL"
}
```

Querying in the data stream that contains both docs:

```
POST /_query?error_trace
{
  "query": "FROM logs-test_3* | WHERE attributes.fooIS NOT NULL"
}
```

Also, a corresponding DSL query works as expected:

```
POST /logs-test*/_search
{
  "query": {
    "exists": {
        "field": "attributes.foo"
    }
  }
}
```

## Logs (if relevant)

--

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cc8b62708f9acf77fda4094a157aa8abcd78c83c`
**Instance ID:** `elastic__elasticsearch-144183`
**Language:** `Java`
