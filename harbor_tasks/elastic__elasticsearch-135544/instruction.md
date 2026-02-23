# Task

## Update the HKMeansTest to Account for Allowing -1 SOAR Assignments

I double checked that we validate that -1 is allowed and accounted for.  It indicates when a vector that's being considered for spilling is too close to a centroid to be given a SOAR assignment.  So only needed to update the test.

fixes: https://github.com/elastic/elasticsearch/issues/135538

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `b7dbb2620b714932b323a137c165d26991418fc0`
**Instance ID:** `elastic__elasticsearch-135544`
**Language:** `Java`
