# Task

## [CI] HierarchicalKMeansTests testFewDifferentValues failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #10829 / sles-15_platform-support-unix](https://gradle-enterprise.elastic.co/s/3zlepdmfqxsni)
- [elasticsearch-pull-request #94367 / part-1](https://gradle-enterprise.elastic.co/s/a2w2mhqoprxyw)
- [elasticsearch-periodic-platform-support #10775 / almalinux-8-aarch64_checkpart1_platform-support-arm](https://gradle-enterprise.elastic.co/s/iomfqo2laokoy)

**Reproduction Line:**
```
./gradlew ":server:test" --tests "org.elasticsearch.index.codec.vectors.cluster.HierarchicalKMeansTests.testFewDifferentValues" -Dtests.seed=E94D04864352A95D -Dtests.locale=zh-HK -Dtests.timezone=America/Atikokan -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.index.codec.vectors.cluster.HierarchicalKMeansTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testFewDifferentValues'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: null
```

**Issue Reasons:**
- [main] 3 failures in test testFewDifferentValues (0.4% fail rate in 827 executions)
- [main] 2 failures in pipeline elasticsearch-periodic-platform-support (20.0% fail rate in 10 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b7dbb2620b714932b323a137c165d26991418fc0`
**Instance ID:** `elastic__elasticsearch-135544`
**Language:** `Java`
