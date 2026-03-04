# Task

## [CI] IndexSortUpgradeIT testIndexSortForNumericTypes {upgradedNodes=1} failing | [CI] IndexSortUpgradeIT testIndexSortForNumericTypes {upgradedNodes=2} failing

### Issue 1: [CI] IndexSortUpgradeIT testIndexSortForNumericTypes {upgradedNodes=1} failing

**Build Scans:**
- [elasticsearch-periodic #11545 / 9.0.8_bwc](https://gradle-enterprise.elastic.co/s/i7oivpy32laec)
- [elasticsearch-pull-request #108024 / 8.19.9_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/all5yqnprncrc)
- [elasticsearch-pull-request #108024 / 9.1.9_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/lovrvuy4emmyi)
- [elasticsearch-pull-request #108024 / pr-upgrade-part-6](https://gradle-enterprise.elastic.co/s/uc54wq6pjcqii)
- [elasticsearch-pull-request #108024 / 9.2.3_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/mlvc3t3oiasyy)
- [elasticsearch-pull-request #107999 / 9.3.0_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/tn2hvsx4dtqt6)

**Reproduction Line:**
```
./gradlew ":qa:rolling-upgrade:v9.0.8#bwcTest" -Dtests.class="org.elasticsearch.upgrades.IndexSortUpgradeIT" -Dtests.method="testIndexSortForNumericTypes {upgradedNodes=1}" -Dtests.seed=68E68168E2A2B4AD -Dtests.bwc=true -Dtests.locale=yrl -Dtests.timezone=Etc/GMT+9 -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.upgrades.IndexSortUpgradeIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testIndexSortForNumericTypes%20%7BupgradedNodes%3D1%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
org.elasticsearch.client.ResponseException: method [GET], host [http://[::1]:40161], URI [/index_int/_search], status line [HTTP/1.1 400 Bad Request]
{"error":{"root_cause":[],"type":"search_phase_execution_exception","reason":"","phase":"fetch","grouped":true,"failed_shards":[],"caused_by":{"type":"illegal_argument_exception","reason":"Can't sort on field [int_field]; the field has incompatible sort types: [INT] and [LONG] across shards!"}},"status":400}
```

**Issue Reasons:**
- [main] 6 failures in test testIndexSortForNumericTypes {upgradedNodes=1} (0.7% fail rate in 910 executions)
- [main] 2 failures in pipeline elasticsearch-pull-request (1.4% fail rate in 139 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 2: [CI] IndexSortUpgradeIT testIndexSortForNumericTypes {upgradedNodes=2} failing

**Build Scans:**
- [elasticsearch-periodic #11545 / 9.0.8_bwc](https://gradle-enterprise.elastic.co/s/i7oivpy32laec)
- [elasticsearch-pull-request #108024 / 8.19.9_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/all5yqnprncrc)
- [elasticsearch-pull-request #108024 / 9.1.9_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/lovrvuy4emmyi)
- [elasticsearch-pull-request #108024 / pr-upgrade-part-6](https://gradle-enterprise.elastic.co/s/uc54wq6pjcqii)
- [elasticsearch-pull-request #108024 / 9.2.3_part_6_bwc-snapshots](https://gradle-enterprise.elastic.co/s/mlvc3t3oiasyy)

**Reproduction Line:**
```
./gradlew ":qa:rolling-upgrade:v9.0.8#bwcTest" -Dtests.class="org.elasticsearch.upgrades.IndexSortUpgradeIT" -Dtests.method="testIndexSortForNumericTypes {upgradedNodes=1}" -Dtests.seed=68E68168E2A2B4AD -Dtests.bwc=true -Dtests.locale=yrl -Dtests.timezone=Etc/GMT+9 -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.upgrades.IndexSortUpgradeIT),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testIndexSortForNumericTypes%20%7BupgradedNodes%3D2%7D'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
org.elasticsearch.client.ResponseException: method [GET], host [http://[::1]:40161], URI [/index_int/_search], status line [HTTP/1.1 400 Bad Request]
{"error":{"root_cause":[],"type":"search_phase_execution_exception","reason":"","phase":"fetch","grouped":true,"failed_shards":[],"caused_by":{"type":"illegal_argument_exception","reason":"Can't sort on field [int_field]; the field has incompatible sort types: [INT] and [LONG] across shards!"}},"status":400}
```

**Issue Reasons:**
- [main] 5 failures in test testIndexSortForNumericTypes {upgradedNodes=2} (0.6% fail rate in 909 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `a0ee98ca7580948520308aa9486ae9b09f7b94d2`
**Instance ID:** `elastic__elasticsearch-139293`
**Language:** `Java`
