"""Link evaluation identities to saved adapter bytes without importing GPU libraries."""

import hashlib
import json
from pathlib import Path

from runpod.inference.service import POLICY


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def adapter_identity(run: Path, settings) -> dict:
    manifest_path = run / "training-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("state") not in {
        "reload_verified_behavior_pending",
        "fresh_process_reload_verified",
    }:
        raise ValueError("Adapter must pass fresh-process reload verification first")
    if (
        manifest.get("revision") != settings.model_revision
        or manifest.get("model_id") != settings.profile["model_id"]
    ):
        raise ValueError("Adapter base revision differs from configured model")
    training_policy_sha256 = digest(run / "policy.json")
    runtime_policy_sha256 = hashlib.sha256(POLICY.encode()).hexdigest()
    if training_policy_sha256 != runtime_policy_sha256:
        raise ValueError("Adapter policy differs from configured policy")
    weight = digest(run / "adapter/adapter_model.safetensors")
    config = digest(run / "adapter/adapter_config.json")
    if manifest.get("adapter_sha256") != weight or manifest.get("adapter_config_sha256") != config:
        raise ValueError("Adapter files changed since reload verification")
    if settings.adapter_sha256 and weight != settings.adapter_sha256:
        raise ValueError("Adapter weights differ from the configured release SHA-256")
    return {
        "variant": "adapter",
        "base_revision": settings.model_revision,
        "adapter_sha256": weight,
        "adapter_config_sha256": config,
        "training_manifest_sha256": digest(manifest_path),
        "training_policy_sha256": training_policy_sha256,
        "runtime_policy_sha256": runtime_policy_sha256,
        "training_policy_matches_runtime": training_policy_sha256 == runtime_policy_sha256,
        "adapter_revision": settings.adapter_revision,
    }


def evaluation_identity(settings, adapter_run: Path | None = None) -> dict:
    if bool(settings.adapter_name) != bool(adapter_run):
        raise ValueError("ADAPTER_NAME and --adapter-run must be specified together")
    if settings.adapter_name == settings.served_model:
        raise ValueError("Adapter alias must differ from the base model alias")
    identity = (
        adapter_identity(adapter_run, settings)
        if adapter_run
        else {
            "variant": "base",
            "base_revision": settings.model_revision,
            "adapter_sha256": None,
            "adapter_config_sha256": None,
            "training_manifest_sha256": None,
        }
    )
    identity["model_id"] = settings.profile["model_id"]
    identity["behavior_profile"] = settings.behavior_profile
    identity["generation_sampling"] = settings.generation_sampling
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {
        **identity,
        "experiment_id": f"{identity['variant']}-{fingerprint[:20]}",
        "generation_model": settings.generation_model,
        "guard_model": settings.served_model,
    }


def experiment_key(metadata: dict) -> str:
    return metadata.get("experiment_id") or f"{metadata['profile']}@{metadata['revision']}"
