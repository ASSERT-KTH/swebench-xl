# Task

## SQL: QlIllegalArgumentException when trying to fold > with field: "Comparisons against fields are not (currently) supported"

Suppressed rest error on Serverless, internal issue is ES-13375.

This looks like it shouldn't throw a server error. May or may not be the same as https://github.com/issues/created?issue=elastic%7Celasticsearch%7C137365.

`Line 1:25: Comparisons against fields are not (currently) supported; offender [field] in [>]`

```
"org.elasticsearch.xpack.ql.QlIllegalArgumentException: Line 1:25: Comparisons against fields are not (currently) supported; offender [field] in [>]
	at org.elasticsearch.xpack.ql.util.Check.isTrue(Check.java:18)
	at org.elasticsearch.xpack.ql.planner.ExpressionTranslators$BinaryComparisons.checkBinaryComparison(ExpressionTranslators.java:270)
	at org.elasticsearch.xpack.sql.planner.QueryTranslator$BinaryComparisons.asQuery(QueryTranslator.java:380)
	at org.elasticsearch.xpack.sql.planner.QueryTranslator$BinaryComparisons.asQuery(QueryTranslator.java:376)
	at org.elasticsearch.xpack.sql.planner.QueryTranslator$SqlExpressionTranslator.translate(QueryTranslator.java:495)
	at org.elasticsearch.xpack.sql.planner.QueryTranslator.toQuery(QueryTranslator.java:147)
	at org.elasticsearch.xpack.sql.planner.QueryFolder$FoldFilter.rule(QueryFolder.java:209)
	at org.elasticsearch.xpack.sql.planner.QueryFolder$FoldFilter.rule(QueryFolder.java:203)
	at org.elasticsearch.xpack.ql.tree.Node.lambda$transformUp$11(Node.java:198)
	at org.elasticsearch.xpack.ql.tree.Node.transformUp(Node.java:192)
	at org.elasticsearch.xpack.ql.tree.Node.lambda$transformUp$10(Node.java:190)
	at org.elasticsearch.xpack.ql.tree.Node.transformChildren(Node.java:211)
	at org.elasticsearch.xpack.ql.tree.Node.transformUp(Node.java:190)
	at org.elasticsearch.xpack.ql.tree.Node.lambda$transformUp$10(Node.java:190)
	at org.elasticsearch.xpack.ql.tree.Node.transformChildren(Node.java:211)
	at org.elasticsearch.xpack.ql.tree.Node.transformUp(Node.java:190)
	at org.elasticsearch.xpack.ql.tree.Node.transformUp(Node.java:198)
	at org.elasticsearch.xpack.sql.planner.QueryFolder$FoldingRule.apply(QueryFolder.java:930)
	at org.elasticsearch.xpack.sql.planner.QueryFolder$FoldingRule.apply(QueryFolder.java:926)
	at org.elasticsearch.xpack.ql.rule.RuleExecutor$Transformation.<init>(RuleExecutor.java:88)
	at org.elasticsearch.xpack.ql.rule.RuleExecutor.executeWithInfo(RuleExecutor.java:167)
	at org.elasticsearch.xpack.ql.rule.RuleExecutor.execute(RuleExecutor.java:136)
	at org.elasticsearch.xpack.sql.planner.QueryFolder.fold(QueryFolder.java:115)
	at org.elasticsearch.xpack.sql.planner.Planner.foldPlan(Planner.java:39)
	at org.elasticsearch.xpack.sql.planner.Planner.plan(Planner.java:29)
	at org.elasticsearch.xpack.sql.session.SqlSession.lambda$physicalPlan$4(SqlSession.java:186)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.sql.session.SqlSession.lambda$optimizedPlan$3(SqlSession.java:182)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.sql.session.SqlSession.lambda$preAnalyze$2(SqlSession.java:169)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.ql.index.IndexResolver.lambda$resolveAsMergedMapping$7(IndexResolver.java:401)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:228)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:222)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$RunBeforeActionListener.onResponse(ActionListenerImplementations.java:350)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListener.completeWith(ActionListener.java:373)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.mergeIndexResponses(TransportFieldCapabilitiesAction.java:368)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.lambda$doExecuteForked$6(TransportFieldCapabilitiesAction.java:238)
	at org.elasticsearch.base@9.3.0/org.elasticsearch.core.AbstractRefCounted$1.closeInternal(AbstractRefCounted.java:125)
	at org.elasticsearch.base@9.3.0/org.elasticsearch.core.AbstractRefCounted.decRef(AbstractRefCounted.java:77)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.RefCountingRunnable.close(RefCountingRunnable.java:113)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.RunOnce.run(RunOnce.java:41)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.RequestDispatcher.innerExecute(RequestDispatcher.java:177)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.RequestDispatcher$1.doRun(RequestDispatcher.java:146)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$1.onResponse(TransportFieldCapabilitiesAction.java:328)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$1.onResponse(TransportFieldCapabilitiesAction.java:324)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractThrottledTaskRunner$1.doRun(AbstractThrottledTaskRunner.java:136)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1076)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
"
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f5cb6ea7d46cc4f62a4c1eb10cd528af1b5c0927`
**Instance ID:** `elastic__elasticsearch-137560`
**Language:** `Java`
