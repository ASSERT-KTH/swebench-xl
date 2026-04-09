# Task

## ESQL: Ensure ERROR level logs for bugs in the compute engine

The compute engine used to log any exception as ERROR, causing noise esp. due to logging any CBE at this level. This was downgraded to WARN in https://github.com/elastic/elasticsearch/pull/139799.

Now, we're likely logging actual bugs in the compute engine as WARN where they should be ERROR. This may affect e.g. InvalidStateExceptions that ensure that invariants remain intact - which would be very bad not to notice due to a missing ERROR log message.

Let's ensure such bugs are correctly logged, for instance by introducing some bugs on purpose, confirming that they're just logged as WARN, and making sure they get logged under the correct level.

The solution might be as simple as refining the [logging in the driver](https://github.com/elastic/elasticsearch/blob/ebc04a6d3f6d8c12120c5cda2fc1addd8bbe4191/x-pack/plugin/esql/compute/src/main/java/org/elasticsearch/compute/operator/Driver.java#L198-L199) to differentiate between exceptions that we classify as internal server errors (5xx) and client errors (4xx).

Classifying as bug because potentially missing ERROR logs definitely affect the operability of ES clusters.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `d79939d4c9aa36f8e1d72bc5d6a524213f6df0b1`
**Instance ID:** `elastic__elasticsearch-142330`
**Language:** `Java`
