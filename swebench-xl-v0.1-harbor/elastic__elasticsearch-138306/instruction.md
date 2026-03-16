# Task

## ES|QL: METADATA _source doesn't work with text fields

Testing on main:

When I create a basic template like this:
```
PUT _index_template/my-template
{
  "index_patterns": [
    "my-test"
  ],
  "priority": 100,
  "data_stream": {},
  "template": {
    "settings": {
      "sort": {
        "field": [
          "@timestamp"
        ],
        "order": [
          "asc"
        ]
      }
    },
    "mappings": {
      "dynamic": false,
      "properties": {
        "foo": {
          "type": "text"
        }
      }
    }
  }
}
```

and then index a doc:

```
POST my-test/_doc
{
    "@timestamp": "2026",
    "baz": "dasd"
}
```

Then querying with metadata _source doesn't return the source, just an empty object:

```
POST _query
{
  "query": """
    FROM my-test METADATA _source
    """
}
```

returns

```
{
  "took": 5,
  "is_partial": false,
  "documents_found": 1,
  "values_loaded": 2,
  "columns": [
    {
      "name": "@timestamp",
      "type": "date"
    },
    {
      "name": "foo",
      "type": "text"
    },
    {
      "name": "_source",
      "type": "_source"
    }
  ],
  "values": [
    [
      "2026-01-01T00:00:00.000Z",
      null,
      {}
    ]
  ]
}
```

I don't know what's going on, I tested around a bit and it looks like the fact that it's a text field is triggering this - if it's a keyword field it works as expected.

_source is returned completely normal when using `_search`

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `e6c5dcc087f13a3cfe738ab1531e4ab7ed39a0de`
**Instance ID:** `elastic__elasticsearch-138306`
**Language:** `Java`
