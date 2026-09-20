from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.app.behavior import BehaviorProfile

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
ENV_FILE = REPO_ROOT / ".keys/.env"
DEFAULT_TTS_INSTRUCTIONS = (
    "편안하고 부드러운 한국어 일상 대화체로 자연스럽게 말한다. 목소리에 은은한 따뜻함을 담고, "
    "자음과 문장 끝을 세게 끊지 않는다. 설명문을 낭독하거나 캐릭터를 연기하지 말고, "
    "바로 옆 사람에게 차분히 이야기하듯 담백하게 말한다. 억양 변화는 완만하게 유지하고 "
    "문장 끝을 과하게 올리거나 늘이지 않는다. 일정한 음량을 유지하며 문장부호에서만 자연스럽게 짧게 쉰다."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    sandbox_api_key: SecretStr = SecretStr("")
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
    max_waiting: int = Field(default=5, ge=0, le=20)
    openai_api_key: SecretStr = SecretStr("")
    stt_model: Literal["gpt-transcribe", "gpt-4o-mini-transcribe"] = "gpt-4o-mini-transcribe"
    stt_timeout_seconds: float = Field(default=60, gt=0, le=120)
    stt_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=25_000_000)
    tts_model: Literal["gpt-4o-mini-tts-2025-12-15"] = "gpt-4o-mini-tts-2025-12-15"
    tts_voice: Literal["marin"] = "marin"
    tts_instructions: str = Field(default=DEFAULT_TTS_INSTRUCTIONS, max_length=500)
    tts_speed: float = Field(default=1.0, ge=0.25, le=4.0)
    tts_timeout_seconds: float = Field(default=60, gt=0, le=120)
    tts_max_chars: int = Field(default=1000, ge=1, le=4000)
    tts_segment_max_chars: int = Field(default=240, ge=30, le=300)
    tts_max_segments: int = Field(default=12, ge=1, le=32)
    tts_verification_retries: int = Field(default=1, ge=0, le=1)
    tts_verification_min_similarity: float = Field(default=0.78, ge=0.5, le=1)
    tts_verification_min_tail_similarity: float = Field(default=0.72, ge=0.5, le=1)
    tts_verification_tail_chars: int = Field(default=18, ge=4, le=64)
    fallback_model: str = "gpt-5.6-luna"
    fallback_reasoning_effort: Literal["high"] = "high"
    fallback_guard_reasoning_tokens: int = Field(default=768, ge=0, le=4096)
    fallback_generation_reasoning_tokens: int = Field(default=1152, ge=0, le=4096)
    primary_timeout_seconds: float = Field(default=15, gt=0, le=60)
    secure_cookies: bool = False
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @field_validator("sandbox_api_key", "model_api_key")
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
        return bool(
            self.sandbox_api_key.get_secret_value()
            and self.model_api_key.get_secret_value()
            and self.model_revision
        )
