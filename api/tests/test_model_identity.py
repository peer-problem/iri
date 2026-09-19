import hashlib
import json

import httpx
import pytest
from pydantic import ValidationError

from api.app.settings import Settings as ApiSettings
from api.tests.test_api import KEY, MODEL_KEY, REVISION, api
from runpod.inference.messages import POLICY
from runpod.operations.experiments import adapter_identity
from runpod.settings import Settings as HarnessSettings

ADAPTER_SHA256 = "0ecacdb7d7f743652a24ff7b7e7c59d0e2ae238e63476e64b2d6d95e8fbe2e02"
ADAPTER_REVISION = "0880ce0372cedf22aec91b190f8a7b9499ccc176"
ADAPTER_NAME = f"iri-kanana3b-v5-{ADAPTER_SHA256[:12]}"


def api_settings(**updates):
    values = {
        "sandbox_api_key": KEY,
        "model_api_key": MODEL_KEY,
        "model_revision": REVISION,
        "adapter_name": ADAPTER_NAME,
        "adapter_revision": ADAPTER_REVISION,
        "adapter_sha256": ADAPTER_SHA256,
    }
    values.update(updates)
    return ApiSettings(_env_file=None, **values)


def test_adapter_configuration_requires_complete_hash_bound_identity():
    with pytest.raises(ValidationError):
        ApiSettings(_env_file=None, adapter_name="iri-kanana3b-v5")
    with pytest.raises(ValidationError):
        ApiSettings(_env_file=None, adapter_revision=ADAPTER_REVISION)
    with pytest.raises(ValidationError):
        HarnessSettings(_env_file=None, adapter_sha256=ADAPTER_SHA256)
    with pytest.raises(ValidationError):
        api_settings(adapter_name="iri-kanana3b-v5-wrong")
    assert api_settings().generation_model == ADAPTER_NAME


async def test_ready_requires_the_hash_bound_adapter_alias():
    settings = api_settings()

    async with api(
        lambda _: httpx.Response(
            200,
            json={
                "data": [
                    {"id": settings.served_model},
                    {"id": "iri-kanana3b-tuned"},
                ]
            },
        ),
        settings,
    ) as client:
        response = await client.get("/ready", headers={"Authorization": f"Bearer {KEY}"})
        assert response.status_code == 503

    async with api(
        lambda _: httpx.Response(
            200,
            json={
                "data": [
                    {"id": settings.served_model},
                    {"id": settings.generation_model},
                ]
            },
        ),
        settings,
    ) as client:
        response = await client.get("/ready", headers={"Authorization": f"Bearer {KEY}"})
        assert response.status_code == 200
        assert response.json()["adapter_sha256"] == ADAPTER_SHA256


def test_harness_rejects_adapter_bytes_that_do_not_match_configured_release(tmp_path):
    run = tmp_path / "run"
    adapter = run / "adapter"
    adapter.mkdir(parents=True)
    weight = adapter / "adapter_model.safetensors"
    config = adapter / "adapter_config.json"
    policy = run / "policy.json"
    weight.write_bytes(b"test-adapter")
    config.write_text(json.dumps({"r": 16}))
    policy.write_text(POLICY)

    weight_sha = hashlib.sha256(weight.read_bytes()).hexdigest()
    config_sha = hashlib.sha256(config.read_bytes()).hexdigest()
    manifest = {
        "state": "fresh_process_reload_verified",
        "revision": REVISION,
        "model_id": "kakaocorp/kanana-2-3b-instruct",
        "adapter_sha256": weight_sha,
        "adapter_config_sha256": config_sha,
    }
    (run / "training-manifest.json").write_text(json.dumps(manifest))

    settings = HarnessSettings(
        _env_file=None,
        model_api_key=MODEL_KEY,
        model_revision=REVISION,
        adapter_name=f"iri-test-{weight_sha[:12]}",
        adapter_revision=ADAPTER_REVISION,
        adapter_sha256=weight_sha,
    )
    assert adapter_identity(run, settings)["adapter_sha256"] == weight_sha

    wrong_sha = "b" * 64
    wrong = HarnessSettings(
        _env_file=None,
        model_api_key=MODEL_KEY,
        model_revision=REVISION,
        adapter_name=f"iri-test-{wrong_sha[:12]}",
        adapter_revision=ADAPTER_REVISION,
        adapter_sha256=wrong_sha,
    )
    with pytest.raises(ValueError, match="configured release"):
        adapter_identity(run, wrong)
