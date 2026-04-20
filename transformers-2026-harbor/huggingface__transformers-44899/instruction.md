# Task

## [BUG] Perceiver image classification (non-default res) fails even with interpolate_pos_encoding=True

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
from transformers import PerceiverForImageClassificationLearned, PerceiverImageProcessorPil
from PIL import Image
import requests

url = "http://images.cocodataset.org/val2017/000000039769.jpg"
image = Image.open(requests.get(url, stream=True).raw)
image_processor = PerceiverImageProcessorPil(size={"height": 384, "width": 384})
model = PerceiverForImageClassificationLearned.from_pretrained("deepmind/vision-perceiver-learned")
model.eval()
inputs = image_processor(image, return_tensors="pt").pixel_values
try:
    with torch.no_grad():
        outputs = model(inputs=inputs, interpolate_pos_encoding=True)
    print("Logits shape:", outputs.logits.shape)
    predicted_class = outputs.logits.argmax(-1).item()
    print("Predicted class:", predicted_class)
except Exception as e:
    print(e)
```

→ Trying to run image classification on a 384×384 image (pretrained default is 224×224) and even after setting `interpolate_pos_encoding=True` expecting the model to handle the resolution difference, the model crashes with a `RuntimeError`.
→ From the screenshot, 384×384 = 147456 and 224×224 = 50176 so it was never actually resized (see the reproduction output).

**Current Repro Output:**

<img alt="Image" src="https://github.com/user-attachments/assets/3f1ac00d-5f36-4d3b-be2a-21f46accd0bb" />

### Expected behavior

→ Inference should complete successfully (torch.Size([1, 1000])) when `interpolate_pos_encoding=True` is passed with non-native input res.

---

**Repo:** `huggingface/transformers`
**Base commit:** `c532659b8734b88d2bbaac2542c2a5a8b525f3f7`
**Instance ID:** `huggingface__transformers-44899`
**Language:** `Python`
