# Task

## Snapshot delete tasks do not complete if blobs-to-delete list exceeds 2GiB

When deleting snapshots, we accumulate a collection of blobs for post-commit deletion in a compressed `ReleasableBytesStreamOutput`, which has a size limit of 2GiB. If we reach this limit then the following message is logged:

```
[2024-11-03T07:36:42,183][WARN ][org.elasticsearch.repositories.blobstore.BlobStoreRepository] [REDACTED] [REDACTED] failed to delete shard data for shard [REDACTED][0]
java.lang.IllegalArgumentException: ReleasableBytesStreamOutput cannot hold more than 2GB of data
    at org.elasticsearch.common.io.stream.BytesStreamOutput.ensureCapacity(BytesStreamOutput.java:173) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.BytesStreamOutput.writeBytes(BytesStreamOutput.java:84) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.Streams$FlushOnCloseOutputStream.writeBytes(Streams.java:220) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.StreamOutput.write(StreamOutput.java:514) ~[elasticsearch-8.15.0.jar:?]
    at java.util.zip.DeflaterOutputStream.deflate(DeflaterOutputStream.java:261) ~[?:?]
    at java.util.zip.DeflaterOutputStream.write(DeflaterOutputStream.java:210) ~[?:?]
    at java.io.BufferedOutputStream.flushBuffer(BufferedOutputStream.java:125) ~[?:?]
    at java.io.BufferedOutputStream.implWrite(BufferedOutputStream.java:222) ~[?:?]
    at java.io.BufferedOutputStream.write(BufferedOutputStream.java:200) ~[?:?]
    at org.elasticsearch.common.io.stream.OutputStreamStreamOutput.writeBytes(OutputStreamStreamOutput.java:29) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.StreamOutput.writeBytes(StreamOutput.java:108) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.StreamOutput.writeString(StreamOutput.java:443) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.StreamOutput.writeString(StreamOutput.java:408) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$ShardBlobsToDelete$ShardSnapshotMetaDeleteResult.writeTo(BlobStoreRepository.java:1575) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$ShardBlobsToDelete.addShardDeleteResult(BlobStoreRepository.java:1623) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion$IndexSnapshotsDeletion$ShardSnapshotsDeletion.deleteFromShardSnapshotMeta(BlobStoreRepository.java:1318) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion$IndexSnapshotsDeletion$ShardSnapshotsDeletion.doRun(BlobStoreRepository.java:1283) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:984) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:26) ~[elasticsearch-8.15.0.jar:?]
    at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1144) ~[?:?]
    at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:642) ~[?:?]
    at java.lang.Thread.run(Thread.java:1570) ~[?:?]
```

If that happens then it looks like `org.elasticsearch.repositories.blobstore.BlobStoreRepository#resolveFilesToDelete` will also throw an exception, and it does so in contexts where such an exception will bubble up the stack without completing the relevant listener:

