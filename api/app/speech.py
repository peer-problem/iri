from collections.abc import AsyncIterator

import httpx

from api.app.settings import Settings

MAX_AUDIO_BYTES = 20 * 1024 * 1024


class SpeechUnavailable(Exception):
    pass


def looks_like_mp3(audio: bytes) -> bool:
    return audio.startswith(b"ID3") or (len(audio) > 1 and audio[0] == 255 and audio[1] & 224 == 224)


class Synthesizer:
    """Turns an answer that already passed the safety pipeline into MP3 speech."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    def _request_body(self, text: str, response_format: str) -> dict[str, str | float]:
        return {
            "model": self.settings.tts_model,
            "voice": self.settings.tts_voice,
            "input": text,
            "instructions": self.settings.tts_instructions,
            "speed": self.settings.tts_speed,
            "response_format": response_format,
        }

    async def synthesize(self, text: str) -> bytes:
        key = self.settings.openai_api_key.get_secret_value()
        if not key:
            raise SpeechUnavailable
        if len(text) > self.settings.tts_max_chars:
            raise ValueError("Text is too long")
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}"},
                json=self._request_body(text, "mp3"),
                timeout=self.settings.tts_timeout_seconds,
            )
            response.raise_for_status()
            audio = response.content
            if not audio or len(audio) > MAX_AUDIO_BYTES or not looks_like_mp3(audio):
                raise SpeechUnavailable
            return audio
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except httpx.HTTPError as exc:
            raise SpeechUnavailable from exc

    async def stream_pcm(self, text: str) -> AsyncIterator[bytes]:
        key = self.settings.openai_api_key.get_secret_value()
        if not key:
            raise SpeechUnavailable
        if len(text) > self.settings.tts_max_chars:
            raise ValueError("Text is too long")
        total = 0
        try:
            async with self.client.stream(
                "POST",
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}"},
                json=self._request_body(text, "pcm"),
                timeout=self.settings.tts_timeout_seconds,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        total += len(chunk)
                        if total > MAX_AUDIO_BYTES:
                            raise SpeechUnavailable
                        yield chunk
            if not total or total % 2:
                raise SpeechUnavailable
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except httpx.HTTPError as exc:
            raise SpeechUnavailable from exc
