# Task

## [CI] KqlParserBooleanQueryTests testParseAndQuery failing

**Build Scans:**
- [elasticsearch-intake #28174 / part3](https://gradle-enterprise.elastic.co/s/3mltxe67el4g2)
- [elasticsearch-periodic #10525 / openjdk23_checkpart3_java-matrix](https://gradle-enterprise.elastic.co/s/glgq2xwithyta)
- [elasticsearch-periodic #10507 / openjdk21_checkpart3_java-fips-matrix](https://gradle-enterprise.elastic.co/s/iwab2ks6e6gdk)
- [elasticsearch-periodic #10495 / encryption-at-rest](https://gradle-enterprise.elastic.co/s/jtqjdxvuzsmra)
- [elasticsearch-periodic-platform-support #10485 / debian-12_platform-support-unix](https://gradle-enterprise.elastic.co/s/dha3cgubszpvc)
- [elasticsearch-periodic-platform-support #10479 / rocky-9_platform-support-unix](https://gradle-enterprise.elastic.co/s/c5mdginh6tj64)
- [elasticsearch-periodic-platform-support #10479 / windows-2025_checkpart3_platform-support-windows](https://gradle-enterprise.elastic.co/s/366klodvcq7cw)
- [elasticsearch-periodic #10476 / openjdk21_checkpart3_java-fips-matrix](https://gradle-enterprise.elastic.co/s/gytikjrgpobf2)
- [elasticsearch-periodic-platform-support #10467 / ubuntu-2404-aarch64_checkpart3_platform-support-arm](https://gradle-enterprise.elastic.co/s/wxuydsin4ajcg)
- [elasticsearch-periodic #10470 / openjdk21_checkpart3_java-matrix](https://gradle-enterprise.elastic.co/s/bqt37fc4rh4ko)

**Reproduction Line:**
```
./gradlew ":x-pack:plugin:kql:test" --tests "org.elasticsearch.xpack.kql.parser.KqlParserBooleanQueryTests.testParseAndQuery" -Dtests.seed=9D65876AC0826FDE -Dtests.locale=uk-UA -Dtests.timezone=Europe/Luxembourg -Druntime.java=24
```

**Applicable branches:**
9.0

**Reproduces locally?:**
N/A

**Failure History:**
[See dashboard](https://es-delivery-stats.elastic.dev/app/dashboards#/view/dcec9e60-72ac-11ee-8f39-55975ded9e63?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d%2Fd,to:now))&_a=(controlGroupState:(initialChildControlState:('0c0c9cb8-ccd2-45c6-9b13-96bac4abc542':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:task.keyword,order:0,selectedOptions:!(),title:'GradleTask',type:optionsListControl),'4e6ad9d6-6fdc-4fcc-bf1a-aa6ca79e0850':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:className.keyword,order:1,selectedOptions:!(org.elasticsearch.xpack.kql.parser.KqlParserBooleanQueryTests),title:'Suite',type:optionsListControl),'144933da-5c1b-4257-a969-7f43455a7901':(dataViewId:fbbdc689-be23-4b3d-8057-aa402e9ed0c5,fieldName:name.keyword,order:2,selectedOptions:!('testParseAndQuery'),title:'Test',type:optionsListControl)))))

**Failure Message:**
```
java.lang.AssertionError: 
Expected: an instance of org.elasticsearch.index.query.BoolQueryBuilder
     but: <{
  "match" : {
    "mapped_string" : {
      "query" : "NOT anD NOT"
    }
  }
}> is a org.elasticsearch.index.query.MatchQueryBuilder
```

**Issue Reasons:**
- [9.0] 24 failures in test testParseAndQuery (4.6% fail rate in 522 executions)
- [9.0] 3 failures in step release-tests (15.0% fail rate in 20 executions)
- [9.0] 2 failures in step sles-15_platform-support-unix (10.0% fail rate in 20 executions)
- [9.0] 2 failures in step debian-12_platform-support-unix (10.5% fail rate in 19 executions)
- [9.0] 2 failures in step rocky-9_platform-support-unix (10.0% fail rate in 20 executions)
- [9.0] 2 failures in step openjdk21_checkpart3_java-fips-matrix (10.5% fail rate in 19 executions)
- [9.0] 2 failures in step openjdk23_checkpart3_java-matrix (10.5% fail rate in 19 executions)
- [9.0] 9 failures in pipeline elasticsearch-periodic (45.0% fail rate in 20 executions)
- [9.0] 8 failures in pipeline elasticsearch-periodic-platform-support (40.0% fail rate in 20 executions)

**Note:**
This issue was created using new test triage automation. Please report issues or feedback to es-delivery.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `53d644fd7336e2fd7728b8a8b4b6198934a5501c`
**Instance ID:** `elastic__elasticsearch-134877`
**Language:** `Java`
