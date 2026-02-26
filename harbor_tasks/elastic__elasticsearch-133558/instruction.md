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
