# Task

## Taking additional settings providers into account for data stream effective settings

The method used to get effective settings for a data stream did not take settings from IndexSettingsProviders into account. This caused the get data stream mappings API to crash for time_series data streams since settings were missing.
This PR moves `getEffectiveSettings` from DataStream to MetadataDataStreamsService, and adds the implicit settings from IndexSettingsProviders to the effective settings.
Closes #137381

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `5ae8eac46199ca91f6b67838b2435f12ff0ed802`
**Instance ID:** `elastic__elasticsearch-137407`
**Language:** `Java`
