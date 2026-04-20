# Task

## [BUG] add_special_tokens=True doesn't add BOS/EOS tokens for microsoft/mdeberta-v3-base tokenizer in transformers >=5.0

### System Info

## Version Details
- Working version: transformers==4.48.0
- Broken versions: transformers==5.0.0, 5.1.0, 5.2.0, 5.3.0
## Environment
- transformers: 5.2.0
- tokenizers: 0.22.2
- Python: 3.12
- Platform: Linux

### Who can help?

@ArthurZucker and @itazap

### Information

- [ ] The official example scripts
- [ ] My own modified scripts

### Tasks

- [ ] An officially supported task in the `examples` folder (such as GLUE/SQuAD, ...)
- [ ] My own task or dataset (give details below)

### Reproduction

## Description
In transformers >=5.0, `add_special_tokens=True` doesn't add special tokens for `microsoft/mdeberta-v3-base` tokenizer. This is a regression from v4.x.
## Reproduction
```python
from transformers import AutoTokenizer
models = [
    "microsoft/mdeberta-v3-base",
    "FacebookAI/roberta-base", 
    "bert-base-uncased"
]
for model_name in models:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    result = tokenizer("hello", add_special_tokens=True)
    print(f"{model_name}: input_ids={result['input_ids']}")
```

## Additional Notes
- The issue is MODEL-SPECIFIC, not general to all tokenizers
- Only microsoft/mdeberta-v3-base is affected
- The tokenizer has correct bos_token_id=1 and eos_token_id=2 values
- This appears to be related to DeBERTa v3's SentencePiece-based tokenizer and the v5 tokenizer redesign
## Expected Behavior
The behavior should be consistent across v4.x and v5.x for backward compatibility.

### Expected behavior

```
Expected (v4.48.0 - Working correctly)
- microsoft/mdeberta-v3-base: [1, 124394, 2] (CLS, hello, SEP)
- FacebookAI/roberta-base: [0, 42891, 2] (<s>, hello, </s>)
- bert-base-uncased: [101, 7592, 102] (CLS, hello, SEP)
Actual (v5.2.0 - Broken for mdeberta only)
- microsoft/mdeberta-v3-base: [124394] ← NO special tokens!
- FacebookAI/roberta-base: [0, 42891, 2] ← Works
- bert-base-uncased: [101, 7592, 102] ← Works
```

---

**Repo:** `huggingface/transformers`
**Base commit:** `bc8c80e0288fd369ad06bff5b480d3c51f97a95e`
**Instance ID:** `huggingface__transformers-44570`
**Language:** `Python`
