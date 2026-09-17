import httpx

from runpod.settings import Settings


class ModelUnavailable(Exception):
    """Public handlers must not return the upstream error body."""

    def __init__(self, message: str, *, code: str = "model_unavailable", stage: str | None = None):
        super().__init__(message)
        self.code = code
        self.stage = stage


class ModelProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.model_api_key.get_secret_value()}"}

    def prepare_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return [dict(message) for message in messages]

    async def ready(self) -> bool:
        if not self.settings.configured:
            return False
        try:
            response = await self.client.get(
                f"{self.settings.model_base_url}/models",
                headers=self.headers,
                timeout=5,
            )
            response.raise_for_status()
            available = {item["id"] for item in response.json()["data"]}
            return {
                self.settings.served_model,
                self.settings.generation_model,
            } <= available
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return False

    async def complete(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 384,
        *,
        guard: bool = False,
        response_schema: dict | None = None,
    ) -> str:
        if not self.settings.configured:
            raise ModelUnavailable("Model is not configured", code="not_configured")
        model = self.settings.served_model if guard else self.settings.generation_model
        body = {
            "model": model,
            "messages": self.prepare_messages(messages),
            "temperature": 0,
            "seed": 42,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "safety_verdict",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        try:
            response = await self.client.post(
                f"{self.settings.model_base_url}/chat/completions",
                headers=self.headers,
                json=body,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if payload["model"] != model:
                raise ModelUnavailable("Unexpected model revision", code="model_mismatch")
            choice = payload["choices"][0]
            text = choice["message"]["content"]
            if choice["finish_reason"] != "stop":
                raise ModelUnavailable("Incomplete model response", code="incomplete_response")
            if not isinstance(text, str) or not text.strip():
                raise ModelUnavailable("Empty model response", code="empty_response")
            if len(text) > 8000:
                raise ModelUnavailable("Oversized model response", code="oversized_response")
            return text.strip()
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except httpx.HTTPStatusError as exc:
            raise ModelUnavailable("Upstream HTTP error", code="upstream_http_error") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailable("Upstream transport error", code="transport_error") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelUnavailable("Invalid upstream response", code="invalid_response") from exc
