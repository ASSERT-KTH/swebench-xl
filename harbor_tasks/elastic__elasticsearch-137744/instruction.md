# Task

## Weird date parsing resulting in 500

in one deployment we have observed a search request with a (probably) badly formatted date to result into a 500 status exception.
The execption was `Invalid date 'February 29' as '2026' is not a leap year` and that resulted in a `INTERNAL_SERVER_ERROR`.
This either should be a 4xx or we have a bug in date parsing.
Full stack trace:
```
java.time.DateTimeException: Invalid date 'February 29' as '2026' is not a leap year
	at java.base/java.time.LocalDate.create(LocalDate.java:459)
	at java.base/java.time.LocalDate.of(LocalDate.java:277)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.time.DateFormatters$1.queryFrom(DateFormatters.java:2198)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.time.DateFormatters$1.queryFrom(DateFormatters.java:2190)
	at java.base/java.time.format.Parsed.query(Parsed.java:247)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.time.DateFormatters.from(DateFormatters.java:2135)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.time.DateFormatters.from(DateFormatters.java:2118)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.time.DateFormatter.parseMillis(DateFormatter.java:40)
	at org.elasticsearch.xpack.esql.type.EsqlDataTypeConverter.dateTimeToLong(EsqlDataTypeConverter.java:623)
	at org.elasticsearch.xpack.esql.expression.function.scalar.date.DateParse.process(DateParse.java:222)
	at org.elasticsearch.xpack.esql.expression.function.scalar.date.DateParseConstantEvaluator.eval(DateParseConstantEvaluator.java:100)
	at org.elasticsearch.xpack.esql.expression.function.scalar.date.DateParseConstantEvaluator.eval(DateParseConstantEvaluator.java:56)
	at org.elasticsearch.xpack.esql.evaluator.mapper.EvaluatorMapper.fold(EvaluatorMapper.java:161)
	at org.elasticsearch.xpack.esql.expression.function.scalar.EsqlScalarFunction.fold(EsqlScalarFunction.java:39)
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
	at org.elasticsearch.xpack.esql.core.tree.Node.transformDown(Node.java:226)
	at org.elasticsearch.xpack.esql.plan.QueryPlan.transformExpressionsDown(QueryPlan.java:122)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$OptimizerExpressionRule.apply(OptimizerRules.java:62)
	at org.elasticsearch.xpack.esql.optimizer.rules.logical.OptimizerRules$OptimizerExpressionRule.apply(OptimizerRules.java:44)
	at org.elasticsearch.xpack.esql.rule.ParameterizedRuleExecutor.lambda$transform$0(ParameterizedRuleExecutor.java:29)
	at org.elasticsearch.xpack.esql.rule.RuleExecutor$Transformation.<init>(RuleExecutor.java:111)
	at org.elasticsearch.xpack.esql.rule.RuleExecutor.executeWithInfo(RuleExecutor.java:190)
	at org.elasticsearch.xpack.esql.rule.RuleExecutor.execute(RuleExecutor.java:159)
	at org.elasticsearch.xpack.esql.optimizer.LogicalPlanOptimizer.optimize(LogicalPlanOptimizer.java:120)
	at org.elasticsearch.xpack.esql.session.EsqlSession.optimizedPlan(EsqlSession.java:946)
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
	at org.elasticsearch.xpack.esql.session.EsqlSession.analyzeWithRetry(EsqlSession.java:886)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$13(EsqlSession.java:569)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:110)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:104)
	at org.elasticsearch.xpack.esql.inference.InferenceResolver.resolveInferenceIds(InferenceResolver.java:67)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$12(EsqlSession.java:566)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.xpack.esql.enrich.EnrichPolicyResolver.resolvePolicies(EnrichPolicyResolver.java:120)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$11(EsqlSession.java:563)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:406)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:326)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:355)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:262)
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:987)
	at org.elasticsearch.xpack.esql.session.EsqlSession.preAnalyzeLookupIndices(EsqlSession.java:583)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$resolveIndicesAndAnalyze$10(EsqlSession.java:561)
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
	at org.elasticsearch.xpack.esql.session.EsqlSession.forAll(EsqlSession.java:987)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$forAll$23(EsqlSession.java:985)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.EsqlSession.lambda$preAnalyzeMainIndices$21(EsqlSession.java:853)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xpack.esql.session.IndexResolver.lambda$resolveAsMergedMappingAndRetrieveMinimumVersion$1(IndexResolver.java:138)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:228)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:222)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$RunBeforeActionListener.onResponse(ActionListenerImplementations.java:350)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.mergeIndexResponses(TransportFieldCapabilitiesAction.java:569)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction.lambda$doExecuteForked$8(TransportFieldCapabilitiesAction.java:338)
	at org.elasticsearch.base@9.3.0/org.elasticsearch.core.AbstractRefCounted$1.closeInternal(AbstractRefCounted.java:125)
	at org.elasticsearch.base@9.3.0/org.elasticsearch.core.AbstractRefCounted.decRef(AbstractRefCounted.java:77)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.support.RefCountingRunnable.close(RefCountingRunnable.java:113)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.RunOnce.run(RunOnce.java:41)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.RequestDispatcher.innerExecute(RequestDispatcher.java:178)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.RequestDispatcher$1.doRun(RequestDispatcher.java:147)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:505)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.action.fieldcaps.TransportFieldCapabilitiesAction$2.onResponse(TransportFieldCapabilitiesAction.java:501)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractThrottledTaskRunner$1.doRun(AbstractThrottledTaskRunner.java:136)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1076)
	at org.elasticsearch.server@9.3.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4eade64dc6f1beb76d34d0471f80c1c62470ae3c`
**Instance ID:** `elastic__elasticsearch-137744`
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
