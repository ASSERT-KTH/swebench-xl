# Task

## [CI] ImmediateLocalSupplierTests testEqualsAndHashcode failing | [CI] BasicPageTests testEqualityAndHashCode failing

### Issue 1: [CI] ImmediateLocalSupplierTests testEqualsAndHashcode failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #10966 / rocky-9_platform-support-unix](https://gradle-enterprise.elastic.co/s/urf6754kiafpu)
- [elasticsearch-pull-request #96588 / part-3](https://gradle-enterprise.elastic.co/s/r7yaoniy4aq6s)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:test" --tests "org.elasticsearch.xpack.esql.plan.logical.local.ImmediateLocalSupplierTests.testEqualsAndHashcode" -Dtests.seed=A4AA443A36B3BCFB -Dtests.locale=ar-KW -Dtests.timezone=America/New_York -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.plan.logical.local.ImmediateLocalSupplierTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testEqualsAndHashcode'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: ImmediateLocalSupplier mutation should not be equal to original
Expected: not <Page{blocks=[IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]]]}>
     but: was <Page{blocks=[IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVector[positions=0, values=[]]], IntVectorBlock[vector=IntArrayVec
[truncated]
```

**Issue Reasons:**
- [main] 2 failures in test testEqualsAndHashcode (0.8% fail rate in 251 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 2: [CI] BasicPageTests testEqualityAndHashCode failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #10973 / rhel-8_platform-support-unix](https://gradle-enterprise.elastic.co/s/skviiltxjvwmk)
- [elasticsearch-pull-request #96538 / part-3](https://gradle-enterprise.elastic.co/s/bp6cn7gkcbx7s)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:compute:test" --tests "org.elasticsearch.compute.data.BasicPageTests.testEqualityAndHashCode" -Dtests.seed=4BEFCA527ED9966 -Dtests.locale=so-SO -Dtests.timezone=Hongkong -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.compute.data.BasicPageTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testEqualityAndHashCode'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.IllegalArgumentException: blocks is empty
```

**Issue Reasons:**
- [main] 2 failures in test testEqualityAndHashCode (0.7% fail rate in 268 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `f74e8e460c86a54fa051d8cd52d44fbb1c78ea99`
**Instance ID:** `elastic__elasticsearch-136266`
**Language:** `Java`
