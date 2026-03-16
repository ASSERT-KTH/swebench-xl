# Task

## [CI] WildcardLikeTests testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with keyword} failing | [CI] WildcardLikeTests testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with text} failing

### Issue 1: [CI] WildcardLikeTests testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with keyword} failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #8496 / ubuntu-2004-aarch64_checkpart3_platform-support-arm](https://gradle-enterprise.elastic.co/s/6ebfbnyn4f6so)
- [elasticsearch-pull-request #73158 / part-3-fips](https://gradle-enterprise.elastic.co/s/unrn27cw7ik34)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:test" --tests "org.elasticsearch.xpack.esql.expression.function.scalar.string.WildcardLikeTests.testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with keyword}" -Dtests.seed=AED21E70A1D0CA84 -Dtests.locale=qu-Latn-PE -Dtests.timezone=America/La_Paz -Druntime.java=24
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.expression.function.scalar.string.WildcardLikeTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!(testEvaluateInManyThreads%20%7BTestCase%3D100%20random%20code%20points%20matches%20self%20case%20insensitive%20with%20keyword%7D),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.IllegalArgumentException: expected '"' at position 195
```

**Issue Reasons:**
- [main] 2 failures in test testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with keyword} (8.3% fail rate in 24 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

### Issue 2: [CI] WildcardLikeTests testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with text} failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #8496 / ubuntu-2004-aarch64_checkpart3_platform-support-arm](https://gradle-enterprise.elastic.co/s/6ebfbnyn4f6so)
- [elasticsearch-pull-request #73158 / part-3-fips](https://gradle-enterprise.elastic.co/s/unrn27cw7ik34)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:esql:test" --tests "org.elasticsearch.xpack.esql.expression.function.scalar.string.WildcardLikeTests.testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with keyword}" -Dtests.seed=AED21E70A1D0CA84 -Dtests.locale=qu-Latn-PE -Dtests.timezone=America/La_Paz -Druntime.java=24
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.esql.expression.function.scalar.string.WildcardLikeTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!(testEvaluateInManyThreads%20%7BTestCase%3D100%20random%20code%20points%20matches%20self%20case%20insensitive%20with%20text%7D),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.IllegalArgumentException: expected '"' at position 195
```

**Issue Reasons:**
- [main] 2 failures in test testEvaluateInManyThreads {TestCase=100 random code points matches self case insensitive with text} (8.3% fail rate in 24 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `28f1e59f56e1b199fbb0bb29b41359810cf8e6c1`
**Instance ID:** `elastic__elasticsearch-128750`
**Language:** `Java`
