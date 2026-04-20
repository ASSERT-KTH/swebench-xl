# Task

## GPT2 attention scaling config is ignored when using SDPA / FlashAttention backends

### System Info

None

### Who can help?

@ArthurZucker Hi, I'm new to LLMs and currently learning GPT2 model. I found that

The GPT2 attention configuration options:
	•	scale_attn_weights
	•	scale_attn_by_inverse_layer_idx

are respected in eager attention mode but silently ignored when using AttentionInterface backends such as "sdpa" or "flash_attention_2".

In eager mode:
the scaling logic is applied inside eager_attention_forward:
	•	division by sqrt(head_dim) if scale_attn_weights=True
	•	division by (layer_idx+1) if scale_attn_by_inverse_layer_idx=True

However, when using sdpa:
`torch._C._nn.scaled_dot_product_attention(query_states_3, key_states_3, value_states_3, attn_mask = attention_mask_1, dropout_p = 0.0, scale = None, is_causal = False)` which seems to ignore the above config.

I realize that the default configuration (`scale_attn_weights =True, scale_attn_by_inverse_layer_idx=False`) produces the same results, so I’m not sure whether this is intentional or should be considered a bug. 

### Information

- [x] The official example scripts
- [ ] My own modified scripts

### Tasks

- [x] An officially supported task in the `examples` folder (such as GLUE/SQuAD, ...)
- [ ] My own task or dataset (give details below)

### Reproduction

None

### Expected behavior

Different attention implementations should produce semantically equivalent results and respect model configuration parameters.

---

**Repo:** `huggingface/transformers`
**Base commit:** `22c35ca55b64af7fa08a8a30ea26d4d8dda88056`
**Instance ID:** `huggingface__transformers-44397`
**Language:** `Python`
