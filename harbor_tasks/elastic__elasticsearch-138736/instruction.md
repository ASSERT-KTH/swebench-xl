# Task

## PromQL: parsing_exception when empty char at the end of the query

When running the following query 

```json
POST _query
{
  "query": "TS metrics-hostmetricsreceiver.otel-default | WHERE @timestamp >= \"2025-11-26T08:41:01.000Z\" AND @timestamp <= \"2025-11-26T13:11:00.000Z\" | PROMQL step 1h (avg by (host.name) (rate(system.cpu.time[1h]))) "
}

```

We get an parsing_exception

```json
{
  "error": {
    "root_cause": [
      {
        "type": "parsing_exception",
        "reason": "line 1:204: extraneous input ' ' expecting <EOF>",
        "stack_trace": """org.elasticsearch.xpack.esql.parser.ParsingException: line 1:204: extraneous input ' ' expecting <EOF>
	at org.elasticsearch.xpack.esql.parser.EsqlParser$1.syntaxError(EsqlParser.java:216)
	at org.antlr.v4.runtime.ProxyErrorListener.syntaxError(ProxyErrorListener.java:41)
	at org.antlr.v4.runtime.Parser.notifyErrorListeners(Parser.java:544)
	at org.antlr.v4.runtime.DefaultErrorStrategy.reportUnwantedToken(DefaultErrorStrategy.java:377)
	at org.antlr.v4.runtime.DefaultErrorStrategy.singleTokenDeletion(DefaultErrorStrategy.java:548)
	at org.antlr.v4.runtime.DefaultErrorStrategy.recoverInline(DefaultErrorStrategy.java:467)
	at org.antlr.v4.runtime.Parser.match(Parser.java:208)
	at org.elasticsearch.xpack.esql.parser.EsqlBaseParser.singleStatement(EsqlBaseParser.java:340)
	at org.elasticsearch.xpack.esql.parser.EsqlBaseParser.statements(EsqlBaseParser.java:289)
	at org.elasticsearch.xpack.esql.parser.EsqlParser.invokeParser(EsqlParser.java:166)
	at org.elasticsearch.xpack.esql.parser.EsqlParser.createQuery(EsqlParser.java:132)
	at org.elasticsearch.xpack.esql.session.EsqlSession.parse(EsqlSession.java:456)
	at org.elasticsearch.xpack.esql.session.EsqlSession.execute(EsqlSession.java:189)
	at org.elasticsearch.xpack.esql.execution.PlanExecutor.lambda$esql$2(PlanExecutor.java:102)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionListener.run(ActionListener.java:465)
	at org.elasticsearch.xpack.esql.execution.PlanExecutor.esql(PlanExecutor.java:102)
	at org.elasticsearch.xpack.esql.plugin.TransportEsqlQueryAction.innerExecute(TransportEsqlQueryAction.java:257)
	at org.elasticsearch.xpack.esql.plugin.TransportEsqlQueryAction.doExecuteForked(TransportEsqlQueryAction.java:227)
	at org.elasticsearch.xpack.esql.plugin.TransportEsqlQueryAction.lambda$doExecute$5(TransportEsqlQueryAction.java:217)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionRunnable$4.doRun(ActionRunnable.java:101)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1088)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
"""
      }
    ],
    "type": "parsing_exception",
    "reason": "line 1:204: extraneous input ' ' expecting <EOF>",
    "stack_trace": """org.elasticsearch.xpack.esql.parser.ParsingException: line 1:204: extraneous input ' ' expecting <EOF>
	at org.elasticsearch.xpack.esql.parser.EsqlParser$1.syntaxError(EsqlParser.java:216)
	at org.antlr.v4.runtime.ProxyErrorListener.syntaxError(ProxyErrorListener.java:41)
	at org.antlr.v4.runtime.Parser.notifyErrorListeners(Parser.java:544)
	at org.antlr.v4.runtime.DefaultErrorStrategy.reportUnwantedToken(DefaultErrorStrategy.java:377)
	at org.antlr.v4.runtime.DefaultErrorStrategy.singleTokenDeletion(DefaultErrorStrategy.java:548)
	at org.antlr.v4.runtime.DefaultErrorStrategy.recoverInline(DefaultErrorStrategy.java:467)
	at org.antlr.v4.runtime.Parser.match(Parser.java:208)
	at org.elasticsearch.xpack.esql.parser.EsqlBaseParser.singleStatement(EsqlBaseParser.java:340)
	at org.elasticsearch.xpack.esql.parser.EsqlBaseParser.statements(EsqlBaseParser.java:289)
	at org.elasticsearch.xpack.esql.parser.EsqlParser.invokeParser(EsqlParser.java:166)
	at org.elasticsearch.xpack.esql.parser.EsqlParser.createQuery(EsqlParser.java:132)
	at org.elasticsearch.xpack.esql.session.EsqlSession.parse(EsqlSession.java:456)
	at org.elasticsearch.xpack.esql.session.EsqlSession.execute(EsqlSession.java:189)
	at org.elasticsearch.xpack.esql.execution.PlanExecutor.lambda$esql$2(PlanExecutor.java:102)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionListener.run(ActionListener.java:465)
	at org.elasticsearch.xpack.esql.execution.PlanExecutor.esql(PlanExecutor.java:102)
	at org.elasticsearch.xpack.esql.plugin.TransportEsqlQueryAction.innerExecute(TransportEsqlQueryAction.java:257)
	at org.elasticsearch.xpack.esql.plugin.TransportEsqlQueryAction.doExecuteForked(TransportEsqlQueryAction.java:227)
	at org.elasticsearch.xpack.esql.plugin.TransportEsqlQueryAction.lambda$doExecute$5(TransportEsqlQueryAction.java:217)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionRunnable$4.doRun(ActionRunnable.java:101)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.TimedRunnable.doRun(TimedRunnable.java:35)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1088)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
"""
  },
  "status": 400
}
``` 


But when I remove the last empty char from the end it works

```json
POST _query?error_trace=true
{
  "query": "TS metrics-hostmetricsreceiver.otel-default | WHERE @timestamp >= \"2025-11-26T08:41:01.000Z\" AND @timestamp <= \"2025-11-26T13:11:00.000Z\" | PROMQL step 1h (avg by (host.name) (rate(system.cpu.time[1h])))"
}
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `49858d1795ffc9b508a0cc5e112d7b1b611120e3`
**Instance ID:** `elastic__elasticsearch-138736`
**Language:** `Java`
