# Task

## `GET /_migration/deprecations` doesn't check disk watermarks against correct settings

In `TransportNodeDeprecationCheckAction` we check for nodes exceeding the low watermark by passing in the (filtered) static settings from the local node, and the (filtered) dynamic settings from its cluster state, and reporting a violation of the watermark if the node's disk usage is too high according to either of these settings sets:

https://github.com/elastic/elasticsearch/blob/aced42f487634fec9b270a234cbad510f3a4cbc6/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/TransportNodeDeprecationCheckAction.java#L138-L140

https://github.com/elastic/elasticsearch/blob/aced42f487634fec9b270a234cbad510f3a4cbc6/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/TransportNodeDeprecationCheckAction.java#L162-L165

There's several issues with this:

1. There should be no facility for filtering out the relevant settings here.
2. The node-local settings have no relevance to disk watermarks unless the node is the elected master.
3. Even the elected master's node-local settings have no relevance to disk watermarks if the settings are overridden with dynamic values.
4. Conversely, if the settings are _not_ overriden with dynamic values then checking `filteredClusterState.metadata().settings()` means checking against the default value of 85%, even if the master's node-local settings specify a different value.

Instead, since this action is originally invoked by the elected master, it should include in its request the actual disk watermark that the node should use.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8c2f569f17430af28c24890056c396ad9c2dd24b`
**Instance ID:** `elastic__elasticsearch-138115`
**Language:** `Java`
