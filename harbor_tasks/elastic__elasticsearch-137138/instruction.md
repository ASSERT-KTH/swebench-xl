# Task

## Tests misuse randomValueOtherThan() and mutate too many fields at once when testing hashcode and equals methods

## Context
### `randomValueOtherThan()`
The `ESTestCase.randomValueOtherThan(T input, Supplier<T> randomSupplier)` method is used to return an object that is not equal to `input` by invoking the `randomSupplier` lambda. The actual implementation of the method uses `Object.equals()` to determine if the object returned by the `randomSupplier` is equal to `input`, and continues generating new objects until `Object.equals()` returns false. This method is useful when an object doesn't have many possible states, to prevent two randomly generated instances happening to be equal.
For example, consider an example class that has two boolean fields:
```
public class MyObject {
    private final boolean firstField;
    private final boolean secondField;

    MyObject(boolean firstField, boolean secondField) {
        this.firstField = firstField;
        this.secondField = secondField;
    }
}
```

If both fields are used in `equals()` then there are only 4 possible states for the object. Randomly generating instances of this object therefore has a 25% chance that any two randomly generated instances will be equal, which could lead to flakiness if a test expects every randomly generated instance to be different:
```
// 25% chance that the two object below are equal
MyObject object1 = new MyObject(randomBoolean(), randomBoolean());
MyObject object2 = new MyObject(randomBoolean(), randomBoolean());

// Objects below are guaranteed not to be equal
MyObject object3 = new MyObject(randomBoolean(), randomBoolean());
MyObject object4 = randomValueOtherThan(object3, () -> new MyObject(randomBoolean(), randomBoolean()));

```
### `mutateInstance()`
 Tests that extend `AbstractWireTestCase` (which is the standard test case for testing wire serialization) must implement `mutateInstance(T instance)`, which is used in `AbstractWireTestCase.testEqualsAndHashcode()` to generate an instance of the class under test that is not equal to the instance returned from `AbstractWireTestCase.createTestInstance()`. The actual implementation of `AbstractWireTestCase.testEqualsAndHashcode()` checks that the mutated object is not equal to the original object, and that the original object is not equal to the mutated object (since `Object.equals()` implementations must be symmetric). 

## Problems
### Misuse of `randomValueOtherThan()` in `mutateInstance()`
Several tests are using `randomValueOtherThan()` in the `mutateInstance()` method in a way that renders the `AbstractWireTestCase.testEqualsAndHashcode()` test redundant. Consider the below example:
```
protected MyObject mutateInstance(MyObject instance) {
    return randomValueOtherThan(instance, () -> new MyObject(randomBoolean(), randomBoolean()));
}
```
This code will use `equals()` in `randomValueOtherThan()` to check if the new object is equal to the original instance, then pass that object to `AbstractWireTestCase.testEqualsAndHashcode()` to check the behaviour of `equals()`. This makes the test circular, and prevents it from detecting incorrect implementations of `equals()`, since by definition, any new object returned from `randomValueOtherThan()` will return false when compared to the original instance using `equals()`, meaning that the test is effectively asserting that `false == false`.

### Multiple fields changed at once in `mutateInstance()`
In order to comprehensively test the behaviour of `equals()`, only one field should be modified per call of `mutateInstance()`, since modifying multiple fields at once prevents the test from determining if any individual field is being correctly considered in the `equals()` implementation. Consider the following incorrect implementation of `equals()`:
```
public boolean equals(Object o) {
    if (o == null || getClass() != o.getClass()) return false;
    MyObject that = (MyObject) o;
    // This implementation incorrectly does not consider the value of secondField
    return Objects.equals(firstField, that.firstField);
}
```
If both fields were modified every time `mutateInstance()` was called, then we would not be able to determine if the value returned by `equals()` was affected by changes in any one specific field and so would not be able to tell that the `equals()` method was incorrect implemented.

## Solution
`randomValueOtherThan()` should never be used directly with the instance being mutated in `mutateInstance()`. Instead, `randomValueOtherThan()` can be used with the fields on the instance to modify them individually.

