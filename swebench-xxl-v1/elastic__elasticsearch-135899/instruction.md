# Task

## Ascending sort with `missing _first` fails on datefields with missing values

**Elasticsearch version** (`bin/elasticsearch --version`): v8.1.0, v7.16.2 and at least v7.15.1

**Description of the problem including expected versus actual behavior**:

Indexing a document with a missing date time value, then ascending sorting it with `"missing": "_first"` results in `Field Year cannot be printed as the value -292275055 exceeds the maximum print width of 4` if it would be the only document returned, ie `size: 1`.

The formatter is trying to format the sentinel value of `-9223372036854775808`.

**Steps to reproduce**:
```
PUT test
{
  "mappings" : {
    "properties" : {
      "field1" : {
        "type" : "integer"
      },
      "dt" : {
        "type" : "date",
        "format" : "strict_date_time||strict_date_time_no_millis"
      }
    }
  }
}

POST _bulk
{"index":{"_index":"test","_id":"1"}}
{"field1": 1243, "dt": "2021-12-20T23:14:20+00:00"}
{"index":{"_index":"test","_id":"2"}}
{"field2": 4567}

GET test/_search
{
  "size": 1,
  "query": {
    "match_all": {}
  },
  "sort": [
    {
      "dt": {
        "missing": "_first",
        "order": "asc"
      }
    }
  ]
}
```

This is https://github.com/elastic/elasticsearch/issues/73763 with [`targetNumericType == NumericType.DATE`](https://github.com/elastic/elasticsearch/blob/master/server/src/main/java/org/elasticsearch/index/fielddata/fieldcomparator/LongValuesComparatorSource.java#L156)

Using `"missing": 0` works around the issue.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b664c448813a0fa6339e7c03b103d8eb89f769b5`
**Instance ID:** `elastic__elasticsearch-135899`
**Language:** `Java`
