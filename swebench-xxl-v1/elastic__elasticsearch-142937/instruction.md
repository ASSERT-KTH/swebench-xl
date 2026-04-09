# Task

## Failure serializing org.elasticsearch.xpack.gpu.NodeGpuStatsResponse

This issue has been observed in Serverless.

```
java.lang.IllegalStateException: Negative longs unsupported, use writeLong or writeZLong for negative numbers [-1]
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.io.stream.StreamOutput.writeVLong(StreamOutput.java:289)
	at org.elasticsearch.xpack.gpu@9.4.0/org.elasticsearch.xpack.gpu.NodeGpuStatsResponse.writeTo(NodeGpuStatsResponse.java:56)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.OutboundHandler.serializeMessageBody(OutboundHandler.java:372)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.OutboundHandler.serialize(OutboundHandler.java:313)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.OutboundHandler.sendMessage(OutboundHandler.java:238)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.OutboundHandler.sendResponse(OutboundHandler.java:150)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.TcpTransportChannel.sendResponse(TcpTransportChannel.java:57)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.TaskTransportChannel.sendResponse(TaskTransportChannel.java:35)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.ChannelActionListener.onResponse(ChannelActionListener.java:33)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.ChannelActionListener.onResponse(ChannelActionListener.java:20)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListener.respondAndRelease(ActionListener.java:389)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.nodes.TransportNodesAction.nodeOperationAsync(TransportNodesAction.java:257)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.nodes.TransportNodesAction$NodeTransportHandler.lambda$messageReceived$0(TransportNodesAction.java:273)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListener.run(ActionListener.java:468)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.nodes.TransportNodesAction$NodeTransportHandler.messageReceived(TransportNodesAction.java:271)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.SecurityServerTransportInterceptor$ProfileSecuredRequestHandler$1.doRun(SecurityServerTransportInterceptor.java:318)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.SecurityServerTransportInterceptor$ProfileSecuredRequestHandler$3.onResponse(SecurityServerTransportInterceptor.java:371)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.SecurityServerTransportInterceptor$ProfileSecuredRequestHandler$3.onResponse(SecurityServerTransportInterceptor.java:360)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService.lambda$authorizeAction$8(AuthorizationService.java:494)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService$AuthorizationResultListener.onResponse(AuthorizationService.java:1167)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService$AuthorizationResultListener.onResponse(AuthorizationService.java:1133)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService.lambda$authorizeAction$9(AuthorizationService.java:508)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.RBACEngine.authorizeClusterAction(RBACEngine.java:214)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService.authorizeAction(AuthorizationService.java:498)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService.maybeAuthorizeRunAs(AuthorizationService.java:474)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService.lambda$authorize$3(AuthorizationService.java:361)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListener$2.onResponse(ActionListener.java:258)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:33)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.RBACEngine.lambda$resolveAuthorizationInfo$0(RBACEngine.java:179)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.store.CompositeRolesStore.lambda$getRoles$4(CompositeRolesStore.java:217)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.store.CompositeRolesStore.lambda$getRole$6(CompositeRolesStore.java:236)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.xcore@9.4.0/org.elasticsearch.xpack.core.security.authz.store.RoleReferenceIntersection.lambda$buildRole$0(RoleReferenceIntersection.java:49)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.support.GroupedActionListener.onResponse(GroupedActionListener.java:57)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.store.CompositeRolesStore.buildRoleFromRoleReference(CompositeRolesStore.java:334)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.store.CompositeRolesStore.lambda$getRole$5(CompositeRolesStore.java:235)
	at org.elasticsearch.xcore@9.4.0/org.elasticsearch.xpack.core.security.authz.store.RoleReferenceIntersection.lambda$buildRole$1(RoleReferenceIntersection.java:53)
	at java.base/java.util.ImmutableCollections$List12.forEach(ImmutableCollections.java:681)
	at org.elasticsearch.xcore@9.4.0/org.elasticsearch.xpack.core.security.authz.store.RoleReferenceIntersection.buildRole(RoleReferenceIntersection.java:53)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.store.CompositeRolesStore.getRole(CompositeRolesStore.java:234)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.store.CompositeRolesStore.getRoles(CompositeRolesStore.java:210)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.RBACEngine.resolveAuthorizationInfo(RBACEngine.java:175)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authz.AuthorizationService.authorize(AuthorizationService.java:377)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.ServerTransportFilter.lambda$inbound$1(ServerTransportFilter.java:115)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListenerImplementations$ResponseWrappingActionListener.onResponse(ActionListenerImplementations.java:261)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authc.AuthenticatorChain.lambda$authenticate$1(AuthenticatorChain.java:91)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.action.ActionListener$2.onResponse(ActionListener.java:258)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authc.AuthenticatorChain.authenticate(AuthenticatorChain.java:111)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authc.AuthenticationService.authenticate(AuthenticationService.java:274)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.authc.AuthenticationService.authenticate(AuthenticationService.java:206)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.ServerTransportFilter.authenticate(ServerTransportFilter.java:128)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.ServerTransportFilter.inbound(ServerTransportFilter.java:106)
	at org.elasticsearch.security@9.4.0/org.elasticsearch.xpack.security.transport.SecurityServerTransportInterceptor$ProfileSecuredRequestHandler.messageReceived(SecurityServerTransportInterceptor.java:382)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.RequestHandlerRegistry.processMessageReceived(RequestHandlerRegistry.java:86)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.InboundHandler.doHandleRequest(InboundHandler.java:319)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.transport.InboundHandler$1.doRun(InboundHandler.java:331)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1114)
	at org.elasticsearch.server@9.4.0/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1090)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:614)
	at java.base/java.lang.Thread.run(Thread.java:1474)
```

relates https://github.com/elastic/elasticsearch/pull/141932

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `c7f0870b296eb218919155875b3f1d4658303dfc`
**Instance ID:** `elastic__elasticsearch-142937`
**Language:** `Java`
