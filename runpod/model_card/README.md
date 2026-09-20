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

# Kanana IRI 3B QLoRA version history

**Powered by Kanana.** This repository preserves all five LoRA adapters produced while improving the IRI Korean child-conversation prototype. The root adapter is the selected `v5` release. Every historical adapter remains under `versions/` so the full iteration history is auditable.

## Recorded v5 results

| Check | Recorded result | Scope |
| --- | --- | --- |
| Training and validation data | 412 training / 92 validation examples | Three-epoch training run |
| Best validation loss | **2.103572** | Lowest recorded value among v2 through v5; validation sets differ |
| Fresh-process generation | **5/5 selected examples generated** | Adapter reload and generation check, not an accuracy or safety pass rate |
| Targeted correction checks | Corrective responses observed for pet-harm and disability-exclusion requests | Two selected examples from the five-example check |
| Independent final evaluation | Pending | No v5 holdout score is available |

The selected checkpoint was restored and reloaded in a fresh process. These results document completed training and targeted generation checks. See the [project assessment](https://github.com/peer-problem/iri/blob/main/runpod/artifacts/kanana-performance-assessment-20260919/README.md) for the selection evidence and evaluation scope.

## Version sequence

| Version | Train rows | Validation rows | Best validation loss | Outcome |
| --- | ---: | ---: | ---: | --- |
| v1 | 50 | 12 | n/a | historical baseline adapter |
| v2 | 268 | 62 | 2.2475779056549072 | retrained candidate |
| v3 | 332 | 76 | 2.1451010704040527 | full-regression candidate rejected |
| v4 | 372 | 84 | 2.1469812393188477 | supplemental-holdout candidate rejected |
| v5 | 412 | 92 | 2.103572130203247 | selected; fresh-process generation completed for 5/5 examples |

v2 through v5 used the same three-epoch schedule while adding reviewed correction data. Their validation sets differ, so the recorded losses do not establish a like-for-like response-quality improvement. Behavioral selection used separate scenario evaluations. A lower validation loss alone did not determine the release.

v3 was rejected after the 300-scenario regression exposed three severe raw-response safety failures. v4 was rejected after a fresh 60-scenario holdout found unsafe content in exclusion and pet-harm request families, with 46/60 guarded action matches. v5 achieved the lowest comparable validation loss and passed fresh-process loading plus generation checks on those failure families.

A separate v5 holdout run did not start because three Runpod allocation paths failed to provide a GPU host. This limitation is part of the release record. v5 is the best available candidate, not a fully validated child-safety model.

## Loading the selected adapter

Use `kakaocorp/kanana-2-3b-instruct` at commit `6a5d7889964c4c590299d16e309eabab1f73f8a9` and load this repository with PEFT. To reproduce a historical version, download the matching `versions/vN` directory and pass that directory to `PeftModel.from_pretrained`.

The adapters do not include the base weights. Input checks, output checks, deterministic safety routing, rate limits and service policy live in the IRI application and are not embedded in the adapter. Do not expose a raw adapter endpoint as a child safety product.

## Reproducibility and license

Each version directory contains its adapter files, a machine-readable metadata record and the available training manifest. SHA-256 values are listed in `version-index.json`. The base Kanana Open License Agreement in `LICENSE` applies to these derivative adapters. `NOTICE` contains the required attribution. Kakao did not endorse this project.
