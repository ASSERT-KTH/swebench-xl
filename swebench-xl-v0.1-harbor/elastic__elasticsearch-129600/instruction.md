# Task

## Synthetic _source can't be retrieved with overlapping keys in flattened field

### Elasticsearch Version

main

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

macOS 15.3

### Problem Description

When using flattened fields in a logsdb index, synthetic source is used to reconstruct the value of the flattened field. In case the key/value pairs in the flattened field have an object/scalar mismatch, the search request fails because the _source can't be constructed.

### Steps to Reproduce

```
PUT my-index
{
  "settings": {
    "mode": "logsdb"
  },
  "mappings": {
    "properties": {
        "test": {
            "type": "flattened"
        }
    }
  }
}

POST my-index/_doc
{
  "@timestamp": "2025",
  "test": {
      "nested.doublynested": 123,
      "nested": {
        "doublynested": {
          "gotcha": true
        }
      }
    }
}

GET my-index/_search // returns 500
```

### Logs (if relevant)

```
failure encoding chunk com.fasterxml.jackson.core.JsonParseException: Duplicate field 'doublynested'
   │       at [Source: (org.elasticsearch.common.io.stream.ByteBufferStreamInput); line: 1, column: 112]
   │      	at com.fasterxml.jackson.core@2.17.2/com.fasterxml.jackson.core.json.JsonReadContext._checkDup(JsonReadContext.java:250)
   │      	at com.fasterxml.jackson.core@2.17.2/com.fasterxml.jackson.core.json.JsonReadContext.setCurrentName(JsonReadContext.java:244)
   │      	at com.fasterxml.jackson.core@2.17.2/com.fasterxml.jackson.core.json.UTF8StreamJsonParser.nextToken(UTF8StreamJsonParser.java:758)
   │      	at com.fasterxml.jackson.core@2.17.2/com.fasterxml.jackson.core.JsonGenerator._copyCurrentContents(JsonGenerator.java:2657)
   │      	at com.fasterxml.jackson.core@2.17.2/com.fasterxml.jackson.core.JsonGenerator.copyCurrentStructure(JsonGenerator.java:2638)
   │      	at org.elasticsearch.xcontent.impl@9.1.0-SNAPSHOT/org.elasticsearch.xcontent.provider.json.JsonXContentGenerator.copyCurrentStructure(JsonXContentGenerator.java:540)
   │      	at org.elasticsearch.xcontent.impl@9.1.0-SNAPSHOT/org.elasticsearch.xcontent.provider.json.JsonXContentGenerator.writeRawField(JsonXContentGenerator.java:475)
   │      	at org.elasticsearch.xcontent.impl@9.1.0-SNAPSHOT/org.elasticsearch.xcontent.provider.json.JsonXContentGenerator.writeRawField(JsonXContentGenerator.java:466)
   │      	at org.elasticsearch.xcontent@9.1.0-SNAPSHOT/org.elasticsearch.xcontent.XContentBuilder.rawField(XContentBuilder.java:1205)
   │      	at org.elasticsearch.server@9.1.0-SNAPSHOT/org.elasticsearch.common.xcontent.XContentHelper.writeRawField(XContentHelper.java:578)
   │      	at org.elasticsearch.server@9.1.0-SNAPSHOT/org.elasticsearch.search.SearchHit.toInnerXContent(SearchHit.java:856)
   │      	at org.elasticsearch.server@9.1.0-SNAPSHOT/org.elasticsearch.search.SearchHit.toXContent(SearchHit.java:801)
   │      	at org.elasticsearch.server@9.1.0-SNAPSHOT/org.elasticsearch.rest.ChunkedRestResponseBodyPart$1.encodeChunk(ChunkedRestResponseBodyPart.java:161)
   │      	at org.elasticsearch.server@9.1.0-SNAPSHOT/org.elasticsearch.rest.RestController$EncodedLengthTrackingChunkedRestResponseBodyPart.encodeChunk(RestController.java:1002)
   │      	at org.elasticsearch.transport.netty4@9.1.0-SNAPSHOT/org.elasticsearch.http.netty4.Netty4HttpPipeliningHandler.writeChunk(Netty4HttpPipeliningHandler.java:440)
   │      	at org.elasticsearch.transport.netty4@9.1.0-SNAPSHOT/org.elasticsearch.http.netty4.Netty4HttpPipeliningHandler.doWriteChunkedResponse(Netty4HttpPipeliningHandler.java:267)
   │      	at org.elasticsearch.transport.netty4@9.1.0-SNAPSHOT/org.elasticsearch.http.netty4.Netty4HttpPipeliningHandler.doWrite(Netty4HttpPipeliningHandler.java:235)
   │      	at org.elasticsearch.transport.netty4@9.1.0-SNAPSHOT/org.elasticsearch.http.netty4.Netty4HttpPipeliningHandler.write(Netty4HttpPipeliningHandler.java:188)
   │      	at io.netty.transport@4.1.115.Final/io.netty.channel.AbstractChannelHandlerContext.invokeWrite0(AbstractChannelHandlerContext.java:891)
   │      	at io.netty.transport@4.1.115.Final/io.netty.channel.AbstractChannelHandlerContext.invokeWriteAndFlush(AbstractChannelHandlerContext.java:956)
   │      	at io.netty.transport@4.1.115.Final/io.netty.channel.AbstractChannelHandlerContext$WriteTask.run(AbstractChannelHandlerContext.java:1263)
   │      	at io.netty.common@4.1.115.Final/io.netty.util.concurrent.AbstractEventExecutor.runTask(AbstractEventExecutor.java:173)
   │      	at io.netty.common@4.1.115.Final/io.netty.util.concurrent.AbstractEventExecutor.safeExecute(AbstractEventExecutor.java:166)
   │      	at io.netty.common@4.1.115.Final/io.netty.util.concurrent.SingleThreadEventExecutor.runAllTasks(SingleThreadEventExecutor.java:472)
   │      	at io.netty.transport@4.1.115.Final/io.netty.channel.nio.NioEventLoop.run(NioEventLoop.java:569)
   │      	at io.netty.common@4.1.115.Final/io.netty.util.concurrent.SingleThreadEventExecutor$4.run(SingleThreadEventExecutor.java:997)
   │      	at io.netty.common@4.1.115.Final/io.netty.util.internal.ThreadExecutorMap$2.run(ThreadExecutorMap.java:74)
   │      	at java.base/java.lang.Thread.run(Thread.java:1575)
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `1edf77c1df6292998e9eb496dd243418af224857`
**Instance ID:** `elastic__elasticsearch-129600`
**Language:** `Java`
