"""Use the pinned GPU model when ready, with an independently guarded cloud fallback."""

import asyncio
import time

import httpx

from api.app.provider import ModelProvider, ModelUnavailable
from api.app.service import ChatService


class LunaProvider(ModelProvider):
    async def complete(self, messages, max_tokens=384, *, guard=False, response_schema=None):
        key = self.settings.openai_api_key.get_secret_value()
        if not key:
            raise ModelUnavailable("Fallback is not configured", code="not_configured")
        if not guard:
            messages = [dict(message) for message in messages]
            messages[0]["content"] += (
                "\n너의 이름은 이리다. 답변을 소리 내어 읽으므로 마크다운, 이모지, 목록 기호 없이 "
                "자연스러운 한국어 문장으로 답하라. 어린아이에게 맞게 2~4문장으로 간결하게 말하라."
            )
        body = {
            "model": self.settings.fallback_model,
            "input": messages,
            "reasoning": {"effort": self.settings.fallback_reasoning_effort},
            "max_output_tokens": 4096,
            "store": False,
        }
        if response_schema is not None:
            body["text"] = {"format": {
                "type": "json_schema", "name": "safety_verdict",
                "strict": True, "schema": response_schema,
            }}
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}"},
                json=body, timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "completed":
                raise ModelUnavailable("Incomplete fallback response", code="incomplete_response")
            text = "".join(
                part["text"] for item in payload["output"] if item.get("type") == "message"
                for part in item.get("content", []) if part.get("type") == "output_text"
            ).strip()
            if not text or len(text) > (8000 if guard else self.settings.tts_max_chars):
                raise ModelUnavailable("Invalid fallback text", code="invalid_response")
            return text
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailable("Fallback unavailable", code="fallback_error") from exc


class RoutedChatService:
    def __init__(self, primary: ModelProvider):
        self.primary = primary
        self.fallback = LunaProvider(primary.settings, primary.client)
        self.retry_at = 0.0

    async def respond(self, age, history):
        has_fallback = bool(self.primary.settings.openai_api_key.get_secret_value())
        # Preserve the existing API's direct-model behavior when cloud fallback is disabled.
        if not has_fallback:
            answer, action = await ChatService(self.primary).respond(age, history)
            return answer, action, "kanana"
        if time.monotonic() >= self.retry_at:
            try:
                async with asyncio.timeout(self.primary.settings.primary_timeout_seconds):
                    if await self.primary.ready():
                        answer, action = await ChatService(self.primary).respond(age, history)
                        return answer, action, "kanana"
            except (ModelUnavailable, TimeoutError):
                pass
            self.retry_at = time.monotonic() + 15
        answer, action = await ChatService(self.fallback).respond(age, history)
        return answer, action, "luna"
