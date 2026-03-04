# Task

## Add a `remediate` processor that transforms a failure store document into an indexable form.

### Description

In our docs at https://www.elastic.co/docs/manage-data/data-store/data-streams/failure-store-recipes#create-a-pipeline-to-convert-failure-documents we currently describe how to remediate documents from the failure store using a Painless script. To make things less error-prone, it would be great if we could encapsulate this functionality into a processor.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `41fea9d8a715b1e2ffb668c3cf54c6c9645f0331`
**Instance ID:** `elastic__elasticsearch-133360`
**Language:** `Java`
