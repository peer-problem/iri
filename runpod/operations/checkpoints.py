"""Resume only completed checkpoints from the same training experiment."""

import json
from pathlib import Path

from runpod.operations.experiments import digest

IDENTITY_FIELDS = (
    "model_id",
    "revision",
    "data_sha256",
    "profile",
    "max_length",
    "smoke",
    "code_sha256",
    "training_config",
)
CHECKPOINT_FILES = (
    "trainer_state.json",
    "optimizer.pt",
    "scheduler.pt",
    "rng_state.pth",
    "adapter_config.json",
    "adapter_model.safetensors",
)


def mark_complete(checkpoint: Path, step: int):
    if any(
        not (checkpoint / name).is_file() or not (checkpoint / name).stat().st_size
        for name in CHECKPOINT_FILES
    ):
        raise ValueError("Checkpoint is incomplete; refusing to mark it complete")
    state = json.loads((checkpoint / "trainer_state.json").read_text())
    if state.get("global_step") != step or checkpoint.name != f"checkpoint-{step}":
        raise ValueError("Checkpoint step mismatch")
    marker = {
        "global_step": step,
        "files": {name: digest(checkpoint / name) for name in CHECKPOINT_FILES},
    }
    temporary = checkpoint / ".checkpoint-complete.tmp"
    temporary.write_text(json.dumps(marker, indent=2))
    temporary.replace(checkpoint / "checkpoint-complete.json")


def validate_resume(output: Path, checkpoint: Path, identity: dict, policy: str):
    if checkpoint.resolve().parent != (output / "checkpoints").resolve():
        raise ValueError("Resume checkpoint must belong to this output directory")
    previous = json.loads((output / "training-manifest.json").read_text())
    if any(key not in identity for key in IDENTITY_FIELDS) or any(
        previous.get(key) != value for key, value in identity.items()
    ):
        raise ValueError("Model, data or training settings changed; start a new experiment")
    if (output / "policy.json").read_text() != policy:
        raise ValueError("Policy changed; start a new experiment")
    required = ("checkpoint-complete.json", *CHECKPOINT_FILES)
    if any(not (checkpoint / name).is_file() for name in required):
        raise ValueError("Checkpoint is incomplete; use the previous completed checkpoint")
    marker = json.loads((checkpoint / "checkpoint-complete.json").read_text())
    step = json.loads((checkpoint / "trainer_state.json").read_text()).get("global_step")
    if marker.get("global_step") != step or checkpoint.name != f"checkpoint-{step}":
        raise ValueError("Checkpoint step mismatch")
    if marker.get("files") != {name: digest(checkpoint / name) for name in CHECKPOINT_FILES}:
        raise ValueError("Checkpoint files changed or completion hashes are missing")
    return previous
