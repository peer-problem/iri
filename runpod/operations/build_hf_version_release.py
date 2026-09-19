"""Assemble all Kanana IRI adapter versions for one Hugging Face release."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from runpod.settings import ROOT

BASE_MODEL = "kakaocorp/kanana-2-3b-instruct"
BASE_REVISION = "6a5d7889964c4c590299d16e309eabab1f73f8a9"

VERSIONS = {
    "v1": {
        "adapter": ROOT / "backups/hf-kanana-iri-3b-qlora/repo",
        "train": 50,
        "validation": 12,
        "epochs": 1,
        "best_eval_loss": None,
        "status": "historical baseline adapter",
        "result": "Development normal correctness did not improve over the base model.",
    },
    "v2": {
        "adapter": ROOT / "backups/kanana-v2-20260919/final/adapter",
        "manifest": ROOT / "backups/kanana-v2-20260919/final/training-manifest.json",
        "train": 268,
        "validation": 62,
        "epochs": 3,
        "best_eval_loss": 2.2475779056549072,
        "status": "retrained candidate",
        "result": "Fresh-process reload passed. Full behavioral selection was not completed.",
    },
    "v3": {
        "adapter": ROOT / "backups/kanana-v3-20260919/final/results/kanana-v3/adapter",
        "manifest": ROOT
        / "backups/kanana-v3-20260919/final/results/kanana-v3/training-manifest.json",
        "train": 332,
        "validation": 76,
        "epochs": 3,
        "best_eval_loss": 2.1451010704040527,
        "status": "full-regression candidate rejected",
        "result": (
            "Final 300-scenario regression found three severe raw safety failures. "
            "Guarded action match was 239/300 with zero guarded execution errors."
        ),
    },
    "v4": {
        "adapter": ROOT / "backups/kanana-v4-20260919/training/results/kanana-v4/adapter",
        "manifest": ROOT
        / "backups/kanana-v4-20260919/training/results/kanana-v4/training-manifest.json",
        "train": 372,
        "validation": 84,
        "epochs": 3,
        "best_eval_loss": 2.1469812393188477,
        "status": "supplemental-holdout candidate rejected",
        "result": (
            "Fresh 60-scenario holdout completed without errors. Guarded action match was "
            "46/60 and unsafe content remained in two request families."
        ),
    },
    "v5": {
        "adapter": ROOT / "backups/kanana-v5-20260919/training/results/kanana-v5/adapter",
        "manifest": ROOT
        / "backups/kanana-v5-20260919/training/results/kanana-v5/training-manifest.json",
        "train": 412,
        "validation": 92,
        "epochs": 3,
        "best_eval_loss": 2.103572130203247,
        "status": "selected with limited final evaluation",
        "result": (
            "Selected after achieving the lowest comparable validation loss and passing a "
            "fresh-process spot check on the v4 failure families. A separate v5 holdout run "
            "could not start because three GPU allocation paths had no available host."
        ),
    },
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_readme(version: str, metadata: dict) -> str:
    loss = metadata["best_eval_loss"]
    loss_text = "not recorded" if loss is None else f"{loss:.6f}"
    return f"""# Kanana IRI 3B QLoRA {version}

This directory preserves the {version} PEFT adapter from the IRI training sequence. It is a
historical artifact for comparison and reproducibility. It is not a standalone base model.

- Base model: `{BASE_MODEL}`
- Base revision: `{BASE_REVISION}`
- Training rows: {metadata["train"]}
- Validation rows: {metadata["validation"]}
- Epochs: {metadata["epochs"]}
- Best validation loss: {loss_text}
- Status: {metadata["status"]}
- Adapter SHA-256: `{metadata["adapter_sha256"]}`

{metadata["result"]}

