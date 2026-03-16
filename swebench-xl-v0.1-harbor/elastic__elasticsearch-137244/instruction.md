# Task

## [ML] Old trained model deployment got deleted unexpectedly after a new one is added through inference API

**Version**:
9.2.0

**Step to reproduce:**
0. Update the `scale_to_zero_time` setting to 1 minutes
```
PUT /_cluster/settings
{
  "persistent": {
    "xpack.ml.trained_models.adaptive_allocations.scale_to_zero_time": "1m"
  }
}
```
1. Create an inference endpoint,
```
PUT _inference/rerank/mytest-old
{
    "service": "elasticsearch",
      "service_settings": {
        "num_threads": 1,
        "model_id": ".rerank-v1",
        "adaptive_allocations": {
          "enabled": true,
          "min_number_of_allocations": 0,
          "max_number_of_allocations": 2
        }
      }
}
```
2. After trained model deployed and started (can use `GET _ml/trained_models/_stats` to check stats), wait couple minutes until the number_of_allocations turns to 0: `"number_of_allocations": 0`
3. Create another inference endpoint,
```
PUT _inference/rerank/mytest-new
{
    "service": "elasticsearch",
      "service_settings": {
        "num_threads": 1,
        "model_id": ".rerank-v1",
        "adaptive_allocations": {
          "enabled": true,
          "min_number_of_allocations": 0,
          "max_number_of_allocations": 2
        }
      }
}
```

4. then run `GET _ml/trained_models/_stats`

the previous `mytest-old` model deployment got deleted unexpectedly.


**Note:**
it can be reproduced on 9.1.0, but not on 8.19.5

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `8c110cb2bc43dc6c135a13482e01ea5ccf85cd14`
**Instance ID:** `elastic__elasticsearch-137244`
**Language:** `Java`