A good implementation of the `mutateInstance()` method for the `MyObject` class used in the examples above would be one that only modifies one field from the instance passed into the method. The following pattern of using a switch statement to modify only one field using `randomValueOtherThan()` is used in many tests and results in the correct behaviour:
```
protected MyObject mutateInstance(MyObject instance) throws IOException {
    boolean firstField = instance.getFirstField();
    boolean secondField = instance.getSecondField();
    // Either mutate the first field, or the second field, then return a new object using the new values
    switch (between(0, 1)) {
        case 0 -> firstField = randomValueOtherThan(firstField, () -> randomBoolean());
        case 1 -> secondField = randomValueOtherThan(secondField, () -> randomBoolean());
        default -> throw new AssertionError("Illegal randomisation branch");
    }
    return new MyObject(firstField, secondField);
}
```
The above approach allows us to confirm that two instances of `MyObject` are not equal when only the first field differs, **or** when only the second field differs, which would catch the incorrect `equals()` implementation shown above.

Using IntelliJ's structural search feature, I identified what I think is a comprehensive list of all test classes that are incorrectly using `randomValueOtherThan()` in `mutateInstance()` and which should be fixed. There also exist many other tests that modify multiple fields at once in `mutateInstance()` and which should be fixed, but there is no easy way to identify them en mass, so these should be fixed when they are encountered.

## Affected classes
Below is a list of all test classes where `randomValueOtherThan()` is being misused in `mutateInstance()` grouped by package. The majority of tests needing to be fixed are in the `elasticsearch.x-pack.plugin.ent-search` and `elasticsearch.x-pack.plugin.inference` packages:

- [x] elasticsearch.server package:
```
RolloverConfigurationTests
PutComposableIndexTemplateRequestTests
DeleteSynonymRuleActionRequestSerializingTests
GetSynonymRuleActionRequestSerializingTests
GetSynonymsActionRequestSerializingTests
GetSynonymsActionResponseSerializingTests
GetSynonymsSetsActionRequestSerializingTests
GetSynonymsSetsActionResponseSerializingTests
PutSynonymRuleActionRequestSerializingTests
PutSynonymsActionRequestSerializingTests
SynonymUpdateResponseSerializingTests
DataStreamMetadataTests
NodesShutdownMetadataTests
```

- [x] elasticsearch.x-pack.plugin.autoscaling package:
```
NodeDecisionsWireSerializationTests
NodeDecisionWireSerializationTests
```

- [x] elasticsearch.x-pack.plugin.core package:
```
MigrateToDataTiersRequestTests
HealthApiFeatureSetUsageTests
EnterpriseSearchFeatureSetUsageBWCSerializingTests
DataTiersFeatureSetUsageTests
InferenceContextTests
UnifiedCompletionActionRequestTests
UnifiedCompletionRequestTests
```

