# Task

## `illegal data type [time_duration]` in constant folding

### Elasticsearch Version

main

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

serverless

### Problem Description

Noticed the following error in serverless, it should be caught and return a better error:

```
org.elasticsearch.xpack.esql.EsqlIllegalArgumentException: illegal data type [time_duration]
	at org.elasticsearch.xpack.esql.EsqlIllegalArgumentException.illegalDataType(EsqlIllegalArgumentException.java:43)
	at org.elasticsearch.xpack.esql.EsqlIllegalArgumentException.illegalDataType(EsqlIllegalArgumentException.java:39)
	at org.elasticsearch.xpack.esql.planner.PlannerUtils.toElementType(PlannerUtils.java:377)
	at org.elasticsearch.xpack.esql.planner.PlannerUtils.toElementType(PlannerUtils.java:350)
	at org.elasticsearch.xpack.esql.expression.function.scalar.conditional.Case.toEvaluator(Case.java:335)
	at org.elasticsearch.xpack.esql.evaluator.mapper.EvaluatorMapper.fold(EvaluatorMapper.java:161)
	at org.elasticsearch.xpack.esql.expression.function.scalar.EsqlScalarFunction.fold(EsqlScalarFunction.java:39)
	at org.elasticsearch.xpack.esql.expression.predicate.operator.arithmetic.DateTimeArithmeticOperation.toEvaluator(DateTimeArithmeticOperation.java:185)
	at org.elasticsearch.xpack.esql.evaluator.mapper.EvaluatorMapper.fold(EvaluatorMapper.java:161)
	at org.elasticsearch.xpack.esql.expression.predicate.operator.arithmetic.EsqlArithmeticOperation.fold(EsqlArithmeticOperation.java:125)
	at org.elasticsearch.xpack.esql.expression.predicate.operator.arithmetic.DateTimeArithmeticOperation.fold(DateTimeArithmeticOperation.java:165)
	at org.elasticsearch.xpack.esql.core.expression.Literal.of(Literal.java:201)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.ConstantFolding.rule(ConstantFolding.java:22)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$OptimizerExpressionRule.lambda$apply$0(OptimizerRules.java:62)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$7(Node.java:221)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:214)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$6(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformChildren(Node.java:256)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$6(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformChildren(Node.java:256)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:221)
	at org.elasticsearch.xpack.esql.plan.QueryPlan.lambda$transformExpressionsDown$9(QueryPlan.java:124)
	at org.elasticsearch.xpack.esql.plan.QueryPlan.doTransformExpression(QueryPlan.java:146)
	at org.elasticsearch.xpack.esql.plan.QueryPlan.lambda$transformExpressionsDown$10(QueryPlan.java:124)
	at org.elasticsearch.xpack.esql.core.tree.NodeInfo.lambda$transform$0(NodeInfo.java:62)
	at org.elasticsearch.xpack.esql.core.tree.NodeInfo$3.innerTransform(NodeInfo.java:120)
	at org.elasticsearch.xpack.esql.core.tree.NodeInfo.transform(NodeInfo.java:66)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformNodeProps(Node.java:306)
	at org.elasticsearch.xpack.esql.plan.QueryPlan.lambda$transformExpressionsDown$11(QueryPlan.java:124)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$8(Node.java:226)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:214)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$6(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformChildren(Node.java:256)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$6(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformChildren(Node.java:256)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.lambda$transformDown$6(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformChildren(Node.java:256)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:216)
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:226)
	at org.elasticsearch.xpack.esql.plan.QueryPlan.transformExpressionsDown(QueryPlan.java:122)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$OptimizerExpressionRule.apply(OptimizerRules.java:62)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$OptimizerExpressionRule.apply(OptimizerRules.java:44)
	at org.elasticsearch.xpack.esql.rule.ParameterizedRuleExecutor.lambda$transform$0(ParameterizedRuleExecutor.java:29)
	at org.elasticsearch.xpack.esql.rule.RuleExecutor$Transformation.<init>(RuleExecutor.java:111)
	at org.elasticsearch.xpack.esql.rule.RuleExecutor.executeWithInfo(RuleExecutor.java:190)
	at org.elasticsearch.xpack.esql.rule.RuleExecutor.execute(RuleExecutor.java:159)
	at org.elasticsearch.xpack.esql.optimizer.LogicalPlanOptimizer.optimize(LogicalPlanOptimizer.java:120)
	at org.elasticsearch.xpack.esql.session.EsqlSession.optimizedPlan(EsqlSession.java:951)
	at org.elasticsearch.xpack.esql.session.EsqlSession$1.lambda$onResponse$1(EsqlSession.java:243)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.addListener(SubscribableListener.java:222)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.lambda$andThen$1(SubscribableListener.java:534)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListener.run(ActionListener.java:465)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.newForked(SubscribableListener.java:138)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.andThen(SubscribableListener.java:534)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.andThen(SubscribableListener.java:489)
	at org.elasticsearch.xpack.esql.session.EsqlSession$1.onResponse(EsqlSession.java:242)
	at org.elasticsearch.xpack.esql.session.EsqlSession$1.onResponse(EsqlSession.java:222)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.xpack.esql.session.EsqlSession.analyzeWithRetry(EsqlSession.java:891)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$13(EsqlSession.java:574)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:110)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:104)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:67)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$12(EsqlSession.java:571)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.enrich.EnrichPolicyResolver.resolvePolicies(EnrichPolicyResolver.java:120)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$11(EsqlSession.java:568)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:992)
	at org.elasticsearch.xpack.esql.session.EsqlSession.preAnalyzeLookupIndices(EsqlSession.java:588)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$10(EsqlSession.java:566)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:992)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$forAll$23(EsqlSession.java:990)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$preAnalyzeMainIndices$21(EsqlSession.java:858)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.IndexResolver.lambda$resolveAsMergedMappingAndRetrieveMinimumVersion$1(IndexResolver.java:138)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:228)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:222)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$RunBeforeActionListener.onResponse(ActionListenerImplementations.java:350)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.mergeIndexResponses(TransportFieldCapabilitiesAction.java:601)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.lambda$doExecuteForked$9(TransportFieldCapabilitiesAction.java:365)
	at org.elasticsearch.base@9.3.0/org.elasticsearch.core.AbstractRefCounted$1.closeInternal(AbstractRefCounted.java:125)
	at org.elasticsearch.base@9.3.0/org.elasticsearch.core.AbstractRefCounted.decRef(AbstractRefCounted.java:77)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.RefCountingRunnable.close(RefCountingRunnable.java:113)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.RunOnce.run(RunOnce.java:41)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.RequestDispatcher.innerExecute(RequestDispatcher.java:178)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.RequestDispatcher$1.doRun(RequestDispatcher.java:147)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:538)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:534)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractThrottledTaskRunner$1.doRun(AbstractThrottledTaskRunner.java:136)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1076)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
```


### Steps to Reproduce

-

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b3b7f97b07904b3b17d49af1ce9d7a2035fb3672`
**Instance ID:** `elastic__elasticsearch-141157`
**Language:** `Java`
