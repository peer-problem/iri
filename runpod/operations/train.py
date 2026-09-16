"""QLoRA training entry point. Imports GPU dependencies only after validating data."""

import argparse
import importlib.metadata
import json
import math
from pathlib import Path

from dotenv import load_dotenv

from api.app.service import POLICY
from runpod.operations.artifacts import code_manifest
from runpod.operations.checkpoints import mark_complete, validate_resume
from runpod.operations.data import load_scenarios
from runpod.operations.experiments import digest
from runpod.operations.prepare_training import validate_split_sizes
from runpod.operations.source_square import normalized
from runpod.operations.training_data import data_fingerprint, encode_row, load_training, pad_batch
from runpod.settings import ENV_FILE, ROOT, Settings


def training_config(smoke: bool) -> dict:
    return {
        "lora": {
            "r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "task_type": "CAUSAL_LM",
            "bias": "none",
        },
        "projection_names": [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        "quantization": {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_use_double_quant": True,
        },
        "trainer": {
            "per_device_train_batch_size": 1,
            "per_device_eval_batch_size": 1,
            "gradient_accumulation_steps": 8,
            "learning_rate": 1e-4,
            "num_train_epochs": 1,
            "max_steps": 20 if smoke else -1,
            "gradient_checkpointing": True,
            "logging_steps": 1,
            "logging_nan_inf_filter": False,
            "eval_strategy": "no",
            "save_strategy": "steps",
            "save_steps": 10,
            "save_total_limit": 2,
            "save_only_model": False,
            "report_to": [],
            "seed": 42,
            "label_names": ["labels"],
            "prediction_loss_only": True,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=(ROOT / "data/prepared/train.jsonl"))
    parser.add_argument(
        "--validation", type=Path, default=(ROOT / "data/prepared/validation.jsonl")
    )
    parser.add_argument("--evaluation", type=Path, nargs="+", default=[(ROOT / "data/dev.jsonl")])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use at most 50 examples and train for 20 optimizer steps",
    )
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--resume-from-checkpoint", type=Path)
    args = parser.parse_args()
    if not 128 <= args.max_length <= 4096:
        parser.error("Context limit must be between 128 and 4096")
    load_dotenv(ENV_FILE)
    settings = Settings()
    if not settings.model_revision:
        parser.error("Set the pinned MODEL_REVISION in .keys/.env")
    train, validation = load_training(args.train, args.validation)
    validate_split_sizes(train, validation)
    evaluation = load_scenarios(args.evaluation)
    if any(row.review_status != "reviewed" for row in evaluation):
        parser.error("Finalize reviewed evaluation labels before training")
    forbidden = {normalized(q) for row in evaluation for q in row.inputs}
    groups = {(row.source_id, row.scenario_id) for row in evaluation}
    if any(
        normalized(row.question) in forbidden or (row.source_id, row.scenario_id) in groups
        for row in [*train, *validation]
    ):
        parser.error("Training data overlaps development or final evaluation")
    config = training_config(args.smoke)
    identity = {
        "model_id": settings.profile["model_id"],
        "revision": settings.model_revision,
        "data_sha256": data_fingerprint([args.train, args.validation]),
        "evaluation_sha256": {str(path): digest(path) for path in args.evaluation},
        "profile": settings.model_profile,
        "max_length": args.max_length,
        "smoke": args.smoke,
        "code_sha256": code_manifest()["sha256"],
        "training_config": config,
    }
    if args.resume_from_checkpoint:
        validate_resume(args.output, args.resume_from_checkpoint, identity, POLICY)
    elif args.output.exists():
        parser.error("Output already exists; choose a new experiment directory")
    stop_file = args.output / "STOP_REQUESTED"
    if stop_file.exists():
        parser.error("Remove STOP_REQUESTED only when ready to resume this training run")
    # Loading these on a laptop is optional; default uv sync does not install them.
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        set_seed,
    )

    if not torch.cuda.is_available():
        parser.error("QLoRA requires the prepared NVIDIA GPU environment")
    set_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(
        settings.profile["model_id"], revision=settings.model_revision
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    if args.smoke:
        train, validation = train[:50], validation[:10]
    encoded_train = [encode_row(row, tokenizer, args.max_length) for row in train]
    encoded_validation = [encode_row(row, tokenizer, args.max_length) for row in validation]
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        settings.profile["model_id"],
        revision=settings.model_revision,
        quantization_config=BitsAndBytesConfig(
            **config["quantization"],
            bnb_4bit_compute_dtype=dtype,
        ),
        torch_dtype=dtype,
        device_map={"": 0},
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    projection_names = set(config["projection_names"])
    targets = [name for name, _ in model.named_modules() if name.split(".")[-1] in projection_names]
    if not targets:
        raise ValueError("No supported language projection modules found")
    model = get_peft_model(
        model,
        LoraConfig(
            **config["lora"],
            target_modules=targets,
        ),
    )

    def collate(features):
        return {
            key: torch.tensor(value)
            for key, value in pad_batch(features, tokenizer.pad_token_id).items()
        }

    class FiniteLoss(TrainerCallback):
        def on_log(self, _args, _state, _control, logs=None, **_kwargs):
            if logs and any(
                not math.isfinite(float(value))
                for key, value in logs.items()
                if key in {"loss", "eval_loss", "grad_norm"}
            ):
                raise ValueError("Non-finite training metric")

    class SaveProgress(TrainerCallback):
        paused = False

        def on_step_end(self, _args, _state, control, **_kwargs):
            if stop_file.exists():
                self.paused = True
                control.should_save = True
                control.should_training_stop = True
            return control

        def on_save(self, trainer_args, state, _control, **_kwargs):
            checkpoint = Path(trainer_args.output_dir) / f"checkpoint-{state.global_step}"
            mark_complete(checkpoint, state.global_step)

    progress = SaveProgress()
    training_args = TrainingArguments(
        output_dir=str(args.output / "checkpoints"),
        logging_dir=str(args.output / "logs"),
        run_name=args.output.name,
        **config["trainer"],
        bf16=dtype == torch.bfloat16,
        fp16=dtype == torch.float16,
    )
    identity["runtime_identity"] = {
        "training_arguments": training_args.to_dict(),
        "dtype": str(dtype),
        "lora_targets": targets,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate")
        },
    }
    if args.resume_from_checkpoint:
        validate_resume(args.output, args.resume_from_checkpoint, identity, POLICY)
    args.output.mkdir(parents=True, exist_ok=bool(args.resume_from_checkpoint))
    manifest = {
        "state": "running",
        **identity,
        "resumed_from": str(args.resume_from_checkpoint) if args.resume_from_checkpoint else None,
        "save_steps": 10,
        "train_count": len(train),
        "validation_count": len(validation),
        "lora_targets": targets,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate")
        },
        "adapter_reload_verified": False,
    }
    (args.output / "training-manifest.json").write_text(json.dumps(manifest, indent=2))
    (args.output / "policy.json").write_text(POLICY)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=encoded_train,
        eval_dataset=encoded_validation,
        data_collator=collate,
        callbacks=[FiniteLoss(), progress],
    )
    torch.cuda.reset_peak_memory_stats()
    result = trainer.train(
        resume_from_checkpoint=str(args.resume_from_checkpoint)
        if args.resume_from_checkpoint
        else None
    )
    if progress.paused:
        manifest.update(state="paused", global_step=trainer.state.global_step)
        (args.output / "training-manifest.json").write_text(json.dumps(manifest, indent=2))
        print("Paused after saving a checkpoint. Stop the Pod and back up persistent storage.")
        return
    metrics = trainer.evaluate()
    if not math.isfinite(float(result.training_loss)) or not math.isfinite(
        float(metrics["eval_loss"])
    ):
        raise ValueError("Training or validation loss is not finite")
    model.save_pretrained(args.output / "adapter")
    tokenizer.save_pretrained(args.output / "adapter")
    manifest.update(
        state="trained_reload_pending",
        training_loss=result.training_loss,
        evaluation=metrics,
        peak_gpu_bytes=torch.cuda.max_memory_allocated(),
        log_history=trainer.state.log_history,
    )
    (args.output / "training-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        f"Adapter saved: {args.output / 'adapter'}. Fresh-process reload and behavioral evaluation remain required."
    )


if __name__ == "__main__":
    main()
