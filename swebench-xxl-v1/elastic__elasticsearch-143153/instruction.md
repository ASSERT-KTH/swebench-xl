# Task

## ESQL: ABS of Integer.MIN_VALUE throws 500 error

### Description

Both scenarios below don't have a very user friendly output. First, I think it should be 400 error or maybe **a Warning should be enough and the value set as `null`**.

```
from base_conversion | eval x = log(abs(expect_integer) + 1)
```

throws 

```
status: 500 java.lang.ArithmeticException: Overflow to represent absolute value of Integer.MIN_VALUE
        at java.base/java.lang.Math.absExact(Math.java:1907)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.Abs.process(Abs.java:67)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.AbsIntEvaluator.eval(AbsIntEvaluator.java:76)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.AbsIntEvaluator.eval(AbsIntEvaluator.java:48)
        at org.elasticsearch.xpack.esql.expression.predicate.operator.arithmetic.AddIntsEvaluator.eval(AddIntsEvaluator.java:49)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.CastIntToDoubleEvaluator.eval(CastIntToDoubleEvaluator.java:47)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.LogConstantEvaluator.eval(LogConstantEvaluator.java:46)
        at org.elasticsearch.compute.operator.EvalOperator.process(EvalOperator.java:50)
```

---

Second scenario:

```
row y = -2147483648 | eval x = abs(y)
```

throws the same kind of error, but here the user is in total control of the values passed to `abs`:

```
status: 500 java.lang.ArithmeticException: Overflow to represent absolute value of Integer.MIN_VALUE
        at java.base/java.lang.Math.absExact(Math.java:1907)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.Abs.process(Abs.java:67)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.AbsIntEvaluator.eval(AbsIntEvaluator.java:86)
        at org.elasticsearch.xpack.esql.expression.function.scalar.math.AbsIntEvaluator.eval(AbsIntEvaluator.java:50)
        at org.elasticsearch.xpack.esql.evaluator.mapper.EvaluatorMapper.fold(EvaluatorMapper.java:161)
        at org.elasticsearch.xpack.esql.expression.function.scalar.EsqlScalarFunction.fold(EsqlScalarFunction.java:322)
        at org.elasticsearch.xpack.esql.core.expression.Literal.of(Literal.java:207)
        at org.elasticsearch.xpack.esql.optimizer.rules.RuleUtils.lambda$foldableReferences$1(RuleUtils.java:100)
        at org.elasticsearch.xpack.esql.core.tree.Node.lambda$forEachUp$1(Node.java:131)
        at org.elasticsearch.xpack.esql.core.tree.Node.forEachUp(Node.java:124)
        at org.elasticsearch.xpack.esql.core.tree.Node.forEachUp(Node.java:129)
        at org.elasticsearch.xpack.esql.plan.QueryPlan.lambda$forEachExpressionUp$21(QueryPlan.java:207)
        at org.elasticsearch.xpack.esql.plan.QueryPlan.doForEachExpression(QueryPlan.java:213)
        at org.elasticsearch.xpack.esql.plan.QueryPlan.doForEachExpression(QueryPlan.java:216)
        at org.elasticsearch.xpack.esql.plan.QueryPlan.lambda$forEachExpressionUp$22(QueryPlan.java:207)
        at org.elasticsearch.xpack.esql.core.tree.Node.forEachProperty(Node.java:153)
        at org.elasticsearch.xpack.esql.core.tree.Node.lambda$forEachPropertyUp$3(Node.java:145)
        at org.elasticsearch.xpack.esql.core.tree.Node.forEachUp(Node.java:124)
        at org.elasticsearch.xpack.esql.core.tree.Node.forEachUp(Node.java:122)
        at org.elasticsearch.xpack.esql.core.tree.Node.forEachPropertyUp(Node.java:145)
        at org.elasticsearch.xpack.esql.plan.QueryPlan.forEachExpressionUp(QueryPlan.java:207)
        at org.elasticsearch.xpack.esql.optimizer.rules.RuleUtils.foldableReferences(RuleUtils.java:91)
        at org.elasticsearch.xpack.esql.optimizer.rules.logical.PropagateEvalFoldables.apply(PropagateEvalFoldables.java:32)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `4111eaa66878b0a84b1194c5bc6b120ab3d7d03e`
**Instance ID:** `elastic__elasticsearch-143153`
**Language:** `Java`
