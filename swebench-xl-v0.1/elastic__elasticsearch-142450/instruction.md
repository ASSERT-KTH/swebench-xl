# Task

## transform creates empty index when query clause includes a runtime field.

### Elasticsearch Version

8.15.1

### Installed Plugins

_No response_

### Java Version

_bundled_

### OS Version

n/a

### Problem Description

The dest index is empty when you make a query that includes a runtime field.

```
    "query": {
      "bool": {
        "filter": [
          {
            "term": {
              "currency": "EUR"
            }
          },
          {
            "range": {
              "total_price_with_tax": {
                "gte": 1
              }
            }
          }
        ]
      }
    }
```

`total_price_with_tax` is a runtime field, which you can see in the repro step.
`POST _transform/_preview` does return a response, which I expect should be populated into the destination index.

Note that the issue was reported by a user who says it used to work in `8.6.1`


### Steps to Reproduce

1. add sample data  `sample eCommerce orders` by following this guide https://www.elastic.co/guide/en/kibana/8.15/get-started.html#gs-get-data-into-kibana

2. then run this script in Kibana.


```
# this will reproduce the issue.
PUT _transform/ecommerce-customer-transform-runtime-within-query
{
  "source": {
    "index": [
      "kibana_sample_data_ecommerce"
    ],
    "runtime_mappings": {
      "total_price_with_tax": {
        "type": "double",
        "script": {
          "source": """
            if (doc.containsKey('products.taxful_price') && doc['products.taxful_price'].size() > 0) {
              double total_price = 0;
              for (int i = 0; i < doc['products.taxful_price'].size(); i++) {
                total_price += doc['products.taxful_price'][i];
              }
              emit(total_price);
            } else {
              emit(0.0);
            }
          """
        }
      }
    },
    "query": {
      "bool": {
        "filter": [
          {
            "term": {
              "currency": "EUR"
            }
          },
          {
            "range": {
              "total_price_with_tax": {
                "gte": 1
              }
            }
          }
        ]
      }
    }
  },
  "pivot": {
    "group_by": {
      "customer_id": {
        "terms": {
          "field": "customer_id"
        }
      }
    },
    "aggregations": {
      "total_quantity.sum": {
        "sum": {
          "field": "total_quantity"
        }
      },
      "taxless_total_price.sum": {
        "sum": {
          "field": "taxless_total_price"
        }
      },
      "total_quantity.max": {
        "max": {
          "field": "total_quantity"
        }
      },
      "order_id.cardinality": {
        "cardinality": {
          "field": "order_id"
        }
      },
      "total_price_with_tax.sum": {
        "sum": {
          "field": "total_price_with_tax"
        }
      }
    }
  },
  "dest": {
    "index": "ecommerce-customers-runtime-within-query"
  },
  "retention_policy": {
    "time": {
      "field": "order_date",
      "max_age": "60d"
    }
  }
}


POST _transform/ecommerce-customer-transform-runtime-within-query/_start
GET ecommerce-customers-runtime-within-query/_search

POST _transform/_preview
{
  "source": {
    "index": "kibana_sample_data_ecommerce",
    "runtime_mappings": {
      "total_price_with_tax": {
        "type": "double",
        "script": {
          "source": """
            if (doc.containsKey('products.taxful_price') && doc['products.taxful_price'].size() > 0) {
              double total_price = 0;
              for (int i = 0; i < doc['products.taxful_price'].size(); i++) {
                total_price += doc['products.taxful_price'][i];
              }
              emit(total_price);
            } else {
              emit(0.0);
            }
          """
        }
      }
    },
    "query": {
      "bool": {
        "filter": [
          {
            "term": {
              "currency": "EUR"
            }
          },
          {
            "range": {
              "total_price_with_tax": {
                "gte": 1
              }
            }
          }
        ]
      }
    }
  },
  "pivot": {
    "group_by": {
      "customer_id": {
        "terms": {
          "field": "customer_id"
        }
      }
    },
    "aggregations": {
      "total_quantity.sum": {
        "sum": {
          "field": "total_quantity"
        }
      },
      "taxless_total_price.sum": {
        "sum": {
          "field": "taxless_total_price"
        }
      },
      "total_quantity.max": {
        "max": {
          "field": "total_quantity"
        }
      },
      "order_id.cardinality": {
        "cardinality": {
          "field": "order_id"
        }
      },
      "total_price_with_tax.sum": {
        "sum": {
          "field": "total_price_with_tax"
        }
      }
    }
  }
}


# This is for comparison so you can see that the index is not empty when runtime is not used in the query condition.

PUT _transform/ecommerce-customer-transform-no-runtime-within-query
{
  "source": {
    "index": [
      "kibana_sample_data_ecommerce"
    ],
    "runtime_mappings": {
      "total_price_with_tax": {
        "type": "double",
        "script": {
          "source": """
            if (doc.containsKey('products.taxful_price') && doc['products.taxful_price'].size() > 0) {
              double total_price = 0;
              for (int i = 0; i < doc['products.taxful_price'].size(); i++) {
                total_price += doc['products.taxful_price'][i];
              }
              emit(total_price);
            } else {
              emit(0.0);
            }
          """
        }
      }
    },
    "query": {
      "bool": {
        "filter": [
          {
            "term": {
              "currency": "EUR"
            }
          }
        ]
      }
    }
  },
  "pivot": {
    "group_by": {
      "customer_id": {
        "terms": {
          "field": "customer_id"
        }
      }
    },
    "aggregations": {
      "total_quantity.sum": {
        "sum": {
          "field": "total_quantity"
        }
      },
      "taxless_total_price.sum": {
        "sum": {
          "field": "taxless_total_price"
        }
      },
      "total_quantity.max": {
        "max": {
          "field": "total_quantity"
        }
      },
      "order_id.cardinality": {
        "cardinality": {
          "field": "order_id"
        }
      },
      "total_price_with_tax.sum": {
        "sum": {
          "field": "total_price_with_tax"
        }
      }
    }
  },
  "dest": {
    "index": "ecommerce-customers-no-runtime-within-query"
  },
  "retention_policy": {
    "time": {
      "field": "order_date",
      "max_age": "60d"
    }
  }
}

POST _transform/ecommerce-customer-transform-no-runtime-within-query/_start


GET ecommerce-customers-no-runtime-within-query/_search
```

### Logs (if relevant)

_No response_

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b650f355ce42ff8e48687b61088c93a9fa35d6eb`
**Instance ID:** `elastic__elasticsearch-142450`
**Language:** `Java`
