# Task

## Don't store keyword multi fields when they trip ignore_above

This is a small refactor + bug for fix [131282](https://github.com/elastic/elasticsearch/issues/131282).

The refactor changes how `text`, `match_only_text`, and `annotated_text` fields use `keyword` multi fields for synthetic source. Currently, this is done via the [hasSyntheticSourceCompatibleKeywordField](https://github.com/elastic/elasticsearch/blob/f0c30f272da3ff36f1a65524cc0e63a07389800a/server/src/main/java/org/elasticsearch/index/mapper/TextFieldMapper.java#L317) argument, where we set a boolean flag to indicate whether there is a keyword multi field that is either stored or has doc values. This is not a good approach for addressing [131282](https://github.com/elastic/elasticsearch/issues/131282) because we want to disable the [following logic](https://github.com/elastic/elasticsearch/blob/main/server/src/main/java/org/elasticsearch/index/mapper/KeywordFieldMapper.java#L1217-L1222) for multi fields. With that disabled, the parent fields will no longer have a multi field to use for synthetic source.

We could designate one of the keyword fields as some kind of "synthetic source provider" for the parent. This way the field will always create a `StoredField` when `ignore_above` is tripped. However, this is a poor approach since it exposes how text fields are implemented to the keyword field. If the parent field decides how and what is stored, it'll be a lot clearer in the code.

This is where this PR comes in. It aims to remove `hasSyntheticSourceCompatibleKeywordField` (although kept for now for bwc) and instead relies on the `syntheticSourceDelegate`. With the addition of a new method `canUseSyntheticSourceDelegateForSyntheticSource()`, which is called during indexing, we can determine whether a particular keyword multi field is a valid supporter of synthetic source. If it isn't, then the parent field will explicitly create a `StoredField` for that.

Note: there are a lot of changed files, that said, most of them are just constructor changes. The actual changes are pretty limited.

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `caff54f13602703b8fa9aaa2f638e4220df31c3b`
**Instance ID:** `elastic__elasticsearch-132962`
**Language:** `Java`
