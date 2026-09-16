"""Run in a NEW process after training to verify saved adapter loading."""

import argparse
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv

from api.app.service import POLICY, generation_messages
from runpod.operations.data import load_scenarios
from runpod.settings import ENV_FILE, ROOT, Settings


def validate_manifest(run: Path, settings: Settings) -> dict:
    manifest = json.loads((run / "training-manifest.json").read_text())
    if manifest["state"] != "trained_reload_pending":
        raise ValueError("A successfully saved, not-yet-verified adapter is required")
    if (
        manifest["revision"] != settings.model_revision
        or manifest["model_id"] != settings.profile["model_id"]
    ):
        raise ValueError("Base model settings differ from training")
    if (run / "policy.json").read_text() != POLICY:
        raise ValueError("Policy changed since training")
    if (
        not (run / "adapter/adapter_config.json").exists()
        or not (run / "adapter/adapter_model.safetensors").exists()
    ):
        raise ValueError("Saved adapter files are missing")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    load_dotenv(ENV_FILE)
    settings = Settings()
    manifest = validate_manifest(args.run, settings)
    import torch
    from peft import PeftModel
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )

    if not torch.cuda.is_available():
        parser.error("Use the NVIDIA training environment")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    base = AutoModelForCausalLM.from_pretrained(
        settings.profile["model_id"],
        revision=settings.model_revision,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        ),
        torch_dtype=dtype,
        device_map={"": 0},
    )
    model = PeftModel.from_pretrained(base, args.run / "adapter", is_trainable=False).eval()
    tokenizer = AutoTokenizer.from_pretrained(args.run / "adapter", local_files_only=True)
    examples = load_scenarios([(ROOT / "data/dev.jsonl")])[:5]
    responses = []
    for example in examples:
        messages = generation_messages(
            example.age_band, [{"role": "user", "content": example.inputs[0]}]
        )
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to("cuda")
        with torch.inference_mode():
            tokens = model.generate(
                input_ids=inputs,
                attention_mask=torch.ones_like(inputs),
                max_new_tokens=128,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        answer = tokenizer.decode(tokens[0][inputs.shape[-1] :], skip_special_tokens=True).strip()
        if not answer:
            raise ValueError("Reloaded adapter generated an empty response")
        responses.append({"id": example.id, "answer": answer})
    (args.run / "reload-responses.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in responses)
    )
    manifest.update(
        state="reload_verified_behavior_pending",
        adapter_reload_verified=True,
        adapter_sha256=hashlib.sha256(
            (args.run / "adapter/adapter_model.safetensors").read_bytes()
        ).hexdigest(),
        adapter_config_sha256=hashlib.sha256(
            (args.run / "adapter/adapter_config.json").read_bytes()
        ).hexdigest(),
    )
    (args.run / "training-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        "Fresh-process adapter reload produced 5 responses. Safety and quality evaluation are still pending."
    )


if __name__ == "__main__":
    main()