- [x] elasticsearch.x-pack.plugin.ent-search package:
```
DeleteAnalyticsCollectionRequestBWCSerializingTests
GetAnalyticsCollectionRequestBWCSerializingTests
GetAnalyticsCollectionResponseBWCSerializingTests
PostAnalyticsEventDebugResponseBWCSerializingTests
PostAnalyticsEventRequestBWCSerializingTests
PostAnalyticsEventResponseBWCSerializingTests
PutAnalyticsCollectionRequestBWCSerializingTests
PutAnalyticsCollectionResponseBWCSerializingTests
AnalyticsEventTests
ConnectorUpdateActionResponseBWCSerializingTests
GetConnectorActionResponseBWCSerializingTests
ListConnectorActionResponseBWCSerializingTests
PostConnectorActionRequestBWCSerializingTests
PostConnectorActionResponseBWCSerializingTests
PutConnectorActionRequestBWCSerializingTests
PutConnectorActionResponseBWCSerializingTests
UpdateConnectorActiveFilteringActionRequestBWCSerializingTests
UpdateConnectorApiKeyIdActionRequestBWCSerializingTests
UpdateConnectorConfigurationActionRequestBWCSerializingTests
UpdateConnectorErrorActionRequestBWCSerializingTests
UpdateConnectorFeaturesActionRequestBWCSerializingTests
UpdateConnectorFilteringActionRequestBWCSerializingTests
UpdateConnectorFilteringValidationActionRequestBWCSerializingTests
UpdateConnectorIndexNameActionRequestBWCSerializingTests
UpdateConnectorLastSeenActionRequestBWCSerializingTests
UpdateConnectorLastSyncStatsActionRequestBWCSerializingTests
UpdateConnectorNameActionRequestBWCSerializingTests
UpdateConnectorNativeActionRequestBWCSerializingTests
UpdateConnectorPipelineActionRequestBWCSerializingTests
UpdateConnectorSchedulingActionRequestBWCSerializingTests
UpdateConnectorServiceTypeActionRequestBWCSerializingTests
UpdateConnectorStatusActionRequestBWCSerializingTests
DeleteConnectorSecretRequestBWCSerializingTests
DeleteConnectorSecretResponseBWCSerializingTests
GetConnectorSecretRequestBWCSerializingTests
GetConnectorSecretResponseBWCSerializingTests
PostConnectorSecretRequestBWCSerializingTests
PostConnectorSecretResponseBWCSerializingTests
PutConnectorSecretRequestBWCSerializingTests
PutConnectorSecretResponseBWCSerializingTests
CancelConnectorSyncJobActionRequestBWCSerializingTests
CheckInConnectorSyncJobActionRequestBWCSerializingTests
ClaimConnectorSyncJobActionRequestBWCSerializingTests
DeleteConnectorSyncJobActionRequestBWCSerializingTests
GetConnectorSyncJobActionRequestBWCSerializingTests
GetConnectorSyncJobActionResponseBWCSerializingTests
ListConnectorSyncJobsActionRequestBWCSerializingTests
ListConnectorSyncJobsActionResponseBWCSerializingTests
PostConnectorSyncJobActionRequestBWCSerializingTests
PostConnectorSyncJobActionResponseBWCSerializingTests
UpdateConnectorSyncJobErrorActionRequestBWCSerializationTests
UpdateConnectorSyncJobIngestionStatsActionRequestBWCSerializingTests
DeleteQueryRuleActionRequestBWCSerializingTests
DeleteQueryRulesetActionRequestBWCSerializingTests
GetQueryRuleActionRequestBWCSerializingTests
GetQueryRuleActionResponseBWCSerializingTests
GetQueryRulesetActionRequestBWCSerializingTests
GetQueryRulesetActionResponseBWCSerializingTests
ListQueryRulesetsActionRequestBWCSerializingTests
ListQueryRulesetsActionResponseBWCSerializingTests
PutQueryRuleActionRequestBWCSerializingTests
PutQueryRuleActionResponseSerializingTests
PutQueryRulesetActionRequestBWCSerializingTests
PutQueryRulesetActionResponseSerializingTests
TestQueryRulesetActionRequestBWCSerializingTests
TestQueryRulesetActionResponseBWCSerializingTests
DeleteSearchApplicationActionRequestBWCSerializingTests
GetSearchApplicationActionRequestBWCSerializingTests
GetSearchApplicationActionResponseBWCSerializingTests
ListSearchApplicationActionRequestBWCSerializingTests
ListSearchApplicationActionResponseBWCSerializingTests
PutSearchApplicationActionRequestBWCSerializingTests
PutSearchApplicationActionResponseBWCSerializingTests
RenderQueryResponseSerializingTests
SearchApplicationSearchRequestBWCSerializingTests
```

