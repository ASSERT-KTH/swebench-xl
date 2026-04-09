# Task

## "Reset an anomaly detection job" API fails with error 500

### Elasticsearch Version

9.3.4

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

linux

### Problem Description

Stacktrace:

org.elasticsearch.transport.RemoteTransportException: [es-es-index-557d45596-5mtnc][100.64.17.99:9300][cluster:admin/xpack/ml/job/reset]
Caused by: org.elasticsearch.common.io.stream.NotSerializableExceptionWrapper: no_such_element_exception: No value present
	at java.util.Optional.get(Optional.java:143)
	at org.elasticsearch.xpack.core.ml.utils.MlIndexAndAlias.latestIndex(MlIndexAndAlias.java:529)
	at org.elasticsearch.xpack.core.ml.utils.MlIndexAndAlias.latestIndexMatchingBaseName(MlIndexAndAlias.java:604)
	at org.elasticsearch.xpack.ml.job.persistence.JobResultsProvider.createJobResultIndex(JobResultsProvider.java:315)
	at org.elasticsearch.xpack.ml.action.TransportResetJobAction.lambda$resetJob$12(TransportResetJobAction.java:258)
	at org.elasticsearch.action.ActionListener$2.onResponse(ActionListener.java:258)
	at org.elasticsearch.xpack.ml.job.persistence.JobConfigProvider.parseJobLenientlyFromSource(JobConfigProvider.java:763)
	at org.elasticsearch.xpack.ml.job.persistence.JobConfigProvider$1.onResponse(JobConfigProvider.java:175)
	at org.elasticsearch.xpack.ml.job.persistence.JobConfigProvider$1.onResponse(JobConfigProvider.java:166)
	at org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:223)
	at org.elasticsearch.tasks.TaskManager$1.onResponse(TaskManager.java:217)
	at org.elasticsearch.action.ActionListenerImplementations$RunBeforeActionListener.onResponse(ActionListenerImplementations.java:350)
	at org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.action.ActionListenerImplementations$MappedActionListener.onResponse(ActionListenerImplementations.java:111)
	at org.elasticsearch.action.ActionListenerResponseHandler.handleResponse(ActionListenerResponseHandler.java:49)
	at org.elasticsearch.transport.TransportService$ContextRestoreResponseHandler.handleResponse(TransportService.java:1514)
	at org.elasticsearch.transport.InboundHandler.doHandleResponse(InboundHandler.java:465)
	at org.elasticsearch.transport.InboundHandler$2.doRun(InboundHandler.java:425)
	at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
	at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.lang.Thread.run(Thread.java:1474)

### Steps to Reproduce

unknown

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `5c8c6e045f273fb8625c296a8132b943181abc4a`
**Instance ID:** `elastic__elasticsearch-144545`
**Language:** `Java`
