import json

import httpx
import pytest

from runpod.operations.checkpoints import CHECKPOINT_FILES, mark_complete, validate_resume
from runpod.operations.runpod_guard import POD_NAME, stop, stop_reason


def test_stop_targets_only_explicit_project_pod_and_verifies_state():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "id": "test-pod",
                "name": POD_NAME,
                "desiredStatus": "EXITED" if len(calls) == 3 else "RUNNING",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert stop(client, "test-pod")
    assert calls == [
        ("GET", "/v1/pods/test-pod"),
        ("POST", "/v1/pods/test-pod/stop"),
        ("GET", "/v1/pods/test-pod"),
    ]


def test_unrelated_pod_never_mutated():
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"id": "other", "name": "another-project"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="identity"):
            stop(client, "other")


def test_successful_stop_request_does_not_imply_confirmed_stop():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "id": "test-pod",
                "name": POD_NAME,
                "desiredStatus": "RUNNING",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert not stop(client, "test-pod")


def test_error_response_never_exposes_credentials():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(401, text="SECRET_CREDENTIAL"))
    ) as client:
        with pytest.raises(RuntimeError, match="^Runpod returned HTTP 401$"):
            stop(client, "test-pod")


def test_activity_lease_and_hard_deadline_are_independent():
    state = {"deadline": 3600}
    assert stop_reason(state, 1000, 999) is None
    assert stop_reason(state, 1000, 820) == "activity_lease_expired"
    assert stop_reason(state, 3600, 3600) == "runtime_limit"
    assert stop_reason(state, 1000, None) == "activity_lease_expired"


def test_resume_rejects_incomplete_and_changed_experiments(tmp_path):
    identity = dict(
        model_id="model",
        revision="a" * 40,
        data_sha256="data",
        profile="kanana",
        max_length=1024,
        smoke=True,
        code_sha256="code",
        training_config={"learning_rate": 1e-4},
    )
    (tmp_path / "training-manifest.json").write_text(json.dumps(identity))
    (tmp_path / "policy.json").write_text("policy")
    checkpoint = tmp_path / "checkpoints/checkpoint-10"
    checkpoint.mkdir(parents=True)
    with pytest.raises(ValueError, match="incomplete"):
        validate_resume(tmp_path, checkpoint, identity, "policy")
    for name in CHECKPOINT_FILES:
        (checkpoint / name).write_text("fixture")
    (checkpoint / "trainer_state.json").write_text('{"global_step":10}')
    mark_complete(checkpoint, 10)
    assert validate_resume(tmp_path, checkpoint, identity, "policy") == identity
    with pytest.raises(ValueError, match="changed"):
        validate_resume(tmp_path, checkpoint, {**identity, "data_sha256": "different"}, "policy")
    with pytest.raises(ValueError, match="Policy changed"):
        validate_resume(tmp_path, checkpoint, identity, "new policy")
    with pytest.raises(ValueError, match="belong"):
        validate_resume(tmp_path, tmp_path.parent, identity, "policy")
    for field, value in (("code_sha256", "new-code"), ("training_config", {"learning_rate": 2e-4})):
        with pytest.raises(ValueError, match="changed"):
            validate_resume(tmp_path, checkpoint, {**identity, field: value}, "policy")
    (checkpoint / "optimizer.pt").write_text("tampered")
    with pytest.raises(ValueError, match="files changed"):
        validate_resume(tmp_path, checkpoint, identity, "policy")