Load this version by passing this directory to `PeftModel.from_pretrained` together with the
pinned base revision. Product safety routing is implemented outside the adapter and is not
included in these files.
"""


def main_readme(selected: str, index: list[dict]) -> str:
    rows = "\n".join(
        f"| {row['version']} | {row['train']} | {row['validation']} | "
        f"{row['best_eval_loss'] if row['best_eval_loss'] is not None else 'n/a'} | "
        f"{row['status']} |"
        for row in index
    )
    return f"""---
base_model: {BASE_MODEL}
library_name: peft
pipeline_tag: text-generation
license: other
license_name: kanana-open-license
license_link: https://huggingface.co/{BASE_MODEL}/blob/{BASE_REVISION}/LICENSE
tags:
  - lora
  - korean
  - base_model:adapter:{BASE_MODEL}
---

# Kanana IRI 3B QLoRA version history

**Powered by Kanana.** This repository preserves all five LoRA adapters produced while improving
the IRI Korean child-conversation prototype. The root adapter is the selected `{selected}` release.
Every historical adapter remains under `versions/` so the failed and successful iterations are
auditable instead of being overwritten.

## Version sequence

| Version | Train rows | Validation rows | Best validation loss | Outcome |
| --- | ---: | ---: | ---: | --- |
{rows}

The validation losses are only comparable among v2 through v5, which used the same three-epoch
training schedule while adding reviewed correction data. Behavioral selection used separate
scenario evaluations. A lower training loss alone did not determine the release.

## Loading the selected adapter

Use `{BASE_MODEL}` at commit `{BASE_REVISION}` and load this repository with PEFT. To reproduce a
historical version, download the matching `versions/vN` directory and pass that directory to
`PeftModel.from_pretrained`.

The adapters do not include the base weights. Input checks, output checks, deterministic safety
routing, rate limits and service policy live in the IRI application and are not embedded in the
adapter. Do not expose a raw adapter endpoint as a child safety product.

## Reproducibility and license

Each version directory contains its adapter files, a machine-readable metadata record and the
available training manifest. SHA-256 values are listed in `version-index.json`. The base Kanana
Open License Agreement in `LICENSE` applies to these derivative adapters. `NOTICE` contains the
required attribution. Kakao did not endorse this project.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selected", choices=VERSIONS, required=True)
    parser.add_argument("--v5-evaluation", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")

    args.output.mkdir(parents=True)
    source = ROOT / "backups/hf-kanana-iri-3b-qlora/repo"
    shutil.copy2(source / "LICENSE", args.output / "LICENSE")
    shutil.copy2(source / "NOTICE", args.output / "NOTICE")
    index = []
    for version, details in VERSIONS.items():
        target = args.output / "versions" / version
        shutil.copytree(details["adapter"], target)
        for stale in ("LICENSE", "NOTICE"):
            (target / stale).unlink(missing_ok=True)
        if details.get("manifest"):
            shutil.copy2(details["manifest"], target / "training-manifest.json")
        adapter_sha = digest(target / "adapter_model.safetensors")
        config_sha = digest(target / "adapter_config.json")
        metadata = {
            "version": version,
            "base_model": BASE_MODEL,
            "base_revision": BASE_REVISION,
            "adapter_sha256": adapter_sha,
            "adapter_config_sha256": config_sha,
            **{key: value for key, value in details.items() if key not in {"adapter", "manifest"}},
        }
        if version == "v5" and args.v5_evaluation:
            summary = json.loads(args.v5_evaluation.read_text())
            metadata["evaluation_summary"] = summary
            shutil.copy2(args.v5_evaluation, target / "evaluation-summary.json")
        (target / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        )
        (target / "README.md").write_text(version_readme(version, metadata))
        index.append(metadata)

    selected_dir = args.output / "versions" / args.selected
    for path in selected_dir.iterdir():
        if path.name in {"README.md", "metadata.json", "training-manifest.json"}:
            continue
        if path.is_file():
            shutil.copy2(path, args.output / path.name)
    (args.output / "version-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "README.md").write_text(main_readme(args.selected, index))


if __name__ == "__main__":
    main()
