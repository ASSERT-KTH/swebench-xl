# Task

## [BUG] DiaConfig loses custom token IDs after save / load and causes IndexError during generation

### System Info

* `transformers` version: `5.0.0.dev0`
* Platform: `Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.39`
* Python version: `3.12.3`
* `huggingface_hub` version: `1.3.2`
* `safetensors` version: `0.7.0`
* `accelerate` version: `1.12.0`
* Accelerate config: `not installed`
* DeepSpeed version: `not installed`
* PyTorch version (accelerator?): `2.9.1+cu128 (CUDA)`
* GPU type: `NVIDIA L4`
* NVIDIA driver version: `550.90.07`
* CUDA version: `12.4`

### Who can help?

@Rocketknight1

### Information

- [x] The official example scripts
- [ ] My own modified scripts

### Tasks

- [x] An officially supported task in the `examples` folder (such as GLUE/SQuAD, ...)
- [ ] My own task or dataset (give details below)

### Reproduction

```python
import tempfile
from transformers import DiaConfig

config = DiaConfig(eos_token_id=97, pad_token_id=98, bos_token_id=99)
print("Before save eos_token_id:", config.decoder_config.eos_token_id)
with tempfile.TemporaryDirectory() as tmpdir:
  config.save_pretrained(tmpdir)
  loaded_config = DiaConfig.from_pretrained(tmpdir)
  print("After load eos_token_id:", loaded_config.decoder_config.eos_token_id)
# Expected: 97, Actual: 1024
```

[DiaConfig](https://github.com/huggingface/transformers/blob/main/src/transformers/models/dia/configuration_dia.py#L267-L275) sets `eos_token_id`, `pad_token_id`, and `bos_token_id` only on the `decoder_config` sub-config, but not as direct attrs of `DiaConfig`. When the config is saved and reloaded, these values are reset to defaults (1024, 1025, 1026) breaking custom token ID tests with smaller vocabularies.

**Current Output:**

<img alt="Image" src="https://github.com/user-attachments/assets/de3d02a5-5db8-4984-9a7f-e3085bf5fcbd" />

### Expected behavior

→ Custom token IDs should be preserved across save and load.
→ `test_modeling_dia.py::DiaModelTest::test_eager_matches_sdpa_generate` should pass without `IndexError`

**Output After the Fix:**

<img alt="Image" src="https://github.com/user-attachments/assets/36fda528-c201-43c9-8b3f-51f0c9f1c60a" />

---

**Repo:** `huggingface/transformers`
**Base commit:** `5405f80e0e7bca9206445e36f510821b294bf051`
**Instance ID:** `huggingface__transformers-43928`
**Language:** `Python`
