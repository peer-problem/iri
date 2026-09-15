import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sandbox_api_key: SecretStr = SecretStr("")
    model_api_key: SecretStr = SecretStr("")
    model_base_url: str = "http://127.0.0.1:8001/v1"
    model_profile: Literal["kanana", "gemma"] = "kanana"
    model_revision: str = ""
    request_timeout_seconds: float = Field(default=90, gt=0, le=300)
    max_waiting: int = Field(default=5, ge=0, le=20)
    openai_api_key: SecretStr = SecretStr("")
    stt_model: Literal["gpt-transcribe"] = "gpt-transcribe"
    stt_timeout_seconds: float = Field(default=60, gt=0, le=120)
    stt_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=25_000_000)

    @field_validator("sandbox_api_key", "model_api_key")
    @classmethod
    def validate_key(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("Use a key of at least 32 characters")
        return value

    @field_validator("model_revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        if value and (len(value) != 40 or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("Use a full lowercase Hugging Face commit SHA")
        return value

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
    def profile(self) -> dict:
        return json.loads((ROOT / "configs/models.json").read_text())[self.model_profile]

    @property
    def served_model(self) -> str:
        return f"{self.model_profile}-{self.model_revision}"

    @property
    def configured(self) -> bool:
        return bool(
            self.sandbox_api_key.get_secret_value()
            and self.model_api_key.get_secret_value()
            and self.model_revision
        )
