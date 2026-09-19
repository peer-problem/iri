import pytest

from api.deploy import deploy


def test_deploy_requires_the_complete_model_identity(monkeypatch):
    config = {key: "configured" for key in deploy.REQUIRED_RUNTIME}
    config.pop("ADAPTER_SHA256")
    monkeypatch.setattr(deploy, "CONFIG", config)

    with pytest.raises(RuntimeError, match="ADAPTER_SHA256"):
        deploy.require_runtime_config()


def test_deploy_accepts_the_complete_runtime_configuration(monkeypatch):
    config = {key: "configured" for key in deploy.REQUIRED_RUNTIME}
    monkeypatch.setattr(deploy, "CONFIG", config)

    deploy.require_runtime_config()
