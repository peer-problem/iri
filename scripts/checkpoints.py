"""Resume only completed checkpoints from the same training experiment."""

import json
from pathlib import Path

IDENTITY_FIELDS = ("model_id", "revision", "data_sha256", "profile", "max_length", "smoke")


def validate_resume(output: Path, checkpoint: Path, identity: dict, policy: str):
    if checkpoint.resolve().parent != (output / "checkpoints").resolve():
        raise ValueError("Resume checkpoint must belong to this output directory")
    previous = json.loads((output / "training-manifest.json").read_text())
    if any(previous.get(key) != identity[key] for key in IDENTITY_FIELDS):
        raise ValueError("Model, data or training settings changed; start a new experiment")
    if (output / "policy.json").read_text() != policy:
        raise ValueError("Policy changed; start a new experiment")
    required = (
        "checkpoint-complete.json",
        "trainer_state.json",
        "optimizer.pt",
        "scheduler.pt",
        "rng_state.pth",
        "adapter_config.json",
        "adapter_model.safetensors",
    )
    if any(not (checkpoint / name).is_file() for name in required):
        raise ValueError("Checkpoint is incomplete; use the previous completed checkpoint")
    return previous
