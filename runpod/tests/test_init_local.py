import pytest


def test_init_local_creates_private_env_without_template(tmp_path, monkeypatch):
    from dotenv import dotenv_values

    from runpod.operations import init_local

    target = tmp_path / ".keys/.env"
    monkeypatch.setattr(init_local, "ENV_FILE", target)
    monkeypatch.chdir(tmp_path)
    init_local.main()
    values = dotenv_values(target)
    assert len(values["MODEL_API_KEY"]) >= 32
    assert target.stat().st_mode & 0o777 == 0o600
    assert target.parent.stat().st_mode & 0o777 == 0o700
    original = target.read_bytes()
    with pytest.raises(SystemExit, match="preserved"):
        init_local.main()
    assert target.read_bytes() == original
