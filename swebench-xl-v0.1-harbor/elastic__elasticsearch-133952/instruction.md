# Task

## Unexpected warning printed when creating a tsdb data stream using builtin metrics-otel@template index template

When creating a tsdb data stream with a `passthrough` object mapper can result in the following error: ` Invalid [path] value [resource.attributes.os.version] for field alias [host.os.version]: an alias must refer to an existing field in the mappings` printed as a warning in the logs. The data stream creation is successful. However the warning log isn't supposed to be printed. The data stream is created using the builtin `metrics-otel@template` index template. 

Full warning log with stack trace:

<details>

```
[2025-07-31T17:05:19,405][WARN ][o.e.x.l.LogsdbIndexModeSettingsProvider] [runTask-0] unable to create mapper service for index [.ds-metrics-hostmetricsreceiver.otel-default-2025.07.31-000001] org.elasticsearch.index.mapper.MapperParsingException: Invalid [path] value [resource.attributes.os.version] for field alias [host.os.version]: an alias must refer to an existing field in the mappings.
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.FieldAliasMapper.validate(FieldAliasMapper.java:90)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.ObjectMapper.validate(ObjectMapper.java:553)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.ObjectMapper.validate(ObjectMapper.java:553)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.ObjectMapper.validate(ObjectMapper.java:553)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.Mapping.validate(Mapping.java:117)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.DocumentMapper.validate(DocumentMapper.java:136)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.MapperService.newDocumentMapper(MapperService.java:609)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.MapperService.doMerge(MapperService.java:592)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.index.mapper.MapperService.merge(MapperService.java:464)
        at org.elasticsearch.xpack.logsdb.LogsdbIndexModeSettingsProvider.getMappingHints(LogsdbIndexModeSettingsProvider.java:270)
        at org.elasticsearch.xpack.logsdb.LogsdbIndexModeSettingsProvider.getAdditionalIndexSettings(LogsdbIndexModeSettingsProvider.java:118)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateIndexService.aggregateIndexSettings(MetadataCreateIndexService.java:1118)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateIndexService.applyCreateIndexRequestWithV2Template(MetadataCreateIndexService.java:758)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateIndexService.applyCreateIndexRequest(MetadataCreateIndexService.java:446)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateIndexService.applyCreateIndexRequest(MetadataCreateIndexService.java:511)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateDataStreamService.createBackingIndex(MetadataCreateDataStreamService.java:399)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateDataStreamService.createDataStream(MetadataCreateDataStreamService.java:300)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateDataStreamService.createDataStream(MetadataCreateDataStreamService.java:190)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.metadata.MetadataCreateDataStreamService.createDataStream(MetadataCreateDataStreamService.java:135)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.action.admin.indices.create.AutoCreateAction$TransportAction$CreateIndexTask.execute(AutoCreateAction.java:269)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.action.admin.indices.create.AutoCreateAction$TransportAction.lambda$new$0(AutoCreateAction.java:124)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService.innerExecuteTasks(MasterService.java:1076)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService.executeTasks(MasterService.java:1039)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService.executeAndPublishBatch(MasterService.java:246)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService$BatchingTaskQueue$Processor.lambda$run$2(MasterService.java:1692)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.action.ActionListener.run(ActionListener.java:465)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService$BatchingTaskQueue$Processor.run(MasterService.java:1689)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService$5.lambda$doRun$0(MasterService.java:1284)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.action.ActionListener.run(ActionListener.java:465)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.cluster.service.MasterService$5.doRun(MasterService.java:1263)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:1067)
        at org.elasticsearch.server@9.2.0-SNAPSHOT/org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:27)
        at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1095)
        at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:619)
        at java.base/java.lang.Thread.run(Thread.java:1447)
```

</details>

The issue can be reproduced by execution the following in a new cluster:

```
PUT /_data_stream/metrics-test.otel-test
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f406f025e1ced060b1845284319eb8e3ab671dd1`
**Instance ID:** `elastic__elasticsearch-133952`
**Language:** `Java`
