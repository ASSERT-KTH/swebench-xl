# Task

## [BUG][CI] BitNet AutoBitLinear fails when packed weights aren’t unpacked during accelerate loading

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

### Information

- [x] The official example scripts
- [ ] My own modified scripts

### Tasks

- [x] An officially supported task in the `examples` folder (such as GLUE/SQuAD, ...)
- [ ] My own task or dataset (give details below)

### Reproduction

```python
import torch
from transformers import BitNetForCausalLM

model = BitNetForCausalLM.from_pretrained("microsoft/bitnet-b1.58-2B-4T")
input_ids = torch.tensor([[1, 2, 3]])
with torch.no_grad():
    output = model(input_ids)
print(output.logits.shape)
```

When loading `microsoft/bitnet-b1.58-2B-4T` with `device_map="auto"`, `AutoBitLinear.load_hook` is bypassed by accelerate's loading process; leaving weights in packed format (shape `[out_features//4, in_features]`). This materializes as inference + CI failures with `RuntimeError: shape '[1, 3, -1, 128]' is invalid for input of size 480`.

**CI Failure:**

<img alt="Image" src="https://github.com/user-attachments/assets/d4d9c72a-e177-4f68-ab85-f53d63de1e44" /><br>

**Current Output:**

<img alt="Image" src="https://github.com/user-attachments/assets/4629e69b-5c80-47d8-a78b-d609eab80fa0" />

### Expected behavior

→ The model should load and run inference successfully.
→ `tests/models/bitnet/test_modeling_bitnet.py::BitNetIntegrationTest::test_model_generation && tests/models/bitnet/test_modeling_bitnet.py::BitNetIntegrationTest::test_model_logits` integration tests pass without regressions

**Output After the Fix:**

<img alt="Image" src="https://github.com/user-attachments/assets/931af873-8190-49af-a7bc-8cf03c18cd63" />

---

**Repo:** `huggingface/transformers`
**Base commit:** `53f8a08290bf835c9891094352f9efd7da0ccece`
**Instance ID:** `huggingface__transformers-43721`
**Language:** `Python`
