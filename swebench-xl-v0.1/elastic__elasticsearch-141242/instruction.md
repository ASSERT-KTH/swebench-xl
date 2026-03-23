# Task

## [CI] MultiClusterSpecIT test {csv-spec:string.Url_encode_component tests with table reads} failing | [CI] EsqlSpecIT test {csv-spec:string.Url_encode_component tests with table reads} failing | [CI] GenerativeForkIT test {csv-spec:string.Url_encode_component tests with table reads} failing

### Issue 1: [CI] MultiClusterSpecIT test {csv-spec:string.Url_encode_component tests with table reads} failing

**Build Scans:**
- [elasticsearch-intake #33226 / 9.2.5_bwc-snapshots](https://gradle-enterprise.elastic.co/s/prkgkyhcy2sjc)
- [elasticsearch-intake #33197 / 9.4.0_bwc-snapshots](https://gradle-enterprise.elastic.co/s/kxjwpsf4mwpgi)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:multi-clusters:v9.2.5#newToOld" -Dtests.class="org.elasticsearch.xpack.esql.ccq.MultiClusterSpecIT" -Dtests.method="test {csv-spec:string.Url_encode_component tests with table reads}" -Dtests.seed=54BCB869082866E0 -Dtests.bwc=true -Dtests.locale=en-LR -Dtests.timezone=Pacific/Easter -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.ccq.MultiClusterSpecIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('test%20%7Bcsv-spec%3Astring.Url_encode_component%20tests%20with%20table%20reads%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: 
Data mismatch:
row 1 column 1:a list containing
row 1 column 1:0: expected "J.%20R.%20R.%20Tolkien" but was "Fyodor%20Dostoevsky"
row 1 column 2:a list containing
row 1 column 2:0: expected "Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth" but was "The%20brothers%20Karamazov"
Actual:
book_no:keyword | author_encoded:keyword | title_encoded:keyword
1211            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov
1463            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov

Expected:
book_no:keyword | author_encoded:keyword | title_encoded:keyword
1211            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov
1463            | J.%20R.%20R.%20Tolkien | Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth

```

**Issue Reasons:**
- [main] 2 failures in test test {csv-spec:string.Url_encode_component tests with table reads} (0.4% fail rate in 558 executions)
- [main] 2 failures in pipeline elasticsearch-intake (15.4% fail rate in 13 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 2: [CI] EsqlSpecIT test {csv-spec:string.Url_encode_component tests with table reads} failing

**Build Scans:**
- [elasticsearch-intake #33247 / part3](https://gradle-enterprise.elastic.co/s/tum5nvo4tmhqa)
- [elasticsearch-periodic-java-ea #144 / checkpart3_ubuntu-2404](https://gradle-enterprise.elastic.co/s/y424xvkfglngo)
- [elasticsearch-pull-request #114126 / part-3](https://gradle-enterprise.elastic.co/s/d7n37ybzxamua)
- [elasticsearch-pull-request #114047 / part-3](https://gradle-enterprise.elastic.co/s/jkskz46ipoa2u)
- [elasticsearch-pull-request #114047 / part-3](https://gradle-enterprise.elastic.co/s/vayzyyu75boxw)
- [elasticsearch-pull-request #114047 / part-3](https://gradle-enterprise.elastic.co/s/zm53e4gdhzrvk)
- [elasticsearch-intake #33201 / part3](https://gradle-enterprise.elastic.co/s/iycz5uybxtuwg)
- [elasticsearch-pull-request #114015 / part-3](https://gradle-enterprise.elastic.co/s/3mzptduy3hvja)
- [elasticsearch-pull-request #113977 / part-3](https://gradle-enterprise.elastic.co/s/sgtux7k3n34oc)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:single-node:javaRestTest" --tests "org.elasticsearch.xpack.esql.qa.single_node.EsqlSpecIT" -Dtests.method="test {csv-spec:string.Url_encode_component tests with table reads}" -Dtests.seed=7B21F0F6F13DC72A -Dtests.locale=az-AZ -Dtests.timezone=Canada/Atlantic -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.qa.single_node.EsqlSpecIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('test%20%7Bcsv-spec%3Astring.Url_encode_component%20tests%20with%20table%20reads%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: 
Data mismatch:
row 1 column 1:a list containing
row 1 column 1:0: expected "J.%20R.%20R.%20Tolkien" but was "Fyodor%20Dostoevsky"
row 1 column 2:a list containing
row 1 column 2:0: expected "Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth" but was "The%20brothers%20Karamazov"
Actual:
book_no:keyword | author_encoded:keyword | title_encoded:keyword
1211            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov
1463            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov

Expected:
book_no:keyword | author_encoded:keyword | title_encoded:keyword
1211            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov
1463            | J.%20R.%20R.%20Tolkien | Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth

```

**Issue Reasons:**
- [main] 9 failures in test test {csv-spec:string.Url_encode_component tests with table reads} (3.9% fail rate in 228 executions)
- [main] 2 failures in step part3 (7.1% fail rate in 28 executions)
- [main] 6 failures in step part-3 (3.8% fail rate in 158 executions)
- [main] 2 failures in pipeline elasticsearch-intake (7.1% fail rate in 28 executions)
- [main] 4 failures in pipeline elasticsearch-pull-request (2.6% fail rate in 153 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 3: [CI] GenerativeForkIT test {csv-spec:string.Url_encode_component tests with table reads} failing

**Build Scans:**
- [elasticsearch-intake #33381 / part3](https://gradle-enterprise.elastic.co/s/nv7mzok4ov2zi)
- [elasticsearch-pull-request #114755 / part-3](https://gradle-enterprise.elastic.co/s/6rirslj3qwpay)
- [elasticsearch-pull-request #114727 / part-3](https://gradle-enterprise.elastic.co/s/ji4m2hc2lcasu)
- [elasticsearch-pull-request #114612 / part-3](https://gradle-enterprise.elastic.co/s/tovd2jixv6jva)
- [elasticsearch-pull-request #114412 / part-3](https://gradle-enterprise.elastic.co/s/zw6a6qpeuu3qk)
- [elasticsearch-pull-request #114398 / part-3](https://gradle-enterprise.elastic.co/s/ul3rr5iohu3tw)
- [elasticsearch-pull-request #114396 / part-3](https://gradle-enterprise.elastic.co/s/henetfxcva2m6)
- [elasticsearch-pull-request #114394 / part-3](https://gradle-enterprise.elastic.co/s/b5jax2rmlxjxk)
- [elasticsearch-pull-request #114184 / part-3](https://gradle-enterprise.elastic.co/s/2dhndvdnifgbg)
- [elasticsearch-pull-request #114064 / part-3-fips](https://gradle-enterprise.elastic.co/s/bnuptrkynlpg6)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:qa:server:single-node:javaRestTest" --tests "org.elasticsearch.xpack.esql.qa.single_node.GenerativeForkIT" -Dtests.method="test {csv-spec:string.Url_encode_component tests with table reads}" -Dtests.seed=D98C1FA883AFA19B -Dtests.locale=naq-NA -Dtests.timezone=Europe/Jersey -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.qa.single_node.GenerativeForkIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('test%20%7Bcsv-spec%3Astring.Url_encode_component%20tests%20with%20table%20reads%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: 
Data mismatch:
row 0 column 1:a list containing
row 0 column 1:0: expected "Fyodor%20Dostoevsky" but was "J.%20R.%20R.%20Tolkien"
row 0 column 2:a list containing
row 0 column 2:0: expected "The%20brothers%20Karamazov" but was "Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth"
Actual:
book_no:keyword | author_encoded:keyword | title_encoded:keyword
1211            | J.%20R.%20R.%20Tolkien | Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth
1463            | J.%20R.%20R.%20Tolkien | Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth

Expected:
book_no:keyword | author_encoded:keyword | title_encoded:keyword
1211            | Fyodor%20Dostoevsky    | The%20brothers%20Karamazov
1463            | J.%20R.%20R.%20Tolkien | Realms%20of%20Tolkien%3A%20Images%20of%20Middle-earth

```

**Issue Reasons:**
- [main] 12 failures in test test {csv-spec:string.Url_encode_component tests with table reads} (1.8% fail rate in 662 executions)
- [main] 10 failures in step part-3 (2.3% fail rate in 431 executions)
- [main] 11 failures in pipeline elasticsearch-pull-request (2.6% fail rate in 426 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `130044bc5c3ee79125dc6cd508c72d0cee584a43`
**Instance ID:** `elastic__elasticsearch-141242`
**Language:** `Java`
