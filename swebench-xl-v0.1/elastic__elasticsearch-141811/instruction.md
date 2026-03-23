# Task

## Bad error handling for wrong PIT format

### Elasticsearch Version

9.3.0-SNAPSHOT

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

cloud

### Problem Description

Calling the `DELETE /_pit` endpoint with a malformed id causes the server to throw an unhandled exception. The id I'm using used to be valid, since it was generated with a server version before 8.0.0, and it's still accepted by the server up to version 9.2.3.

### Steps to Reproduce

Kibana call:
```
DELETE /_pit
{
  "id": "46ToAwMDaWR5BXV1aWQyKwZub2RlXzMAAAAAAAAAACoBYwADaWR4BXV1aWQxAgZub2RlXzEAAAAAAAAAAAEBYQADaWR5BXV1aWQyKgZub2RlXzIAAAAAAAAAAAwBYgACBXV1aWQyAAAFdXVpZDEAAQltYXRjaF9hbGw_gAAAAA=="
}
```

If sent to any server version <9.3.0, this will return:
```
{
  "succeeded": false,
  "num_freed": 0
}
```
As the PIT does not exist, but it's still recognized. Server version 9.3.0-SNAPSHOT returns:

```
{"error":{"root_cause":[{"type":"illegal_state_exception","reason":"unexpected byte [0x06]"}],"type":"illegal_state_exception","reason":"unexpected byte [0x06]"},"status":500}
```
With error stacktrace: 
```
java.lang.IllegalStateException: unexpected byte [0x06]
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.io.stream.StreamInput.readBoolean(StreamInput.java:675)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.io.stream.StreamInput.readBoolean(StreamInput.java:665)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.io.stream.StreamInput.readOptionalString(StreamInput.java:424)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.search.SearchContextIdForNode.<init>(SearchContextIdForNode.java:40)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.search.SearchContextId.readShardsMapEntry(SearchContextId.java:140)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.common.io.stream.StreamInput.readCollection(StreamInput.java:1367)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.search.SearchContextId.decode(SearchContextId.java:112)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.search.TransportClosePointInTimeAction.doExecute(TransportClosePointInTimeAction.java:57)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.search.TransportClosePointInTimeAction.doExecute(TransportClosePointInTimeAction.java:34)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.TransportAction$RequestFilterChain.proceed(TransportAction.java:135)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.ActionFilter$Simple.apply(ActionFilter.java:54)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.TransportAction$RequestFilterChain.proceed(TransportAction.java:132)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.MappedActionFilters$MappedFilterChain.proceed(MappedActionFilters.java:71)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.MappedActionFilters.apply(MappedActionFilters.java:49)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.TransportAction$RequestFilterChain.proceed(TransportAction.java:132)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.action.filter.SecurityActionFilter.lambda$applyInternal$6(SecurityActionFilter.java:202)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionListenerImplementations$DelegatingFailureActionListener.onResponse(ActionListenerImplementations.java:233)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:423)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:343)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.SubscribableListener.addListener(SubscribableListener.java:239)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.SubscribableListener.addListener(SubscribableListener.java:197)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.action.filter.SecurityActionFilter.applyInternal(SecurityActionFilter.java:200)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.action.filter.SecurityActionFilter.apply(SecurityActionFilter.java:134)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.TransportAction$RequestFilterChain.proceed(TransportAction.java:132)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.TransportAction.handleExecution(TransportAction.java:96)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.support.TransportAction.execute(TransportAction.java:59)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.tasks.TaskManager.registerAndExecute(TaskManager.java:216)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.client.internal.node.NodeClient.executeLocally(NodeClient.java:107)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.client.internal.node.NodeClient.doExecute(NodeClient.java:85)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.client.internal.support.AbstractClient.execute(AbstractClient.java:160)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.search.RestClosePointInTimeAction.lambda$prepareRequest$0(RestClosePointInTimeAction.java:44)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.rest.BaseRestHandler.handleRequest(BaseRestHandler.java:143)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.rest.RestController$1.onResponse(RestController.java:472)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.rest.RestController$1.onResponse(RestController.java:466)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.rest.SecurityRestFilter.doHandleRequest(SecurityRestFilter.java:105)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.rest.SecurityRestFilter.lambda$intercept$0(SecurityRestFilter.java:90)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionListener$2.onResponse(ActionListener.java:258)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.authc.support.SecondaryAuthenticator.lambda$authenticateAndAttachToContext$3(SecondaryAuthenticator.java:99)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.authc.support.SecondaryAuthenticator.authenticate(SecondaryAuthenticator.java:109)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.authc.support.SecondaryAuthenticator.authenticateAndAttachToContext(SecondaryAuthenticator.java:90)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.rest.SecurityRestFilter.lambda$intercept$2(SecurityRestFilter.java:80)
	at org.elasticsearch.security@9.3.0-SNAPSHOT/org.elasticsearch.xpack.security.rest.SecurityRestFilter.intercept(SecurityRestFilter.java:96)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.rest.RestController.dispatchRequest(RestController.java:466)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.rest.RestController.lambda$maybeAggregateAndDispatchRequest$4(RestController.java:404)
	at org.elasticsearch.server@9.3.0-SNAPSHOT/org.elasticsearch.rest.RestContentAggregator$AggregationChunkHandler.onNext(RestContentAggregator.java:78)
	at org.elasticsearch.transport.netty4@9.3.0-SNAPSHOT/org.elasticsearch.http.netty4.Netty4HttpRequestBodyStream.handleNettyContent(Netty4HttpRequestBodyStream.java:87)
	at org.elasticsearch.transport.netty4@9.3.0-SNAPSHOT/org.elasticsearch.http.netty4.Netty4HttpPipeliningHandler.channelRead(Netty4HttpPipeliningHandler.java:146)
	at io.netty.transport@4.1.130.Final/io.netty.channel.AbstractChannelHandlerContext.invokeChannelRead(AbstractChannelHandlerContext.java:442)
	at io.netty.transport@4.1.130.Final/io.netty.channel.AbstractChannelHandlerContext.invokeChannelRead(AbstractChannelHandlerContext.java:420)
	at io.netty.transport@4.1.130.Final/io.netty.channel.AbstractChannelHandlerContext.fireChannelRead(AbstractChannelHandlerContext.java:412)
	at io.netty.handler@4.1.130.Final/io.netty.handler.flow.FlowControlHandler.dequeue(FlowControlHandler.java:202)
	at io.netty.handler@4.1.130.Final/io.netty.handler.flow.FlowControlHandler.read(FlowControlHandler.java:139)
	at io.netty.transport@4.1.130.Final/io.netty.channel.AbstractChannelHandlerContext.invokeRead(AbstractChannelHandlerContext.java:847)
	at io.netty.transport@4.1.130.Final/io.netty.channel.AbstractChannelHandlerContext.read(AbstractChannelHandlerContext.java:824)
	at io.netty.common@4.1.130.Final/io.netty.util.concurrent.AbstractEventExecutor.runTask(AbstractEventExecutor.java:173)
	at io.netty.common@4.1.130.Final/io.netty.util.concurrent.AbstractEventExecutor.safeExecute(AbstractEventExecutor.java:166)
	at io.netty.common@4.1.130.Final/io.netty.util.concurrent.SingleThreadEventExecutor.runAllTasks(SingleThreadEventExecutor.java:472)
	at io.netty.transport@4.1.130.Final/io.netty.channel.nio.NioEventLoop.run(NioEventLoop.java:566)
	at io.netty.common@4.1.130.Final/io.netty.util.concurrent.SingleThreadEventExecutor$4.run(SingleThreadEventExecutor.java:998)
	at io.netty.common@4.1.130.Final/io.netty.util.internal.ThreadExecutorMap$2.run(ThreadExecutorMap.java:74)
	at java.base/java.lang.Thread.run(Thread.java:1474)
```

I already had a chat with @DaveCTurner about this, he confirmed that while the PIT format is not accepted anymore by 9.3.0, "it is a bug that we even try to decode it - the first thing we check is the protocol version, and we should be bailing out at that point, and it is also a bug that a decoding failure is a 500 given that users can send arbitrary data here". 

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `50103af6d8af56a4fa92d280d5f8d49e3bcd980c`
**Instance ID:** `elastic__elasticsearch-141811`
**Language:** `Java`