```
[WARN ][org.elasticsearch.snapshots.SnapshotsService] [REDACTED] [REDACTED] failed to complete snapshot deletion for [REDACTED] from repository [REDACTED]
java.lang.IllegalArgumentException: ReleasableBytesStreamOutput cannot hold more than 2GB of data
    at org.elasticsearch.common.io.stream.BytesStreamOutput.ensureCapacity(BytesStreamOutput.java:173) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.BytesStreamOutput.writeBytes(BytesStreamOutput.java:84) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.Streams$FlushOnCloseOutputStream.writeBytes(Streams.java:220) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.io.stream.StreamOutput.write(StreamOutput.java:514) ~[elasticsearch-8.15.0.jar:?]
    at java.util.zip.DeflaterOutputStream.deflate(DeflaterOutputStream.java:261) ~[?:?]
    at java.util.zip.DeflaterOutputStream.finish(DeflaterOutputStream.java:226) ~[?:?]
    at java.util.zip.DeflaterOutputStream.close(DeflaterOutputStream.java:244) ~[?:?]
    at java.io.FilterOutputStream.close(FilterOutputStream.java:193) ~[?:?]
    at org.elasticsearch.common.io.stream.OutputStreamStreamOutput.close(OutputStreamStreamOutput.java:39) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$ShardBlobsToDelete.getBlobPaths(BlobStoreRepository.java:1638) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion.resolveFilesToDelete(BlobStoreRepository.java:1408) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion.cleanupUnlinkedShardLevelBlobs(BlobStoreRepository.java:1387) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion.lambda$runWithUniqueShardMetadataNaming$1(BlobStoreRepository.java:1091) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.ActionListener$2.onResponse(ActionListener.java:249) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:386) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:306) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:335) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:249) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.repositories.blobstore.BlobStoreRepository$10.clusterStateProcessed(BlobStoreRepository.java:2886) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.cluster.service.MasterService$UnbatchedExecutor.lambda$execute$0(MasterService.java:571) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.cluster.service.MasterService$ExecutionResult.onPublishSuccess(MasterService.java:956) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.cluster.service.MasterService$4.onResponse(MasterService.java:375) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.cluster.service.MasterService$4.onResponse(MasterService.java:370) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.ActionListenerImplementations$RunAfterActionListener.onResponse(ActionListenerImplementations.java:269) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:32) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.action.support.ThreadedActionListener$1.doRun(ThreadedActionListener.java:39) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:984) ~[elasticsearch-8.15.0.jar:?]
    at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:26) ~[elasticsearch-8.15.0.jar:?]
    at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1144) ~[?:?]
    at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:642) ~[?:?]
    at java.lang.Thread.run(Thread.java:1570) ~[?:?]
    Suppressed: java.lang.IllegalArgumentException: ReleasableBytesStreamOutput cannot hold more than 2GB of data
        at org.elasticsearch.common.io.stream.BytesStreamOutput.ensureCapacity(BytesStreamOutput.java:173) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.common.io.stream.BytesStreamOutput.writeBytes(BytesStreamOutput.java:84) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.common.io.Streams$FlushOnCloseOutputStream.writeBytes(Streams.java:220) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.common.io.stream.StreamOutput.write(StreamOutput.java:514) ~[elasticsearch-8.15.0.jar:?]
        at java.util.zip.DeflaterOutputStream.deflate(DeflaterOutputStream.java:261) ~[?:?]
        at java.util.zip.DeflaterOutputStream.write(DeflaterOutputStream.java:210) ~[?:?]
        at java.io.BufferedOutputStream.flushBuffer(BufferedOutputStream.java:125) ~[?:?]
        at java.io.BufferedOutputStream.implFlush(BufferedOutputStream.java:252) ~[?:?]
        at java.io.BufferedOutputStream.flush(BufferedOutputStream.java:240) ~[?:?]
        at java.io.FilterOutputStream.close(FilterOutputStream.java:184) ~[?:?]
        at org.elasticsearch.common.io.stream.OutputStreamStreamOutput.close(OutputStreamStreamOutput.java:39) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.repositories.blobstore.BlobStoreRepository$ShardBlobsToDelete.getBlobPaths(BlobStoreRepository.java:1638) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion.resolveFilesToDelete(BlobStoreRepository.java:1408) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion.cleanupUnlinkedShardLevelBlobs(BlobStoreRepository.java:1387) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.repositories.blobstore.BlobStoreRepository$SnapshotsDeletion.lambda$runWithUniqueShardMetadataNaming$1(BlobStoreRepository.java:1091) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.ActionListener$2.onResponse(ActionListener.java:249) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.support.SubscribableListener$SuccessResult.complete(SubscribableListener.java:386) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.support.SubscribableListener.tryComplete(SubscribableListener.java:306) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.support.SubscribableListener.setResult(SubscribableListener.java:335) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.support.SubscribableListener.onResponse(SubscribableListener.java:249) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.repositories.blobstore.BlobStoreRepository$10.clusterStateProcessed(BlobStoreRepository.java:2886) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.cluster.service.MasterService$UnbatchedExecutor.lambda$execute$0(MasterService.java:571) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.cluster.service.MasterService$ExecutionResult.onPublishSuccess(MasterService.java:956) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.cluster.service.MasterService$4.onResponse(MasterService.java:375) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.cluster.service.MasterService$4.onResponse(MasterService.java:370) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.ActionListenerImplementations$RunAfterActionListener.onResponse(ActionListenerImplementations.java:269) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.support.ContextPreservingActionListener.onResponse(ContextPreservingActionListener.java:32) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.action.support.ThreadedActionListener$1.doRun(ThreadedActionListener.java:39) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.common.util.concurrent.ThreadContext$ContextPreservingAbstractRunnable.doRun(ThreadContext.java:984) ~[elasticsearch-8.15.0.jar:?]
        at org.elasticsearch.common.util.concurrent.AbstractRunnable.run(AbstractRunnable.java:26) ~[elasticsearch-8.15.0.jar:?]
        at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1144) ~[?:?]
        at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:642) ~[?:?]
        at java.lang.Thread.run(Thread.java:1570) ~[?:?]
```

We must avoid leaking this listener on such an exception.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d8ae9aecdec0181a1f422609854084f42681c435`
**Instance ID:** `elastic__elasticsearch-133558`
**Language:** `Java`
