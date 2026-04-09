# Task

## [CI] CliApiKeyIT testCliConnectionWithInvalidApiKey failing | [CI] CliApiKeyIT testCliConnectionWithInvalidApiKey failing

### Issue 1: [CI] CliApiKeyIT testCliConnectionWithInvalidApiKey failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #11926 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/vinal7afy2pz2)
- [elasticsearch-periodic-platform-support #11926 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/vinal7afy2pz2)
- [elasticsearch-periodic-platform-support #11926 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/6gtul7pkj34yy)
- [elasticsearch-periodic-platform-support #11926 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/6gtul7pkj34yy)
- [elasticsearch-periodic-platform-support #11926 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/zqmawq36m67lo)
- [elasticsearch-periodic-platform-support #11926 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/zqmawq36m67lo)
- [elasticsearch-periodic-platform-support #11926 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/gdrlh6wro7ahm)
- [elasticsearch-periodic-platform-support #11926 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/gdrlh6wro7ahm)
- [elasticsearch-periodic-java-ea #193 / checkpart4_windows-2025](https://gradle-enterprise.elastic.co/s/jptlh2tnkat6s)
- [elasticsearch-periodic-java-ea #193 / checkpart4_windows-2025](https://gradle-enterprise.elastic.co/s/jptlh2tnkat6s)

**Reproduction Line:**
```
gradlew ":x-pack:plugin:sql:qa:server:security:with-ssl:javaRestTest" --tests "org.elasticsearch.xpack.sql.qa.security.CliApiKeyIT.testCliConnectionWithInvalidApiKey" -Dtests.seed=D9FA802C49375459 -Dtests.locale=bs-Latn -Dtests.timezone=Canada/Central -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.sql.qa.security.CliApiKeyIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testCliConnectionWithInvalidApiKey'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: unconsumed lines
Expected: an empty collection
     but: <[	at org.elasticsearch.xpack.sql.client.JreHttpUrlConnection.request(JreHttpUrlConnection.java:190), 	at org.elasticsearch.xpack.sql.client.HttpClient.lambda$post$1(HttpClient.java:169), 	at org.elasticsearch.xpack.sql.client.JreHttpUrlConnection.http(JreHttpUrlConnection.java:82), 	at org.elasticsearch.xpack.sql.client.HttpClient.lambda$post$2(HttpClient.java:165), 	at java.base/java.security.AccessController.doPrivileged(AccessController.java:74), 	at org.elasticsearch.xpack.sql.client.HttpClient.post(HttpClient.java:164), 	at org.elasticsearch.xpack.sql.client.HttpClient.query(HttpClient.java:131), 	at org.elasticsearch.xpack.sql.client.HttpClient.basicQuery(HttpClient.java:127), 	at org.elasticsearch.xpack.sql.cli.command.ServerQueryCliCommand.doHandle(ServerQueryCliCommand.java:30), 	at org.elasticsearch.xpack.sql.cli.command.AbstractServerCliCommand.handle(AbstractServerCliCommand.java:18), 	at 
[truncated]
```

**Issue Reasons:**
- [main] 6 consecutive failures in test testCliConnectionWithInvalidApiKey
- [main] 8 consecutive failures in step windows-2022_checkpart4_platform-support-windows
- [main] 8 consecutive failures in step windows-2025_checkpart4_platform-support-windows
- [main] 2 consecutive failures in step checkpart4_windows-2025
- [main] 36 failures in test testCliConnectionWithInvalidApiKey (4.1% fail rate in 870 executions)
- [main] 8 failures in step windows-2022_checkpart4_platform-support-windows (100.0% fail rate in 8 executions)
- [main] 8 failures in step windows-2025_checkpart4_platform-support-windows (100.0% fail rate in 8 executions)
- [main] 2 failures in step checkpart4_windows-2025 (100.0% fail rate in 2 executions)
- [main] 4 failures in pipeline elasticsearch-periodic-platform-support (100.0% fail rate in 4 executions)
- [main] 2 failures in pipeline elasticsearch-periodic-java-ea (66.7% fail rate in 3 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 2: [CI] CliApiKeyIT testCliConnectionWithInvalidApiKey failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #11930 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/yqc6joe2mfa7k)
- [elasticsearch-periodic-platform-support #11930 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/yqc6joe2mfa7k)
- [elasticsearch-periodic-platform-support #11930 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/lwygks52e5eao)
- [elasticsearch-periodic-platform-support #11930 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/lwygks52e5eao)
- [elasticsearch-periodic-platform-support #11930 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/4shbxk43fviz2)
- [elasticsearch-periodic-platform-support #11930 / windows-2022_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/4shbxk43fviz2)
- [elasticsearch-periodic-platform-support #11930 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/ipyeutazjbm6c)
- [elasticsearch-periodic-platform-support #11930 / windows-2025_checkpart4_platform-support-windows](https://gradle-enterprise.elastic.co/s/ipyeutazjbm6c)
- [elasticsearch-periodic-java-ea #194 / checkpart4_windows-2025](https://gradle-enterprise.elastic.co/s/qd3ko7juqol3q)
- [elasticsearch-periodic-java-ea #194 / checkpart4_windows-2025](https://gradle-enterprise.elastic.co/s/qd3ko7juqol3q)

**Reproduction Line:**
```
gradlew ":x-pack:plugin:sql:qa:server:security:with-ssl:javaRestTest" --tests "org.elasticsearch.xpack.sql.qa.security.CliApiKeyIT.testCliConnectionWithInvalidApiKey" -Dtests.seed=9E08F2FC06F254F8 -Dtests.locale=fr-HT -Dtests.timezone=Etc/GMT-3 -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.sql.qa.security.CliApiKeyIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testCliConnectionWithInvalidApiKey'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: unconsumed lines
Expected: an empty collection
     but: <[	at org.elasticsearch.xpack.sql.client.JreHttpUrlConnection.request(JreHttpUrlConnection.java:190), 	at org.elasticsearch.xpack.sql.client.HttpClient.lambda$post$1(HttpClient.java:169), 	at org.elasticsearch.xpack.sql.client.HttpClient.lambda$post$2(HttpClient.java:165), 	at java.base/java.security.AccessController.doPrivileged(AccessController.java:74), 	at org.elasticsearch.xpack.sql.client.HttpClient.post(HttpClient.java:164), 	at org.elasticsearch.xpack.sql.client.HttpClient.query(HttpClient.java:131), 	at org.elasticsearch.xpack.sql.client.HttpClient.basicQuery(HttpClient.java:127), 	at org.elasticsearch.xpack.sql.cli.command.ServerQueryCliCommand.doHandle(ServerQueryCliCommand.java:30), 	at org.elasticsearch.xpack.sql.cli.command.AbstractServerCliCommand.handle(AbstractServerCliCommand.java:18), 	at org.elasticsearch.xpack.sql.cli.command.CliCommands.handle(CliCommands.java:28), 	at org.elastic
[truncated]
```

**Issue Reasons:**
- [main] 2 consecutive failures in test testCliConnectionWithInvalidApiKey
- [main] 4 consecutive failures in step windows-2022_checkpart4_platform-support-windows
- [main] 4 consecutive failures in step windows-2025_checkpart4_platform-support-windows
- [main] 3 consecutive failures in step checkpart4_windows-2025
- [main] 22 failures in test testCliConnectionWithInvalidApiKey (2.3% fail rate in 971 executions)
- [main] 4 failures in step windows-2022_checkpart4_platform-support-windows (100.0% fail rate in 4 executions)
- [main] 4 failures in step windows-2025_checkpart4_platform-support-windows (100.0% fail rate in 4 executions)
- [main] 3 failures in step checkpart4_windows-2025 (100.0% fail rate in 3 executions)
- [main] 2 failures in pipeline elasticsearch-periodic-platform-support (100.0% fail rate in 2 executions)
- [main] 2 failures in pipeline elasticsearch-periodic-java-ea (100.0% fail rate in 2 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `cb95c77dbb0114c826ed6257068ac91eb334e680`
**Instance ID:** `elastic__elasticsearch-143408`
**Language:** `Java`
