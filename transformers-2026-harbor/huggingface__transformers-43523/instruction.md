# Task

## Weights are not tied when model is loaded onto the `meta` device

This can cause issues if the `model.named_parameters` of a model on the `meta` device are examined because the parameter for the tied weight will still be present.

---

**Repo:** `huggingface/transformers`
**Base commit:** `3f254fbf5fe0754e3183ea002740bb342edb419c`
**Instance ID:** `huggingface__transformers-43523`
**Language:** `Python`
