# Task

## [CI] FieldExtractorIT testTsIndexConflictingTypes {null} failing | [CI] FieldExtractorIT testTsIndexConflictingTypes {NONE} failing | [CI] EsqlClientYamlIT test {p0=esql/40_tsdb/TS Command grouping on text field} failing | [CI] EsqlClientYamlIT test {p0=esql/40_tsdb/to_aggregate_metric_double with multi_values} failing | Investigate potential deprecation warning leak

### Issue 1: [CI] FieldExtractorIT testTsIndexConflictingTypes {null} failing

**Build Scans:**
- [elasticsearch-intake #35224 / bc-upgrade-tests-part3](https://gradle-enterprise.elastic.co/s/tda3tli4yarro)
- [elasticsearch-pull-request #123381 / pr-upgrade-part-3](https://gradle-enterprise.elastic.co/s/qdautvoayqyd2)
- [elasticsearch-pull-request #123192 / 8.19.12_part_3_bwc-snapshots](https://gradle-enterprise.elastic.co/s/5l524ywiylpci)
- [elasticsearch-pull-request #123107 / pr-upgrade-part-3](https://gradle-enterprise.elastic.co/s/zxozf3axblnpg)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:mixed-cluster:bcUpgradeTest" -Dtests.class="org.elasticsearch.xpack.esql.qa.mixed.FieldExtractorIT" -Dtests.method="testTsIndexConflictingTypes {null}" -Dtests.seed=7D2739051A67A4DD -Dtests.bwc.main.version=9.4.0-SNAPSHOT -Dtests.bwc.refspec.main=6850484510f41371d1e2ca75baa89f493b625dfb -Dtests.locale=jv-Latn-ID -Dtests.timezone=Europe/Stockholm -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.qa.mixed.FieldExtractorIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testTsIndexConflictingTypes%20%7Bnull%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
org.elasticsearch.client.WarningFailureException: method [PUT], host [http://[::1]:43289], URI [/metrics-long], status line [HTTP/1.1 200 OK]
Warnings: [Parameter [default_metric] is deprecated and will be removed in a future version]
:)
úacknowledged#shards_acknowledged#indexKmetrics-longû
```

**Issue Reasons:**
- [main] 4 failures in test testTsIndexConflictingTypes {null} (0.4% fail rate in 892 executions)
- [main] 2 failures in step pr-upgrade-part-3 (0.3% fail rate in 742 executions)
- [main] 3 failures in pipeline elasticsearch-pull-request (0.4% fail rate in 739 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 2: [CI] FieldExtractorIT testTsIndexConflictingTypes {NONE} failing

**Build Scans:**
- [elasticsearch-intake #35549 / bc-upgrade-tests-part3](https://gradle-enterprise.elastic.co/s/yoetd64daxdyg)
- [elasticsearch-pull-request #125989 / pr-upgrade-part-3](https://gradle-enterprise.elastic.co/s/4aznnof63dtfe)
- [elasticsearch-pull-request #125925 / pr-upgrade-part-3](https://gradle-enterprise.elastic.co/s/ehpb2ulhek7nc)
- [elasticsearch-pull-request #125656 / pr-upgrade-part-3](https://gradle-enterprise.elastic.co/s/miturgsmwxv2g)
- [elasticsearch-pull-request #125656 / pr-upgrade-part-3](https://gradle-enterprise.elastic.co/s/qfeh6ha36yqbc)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:mixed-cluster:bcUpgradeTest" -Dtests.class="org.elasticsearch.xpack.esql.qa.mixed.FieldExtractorIT" -Dtests.method="testTsIndexConflictingTypes {NONE}" -Dtests.seed=F51120B836105641 -Dtests.bwc.main.version=9.4.0-SNAPSHOT -Dtests.bwc.refspec.main=d29810df206d8afa320270485bf35f7c8085ead3 -Dtests.locale=to -Dtests.timezone=Asia/Qostanay -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.qa.mixed.FieldExtractorIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testTsIndexConflictingTypes%20%7BNONE%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
org.elasticsearch.client.WarningFailureException: method [PUT], host [http://[::1]:44177], URI [/metrics-long], status line [HTTP/1.1 200 OK]
Warnings: [Parameter [default_metric] is deprecated and will be removed in a future version]
{"acknowledged":true,"shards_acknowledged":true,"index":"metrics-long"}
```

**Issue Reasons:**
- [main] 5 failures in test testTsIndexConflictingTypes {NONE} (1.6% fail rate in 311 executions)
- [main] 4 failures in step pr-upgrade-part-3 (1.6% fail rate in 243 executions)
- [main] 3 failures in pipeline elasticsearch-pull-request (1.2% fail rate in 242 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 3: [CI] EsqlClientYamlIT test {p0=esql/40_tsdb/TS Command grouping on text field} failing

**Build Scans:**
- [elasticsearch-intake #35313 / 9.2.7_bwc-snapshots](https://gradle-enterprise.elastic.co/s/6pfqqiueehks6)
- [elasticsearch-pull-request #124738 / 9.3.2_part_3_bwc-snapshots](https://gradle-enterprise.elastic.co/s/fllim5e6327uk)
- [elasticsearch-pull-request #124654 / 9.2.7_part_3_bwc-snapshots](https://gradle-enterprise.elastic.co/s/p2vgcxuiii2xu)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:mixed-cluster:v9.2.7#yamlRestTest" -Dtests.class="org.elasticsearch.xpack.esql.qa.mixed.EsqlClientYamlIT" -Dtests.method="test {p0=esql/40_tsdb/TS Command grouping on text field}" -Dtests.seed=198121741846A9E4 -Dtests.bwc=true -Dtests.locale=fr-TN -Dtests.timezone=America/Atikokan -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.qa.mixed.EsqlClientYamlIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('test%20%7Bp0%3Desql%2F40_tsdb%2FTS%20Command%20grouping%20on%20text%20field%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: java.lang.AssertionError: indices.create[{index=test-text-field}]: got unexpected warning header [
	299 Elasticsearch-9.4.0-198aee2d55e01a23c83c465a6e535dc8c7f862d8 "Parameter [default_metric] is deprecated and will be removed in a future version"
]

```

**Issue Reasons:**
- [main] 3 failures in test test {p0=esql/40_tsdb/TS Command grouping on text field} (1.2% fail rate in 258 executions)
- [main] 2 failures in pipeline elasticsearch-pull-request (2.2% fail rate in 93 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 4: [CI] EsqlClientYamlIT test {p0=esql/40_tsdb/to_aggregate_metric_double with multi_values} failing

**Build Scans:**
- [elasticsearch-intake #35795 / part3](https://gradle-enterprise.elastic.co/s/p7ht25fv5ypl4)
- [elasticsearch-periodic-platform-support #11958 / opensuse-leap-15_platform-support-unix](https://gradle-enterprise.elastic.co/s/zxv4xz4xm5cls)
- [elasticsearch-intake #35752 / part3](https://gradle-enterprise.elastic.co/s/fhir5mhrhm6gm)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:multi-node:yamlRestTest" --tests "org.elasticsearch.xpack.esql.qa.multi_node.EsqlClientYamlIT.test {p0=esql/40_tsdb/to_aggregate_metric_double with multi_values}" -Dtests.seed=C64C857A9513B2DA -Dtests.locale=smn-Latn-FI -Dtests.timezone=Europe/Uzhgorod -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.qa.multi_node.EsqlClientYamlIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('test%20%7Bp0%3Desql%2F40_tsdb%2Fto_aggregate_metric_double%20with%20multi_values%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: java.lang.AssertionError: indices.create[{index=convert_test}]: got unexpected warning header [
	299 Elasticsearch-9.4.0-91195322f1e2db52c6c8bbb4db711362469fa097 "Parameter [default_metric] is deprecated and will be removed in a future version"
]

```

**Issue Reasons:**
- [main] 3 failures in test test {p0=esql/40_tsdb/to_aggregate_metric_double with multi_values} (1.5% fail rate in 200 executions)
- [main] 2 failures in step part3 (5.3% fail rate in 38 executions)
- [main] 2 failures in pipeline elasticsearch-intake (5.3% fail rate in 38 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 5: Investigate potential deprecation warning leak

Recently (https://github.com/elastic/elasticsearch/pull/141877), we deprecated the `default_metric` of the `aggregate_metric_double` field type. As a result, elasticsearch adds a deprecation warning to any request that is using this configuration.

We have adjusted tests to allow this warning. Unfortunately, it seems like these warnings some times leak to other requests too. For example, in the following logs we see an index create request that is not using an `aggregate_metric_double` at all is also returning the warning header in certain scenarios:

```
[2026-03-03T12:11:44,927][WARN ][o.e.c.RestClient         ][testTsIndexConflictingTypes] request [PUT http://[::1]:36637/metrics-long] returned 1 warnings: [299 Elasticsearch-9.4.0-bca3093cd0619c6871cfa5d1cad2e839fcfbdc9b "Parameter [default_metric] is deprecated and will be removed in a future version"]
[2026-03-03T12:11:44,933][ERROR][o.e.x.e.q.r.FieldExtractorTestCase][testTsIndexConflictingTypes] Received warning when creating index [metrics-long] with mapping [{metrics-long={mappings={_data_stream_timestamp={enabled=true}, properties={@timestamp={type=date}, metric={properties={name={time_series_dimension=true, type=keyword}, value={time_series_metric=gauge, type=long}}}}}}}]
```

Relates to: https://github.com/elastic/elasticsearch/issues/142964, https://github.com/elastic/elasticsearch/issues/142544, https://github.com/elastic/elasticsearch/issues/142477, https://github.com/elastic/elasticsearch/issues/142410

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `83e956212e79578d2ad74d14983ac7c84869bf3b`
**Instance ID:** `elastic__elasticsearch-144040`
**Language:** `Java`
