# Task

## [CI] TermsEnumTests testTermsEnumIPRandomized failing

**Build Scans:**
- [elasticsearch-periodic-platform-support #11890 / rocky-8_platform-support-unix](https://gradle-enterprise.elastic.co/s/typo65nn27nii)
- [elasticsearch-periodic-platform-support #11890 / rocky-8_platform-support-unix](https://gradle-enterprise.elastic.co/s/uhrb3okyv3wh4)
- [elasticsearch-pull-request #122282 / part-2](https://gradle-enterprise.elastic.co/s/fumuw7n4pu3do)
- [elasticsearch-pull-request #122274 / part-2](https://gradle-enterprise.elastic.co/s/wfxxp4zroxuro)
- [elasticsearch-pull-request #121874 / part-2](https://gradle-enterprise.elastic.co/s/ugs27jbcjnrsk)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:core:test" --tests "org.elasticsearch.xpack.core.termsenum.TermsEnumTests.testTermsEnumIPRandomized" -Dtests.seed=4ED6E49608803825 -Dtests.locale=en-NL -Dtests.timezone=America/Vancouver -Druntime.java=25
```

**Applicable branches:**
main

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.core.termsenum.TermsEnumTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testTermsEnumIPRandomized'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: expected 1 for prefix 0 but was 0, [] expected:<1> but was:<0>
```

**Issue Reasons:**
- [main] 2 consecutive failures in step rocky-8_platform-support-unix
- [main] 5 failures in test testTermsEnumIPRandomized (1.2% fail rate in 428 executions)
- [main] 2 failures in step rocky-8_platform-support-unix (50.0% fail rate in 4 executions)
- [main] 3 failures in step part-2 (1.1% fail rate in 274 executions)
- [main] 3 failures in pipeline elasticsearch-pull-request (1.1% fail rate in 269 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `5bfbd9c0a36f7ec9650122cca38287feec4fb7dd`
**Instance ID:** `elastic__elasticsearch-144308`
**Language:** `Java`
