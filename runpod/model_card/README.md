---
base_model: kakaocorp/kanana-2-3b-instruct
library_name: peft
pipeline_tag: text-generation
license: other
license_name: kanana-open-license
license_link: https://huggingface.co/kakaocorp/kanana-2-3b-instruct/blob/6a5d7889964c4c590299d16e309eabab1f73f8a9/LICENSE
tags:
  - lora
  - korean
  - base_model:adapter:kakaocorp/kanana-2-3b-instruct
---

# Kanana IRI 3B QLoRA

**Powered by Kanana.** This repository contains an IRI project LoRA adapter, not a copy of the Kanana base weights. It was trained on `kakaocorp/kanana-2-3b-instruct` at revision `6a5d7889964c4c590299d16e309eabab1f73f8a9`. Use that exact base revision with this adapter.

## Purpose and status

IRI is a Korean conversational prototype for children aged 4 to 10. This adapter is published as a reproducible training result. The Phase 2 comparison did **not** select it as a quality improvement: in a single Codex review of 40 development questions, guarded normal-answer correctness was 21/40 for the adapter and 22/40 for the base. Raw correctness was 22/40 for the adapter and 26/40 for the base. These are development results, not an independent human evaluation. The adapter must not be presented as a validated child-safety model.

The project owner requested publication and a serving path despite the quality result. IRI's input and output checks remain separate from this model. Do not expose a raw model endpoint to children.

## Training and files

The adapter was trained with QLoRA on 50 reviewed training examples and 12 validation examples. It uses rank 16, alpha 32, dropout 0.05 and 4-bit NF4 training quantization. It was reloaded in a fresh process and generated five nonempty responses. `adapter_model.safetensors` and `adapter_config.json` are the PEFT adapter. The tokenizer files are retained from the verified training package for reproducibility.

SHA-256 of `adapter_model.safetensors`: `7e65cf058a51407cef1a0526673253f30f5aafd4d2e192843e71516e43fe71d5`.

SHA-256 of `adapter_config.json`: `fd752db2b93f36dd32c6a884a246334ae7fcf4bd728f4f1f500a22982575926c`.

## Loading

Install compatible versions of `transformers` and `peft`, download the pinned base model and this repository, then attach the adapter with `PeftModel.from_pretrained(base, adapter_directory)`. The IRI repository's `runpod/operations/serve_model.py` starts vLLM 0.29.0 with `--enable-lora` and a distinct adapter alias. The base model handles safety classification while the adapter alias handles answer generation. See `runpod/HF_SERVING.md` in the [IRI source repository](https://github.com/peer-problem/iri) for the exact operator steps and stop procedure.

## Limits and license

This was a small project training run. The final 300-question evaluation was not executed for this adapter. Known development failures include factual mistakes and incomplete safety behavior. A public child-facing launch has not been validated by this card.

The base model is licensed under the [Kanana Open License Agreement](LICENSE). Its restrictions apply to this derivative. The required attribution is in [NOTICE](NOTICE). This adapter and card were modified by the IRI project; Kakao did not endorse them. Commercial remote-access resale may require a separate license under the base agreement.