- [x] elasticsearch.x-pack.plugin.inference package:
```
ModelSecretsTests
GetRerankerWindowSizeActionRequestTests
GetRerankerWindowSizeActionResponseTests
InferenceActionResponseTests
PutInferenceModelRequestTests
PutInferenceModelResponseTests
UpdateInferenceModelActionRequestTests
UpdateInferenceModelActionResponseTests
AwsSecretSettingsTests
ModelRegistryMetadataTests
Ai21ChatCompletionServiceSettingsTests
AmazonBedrockChatCompletionServiceSettingsTests
AmazonBedrockChatCompletionTaskSettingsTests
AmazonBedrockEmbeddingsServiceSettingsTests
AnthropicChatCompletionServiceSettingsTests
AnthropicChatCompletionTaskSettingsTests
AzureAiStudioChatCompletionServiceSettingsTests
AzureAiStudioChatCompletionTaskSettingsTests
AzureAiStudioEmbeddingsServiceSettingsTests
AzureAiStudioEmbeddingsTaskSettingsTests
AzureAiStudioRerankServiceSettingsTests
AzureAiStudioRerankTaskSettingsTests
AzureOpenAiSecretSettingsTests
AzureOpenAiCompletionServiceSettingsTests
AzureOpenAiCompletionTaskSettingsTests
AzureOpenAiEmbeddingsServiceSettingsTests
AzureOpenAiEmbeddingsTaskSettingsTests
CohereServiceSettingsTests
CohereCompletionServiceSettingsTests
CohereEmbeddingsServiceSettingsTests
CohereEmbeddingsTaskSettingsTests
CohereRerankServiceSettingsTests
CohereRerankTaskSettingsTests
CustomSecretSettingsTests
CustomServiceSettingsTests
CustomTaskSettingsTests
InputTypeTranslatorTests
QueryParametersTests
CompletionResponseParserTests
RerankResponseParserTests
SparseEmbeddingResponseParserTests
TextEmbeddingResponseParserTests
ElasticInferenceServiceSparseEmbeddingsServiceSettingsTests
ElasticInferenceServiceCompletionServiceSettingsTests
ElasticInferenceServiceDenseTextEmbeddingsServiceSettingsTests
ElasticInferenceServiceRerankServiceSettingsTests
CustomElandInternalTextEmbeddingServiceSettingsTests
RerankTaskSettingsTests
GoogleAiStudioCompletionServiceSettingsTests
GoogleAiStudioEmbeddingsServiceSettingsTests
GoogleVertexAiSecretSettingsTests
GoogleVertexAiEmbeddingsServiceSettingsTests
GoogleVertexAiEmbeddingsTaskSettingsTests
GoogleVertexAiRerankServiceSettingsTests
GoogleVertexAiRerankTaskSettingsTests
HuggingFaceServiceSettingsTests
HuggingFaceChatCompletionServiceSettingsTests
HuggingFaceElserServiceSettingsTests
HuggingFaceRerankTaskSettingsTests
IbmWatsonxChatCompletionServiceSettingsTests
IbmWatsonxEmbeddingsServiceSettingsTests
JinaAIServiceSettingsTests
JinaAIEmbeddingsServiceSettingsTests
JinaAIEmbeddingsTaskSettingsTests
JinaAIRerankServiceSettingsTests
JinaAIRerankTaskSettingsTests
LlamaChatCompletionServiceSettingsTests
LlamaEmbeddingsServiceSettingsTests
MistralChatCompletionServiceSettingsTests
OpenAiChatCompletionServiceSettingsTests
OpenAiEmbeddingsServiceSettingsTests
OpenAiEmbeddingsTaskSettingsTests
DefaultSecretSettingsTests
RateLimitSettingsTests
VoyageAIServiceSettingsTests
VoyageAIEmbeddingsServiceSettingsTests
VoyageAIEmbeddingsTaskSettingsTests
VoyageAIRerankServiceSettingsTests
VoyageAIRerankTaskSettingsTests
```

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ac0bc487771aa0405dbd50dcbae3b0803b7fac84`
**Instance ID:** `elastic__elasticsearch-137138`
**Language:** `Java`

You can execute bash commands and edit files to implement the necessary changes.

## Recommended Workflow

This workflows should be done step-by-step so that you can iterate on your 
changes and any possible problems.

1. Analyze the codebase by finding and reading relevant files
2. Create a script to reproduce the issue
3. Edit the source code to resolve the issue
4. Verify your fix works by running your script again
5. Test edge cases to ensure your fix is robust
6. Submit your changes and finish your work by issuing the following command: 
`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.
   Do not combine it with any other command. <important>After this command, you 
cannot continue working on this task.</important>

## Important Rules

1. Every response must contain exactly one action
2. The action must be enclosed in triple backticks
3. Directory or environment variable changes are not persistent. Every action is
executed in a new subshell.
   However, you can prefix any action with `MY_ENV_VAR=MY_VALUE cd 
/path/to/working/dir && ...` or write/load environment variables from files

<system_information>
Linux 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun  5 
18:30:46 UTC 2025 x86_64
</system_information>

## Formatting your response

Here is an example of a correct response:

<example_response>
THOUGHT: I need to understand the structure of the repository first. Let me 
check what files are in the current directory to get a better understanding of 
the codebase.

```bash
ls -la
```
</example_response>

## Useful command examples

### Create a new file:

```bash
cat <<'EOF' > newfile.py
import numpy as np
hello = "world"
print(hello)
EOF
```

### Edit files with sed:```bash
# Replace all occurrences
sed -i 's/old_string/new_string/g' filename.py

# Replace only first occurrence
sed -i 's/old_string/new_string/' filename.py

# Replace first occurrence on line 1
sed -i '1s/old_string/new_string/' filename.py

# Replace all occurrences in lines 1-10
sed -i '1,10s/old_string/new_string/g' filename.py
```

### View file content:

```bash
# View specific lines with numbers
nl -ba filename.py | sed -n '10,20p'
```

### Any other command you want to run

```bash
anything
```
