import base64
import binascii
from collections.abc import AsyncIterator
from dataclasses import dataclass
import io
import json
import wave

import httpx

from api.app.settings import Settings
from api.app.speech_contract import segment_speech_text, verify_spoken_text

MAX_AUDIO_BYTES = 20 * 1024 * 1024


class SpeechUnavailable(Exception):
    pass


class SpeechIncomplete(Exception):
    pass


@dataclass(frozen=True)
class VerifiedSpeechSegment:
    index: int
    pcm: bytes
    attempts: int


class Synthesizer:
    """Turns a checked answer into semantically verified PCM speech."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    def _request_body(
        self, text: str, response_format: str, *, stream_format: str | None = None
    ) -> dict[str, str | float]:
        body: dict[str, str | float] = {
            "model": self.settings.tts_model,
            "voice": self.settings.tts_voice,
            "input": text,
            "instructions": self.settings.tts_instructions,
            "speed": self.settings.tts_speed,
            "response_format": response_format,
        }
        if stream_format:
            body["stream_format"] = stream_format
        return body

    @staticmethod
    def pcm_to_wav(pcm: bytes) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24_000)
            wav.writeframes(pcm)
        return output.getvalue()

    async def _generate_sse_pcm(self, text: str) -> bytes:
        key = self.settings.openai_api_key.get_secret_value()
        parts: list[bytes] = []
        total = 0
        completed = False
        try:
            async with self.client.stream(
                "POST",
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}"},
                json=self._request_body(text, "pcm", stream_format="sse"),
                timeout=self.settings.tts_timeout_seconds,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    event = json.loads(payload)
                    event_type = event.get("type")
                    if event_type == "speech.audio.delta":
                        encoded = event.get("audio", event.get("delta"))
                        if isinstance(encoded, dict):
                            encoded = encoded.get("data", encoded.get("delta"))
                        if not isinstance(encoded, str):
                            raise SpeechUnavailable
                        chunk = base64.b64decode(encoded, validate=True)
                        if chunk:
                            total += len(chunk)
                            if total > MAX_AUDIO_BYTES:
                                raise SpeechUnavailable
                            parts.append(chunk)
                    elif event_type == "speech.audio.done":
                        completed = True
                    else:
                        raise SpeechUnavailable
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except SpeechUnavailable:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, binascii.Error, ValueError) as exc:
            raise SpeechUnavailable from exc
        pcm = b"".join(parts)
        if not completed or not pcm or len(pcm) % 2:
            raise SpeechUnavailable
        return pcm

    async def _transcribe_generated_pcm(self, pcm: bytes) -> str:
        wav = self.pcm_to_wav(pcm)
        if len(wav) > self.settings.stt_max_bytes:
            raise SpeechUnavailable
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={
                    "Authorization": (
                        f"Bearer {self.settings.openai_api_key.get_secret_value()}"
                    )
                },
                data={"model": self.settings.stt_model, "language": "ko"},
                files={"file": ("generated-speech.wav", wav, "audio/wav")},
                timeout=self.settings.stt_timeout_seconds,
            )
            response.raise_for_status()
            transcript = response.json()["text"]
            if not isinstance(transcript, str) or not transcript.strip():
                raise SpeechUnavailable
            return transcript.strip()
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except SpeechUnavailable:
            raise
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise SpeechUnavailable from exc

    async def _generate_and_verify(self, text: str) -> bytes:
        pcm = await self._generate_sse_pcm(text)
        transcript = await self._transcribe_generated_pcm(pcm)
        verification = verify_spoken_text(
            text,
            transcript,
            min_similarity=self.settings.tts_verification_min_similarity,
            min_tail_similarity=self.settings.tts_verification_min_tail_similarity,
            tail_chars=self.settings.tts_verification_tail_chars,
        )
        if not verification.passed:
            raise SpeechIncomplete
        return pcm

    async def verified_segments(self, text: str) -> AsyncIterator[VerifiedSpeechSegment]:
        key = self.settings.openai_api_key.get_secret_value()
        if not key:
            raise SpeechUnavailable
        if len(text) > self.settings.tts_max_chars:
            raise ValueError("Text is too long")
        segments = segment_speech_text(
            text,
            max_chars=self.settings.tts_segment_max_chars,
            max_segments=self.settings.tts_max_segments,
        )
        total = 0
        output_index = 0
        for segment in segments:
            try:
                pcm = await self._generate_and_verify(segment)
                attempts = 1
                verified_parts = [pcm]
            except SpeechIncomplete:
                if not self.settings.tts_verification_retries:
                    raise
                retry_segments = segment_speech_text(
                    segment,
                    max_chars=max(30, self.settings.tts_segment_max_chars // 2),
                    max_segments=self.settings.tts_max_segments,
                )
                verified_parts = []
                for retry_segment in retry_segments:
                    verified_parts.append(await self._generate_and_verify(retry_segment))
                attempts = 2
            for pcm in verified_parts:
                total += len(pcm)
                if total > MAX_AUDIO_BYTES:
                    raise SpeechUnavailable
                yield VerifiedSpeechSegment(output_index, pcm, attempts)
                output_index += 1

    async def synthesize_verified_pcm(self, text: str) -> bytes:
        parts = [segment.pcm async for segment in self.verified_segments(text)]
        if not parts:
            raise SpeechUnavailable
        return b"".join(parts)
