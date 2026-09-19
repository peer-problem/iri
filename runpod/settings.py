import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from runpod.inference.behavior import BehaviorProfile

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
ENV_FILE = REPO_ROOT / ".keys/.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    model_api_key: SecretStr = SecretStr("")
    model_base_url: str = "http://127.0.0.1:8002/v1"
    model_serve_port: int = Field(default=8002, ge=1024, le=65535)
    model_profile: Literal["kanana"] = "kanana"
    model_revision: str = ""
    adapter_name: str = Field(default="", pattern=r"^[a-zA-Z0-9_-]*$")
    adapter_revision: str = ""
    adapter_sha256: str = ""
    behavior_profile: BehaviorProfile = "baseline"
    request_timeout_seconds: float = Field(default=90, gt=0, le=300)

    @field_validator("model_api_key")
    @classmethod
    def validate_key(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("Use a key of at least 32 characters")
        return value

    @field_validator("model_revision", "adapter_revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        if value and (len(value) != 40 or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("Use a full lowercase Hugging Face commit SHA")
        return value

    @field_validator("adapter_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if value and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("Use a full lowercase SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_adapter(self):
        identity = (self.adapter_name, self.adapter_revision, self.adapter_sha256)
        if any(identity) and not all(identity):
            raise ValueError(
                "ADAPTER_NAME, ADAPTER_REVISION and ADAPTER_SHA256 must be specified together"
            )
        if self.adapter_name and not self.adapter_name.endswith(self.adapter_sha256[:12]):
            raise ValueError("Adapter alias must end with the first 12 characters of its SHA-256")
        return self

    @field_validator("model_base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        url = urlparse(value)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ValueError("Model URL must not contain credentials, query or fragment")
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Use HTTPS or a localhost SSH tunnel")
        return value.rstrip("/")

    @property
    def served_model(self) -> str:
        return f"{self.model_profile}-{self.model_revision}"

    @property
    def generation_model(self) -> str:
        return self.adapter_name or self.served_model

    @property
    def configured(self) -> bool:
        return bool(self.model_api_key.get_secret_value() and self.model_revision)

    @property
    def profile(self) -> dict:
        return json.loads((ROOT / "configs/models.json").read_text())[self.model_profile]

    @property
    def generation_sampling(self) -> dict:
        return {"temperature": 0, "seed": 42}
