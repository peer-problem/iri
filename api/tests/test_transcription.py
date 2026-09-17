import asyncio

import httpx
import pytest

from api.tests.test_api import KEY, api, configuration

WAV = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"fmt " + b"\x00" * 32
OPENAI_KEY = "test-only-openai-key"


def headers(**updates):
    result = {
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "audio/wav",
        "X-Audio-Consent": "true",
    }
    result.update(updates)
    return result


async def test_transcription_uses_official_fields_and_never_calls_chat():
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/audio/transcriptions"
        assert request.headers["authorization"] == f"Bearer {OPENAI_KEY}"
        assert b'name="language"' in request.content and b"gpt-4o-mini-transcribe" in request.content
        assert b'name="languages[]"' not in request.content
        return httpx.Response(200, json={"text": "  비는 왜 내려?  "})

    async with api(handler, configuration(openai_api_key=OPENAI_KEY)) as client:
        response = await client.post("/transcribe", content=WAV, headers=headers())
    assert response.status_code == 200
    assert response.json()["text"] == "비는 왜 내려?"
    assert response.json()["requires_confirmation"] is True
    assert len(calls) == 1


@pytest.mark.parametrize(
    "content,changes,status",
    [
        (WAV, {"Authorization": "Bearer bad"}, 401),
        (WAV, {"X-Audio-Consent": "false"}, 400),
        (WAV, {"Content-Type": "text/plain"}, 415),
        (b"", {}, 400),
        (b"this is not audio", {}, 400),
    ],
)
async def test_invalid_audio_never_reaches_external_service(content, changes, status):
    async with api(
        lambda _: pytest.fail("No external request expected"),
        configuration(openai_api_key=OPENAI_KEY),
    ) as client:
        response = await client.post("/transcribe", content=content, headers=headers(**changes))
    assert response.status_code == status


async def test_audio_limit_enforced_even_without_content_length():
    async def chunks():
        yield WAV[:12]
        yield b"a" * 32

    async with api(
        lambda _: pytest.fail("No external request expected"),
        configuration(openai_api_key=OPENAI_KEY, stt_max_bytes=20),
    ) as client:
        response = await client.post("/transcribe", content=chunks(), headers=headers())
    assert response.status_code == 413


async def test_missing_openai_key_does_not_fall_back_to_fake_transcription():
    async with api(
        lambda _: pytest.fail("No external request expected"), configuration(openai_api_key="")
    ) as client:
        response = await client.post("/transcribe", content=WAV, headers=headers())
    assert response.status_code == 503


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="private upstream error"),
        httpx.Response(429, text="private quota information"),
        httpx.Response(200, json={"text": "a" * 1001}),
        httpx.Response(200, json={"wrong": "field"}),
        httpx.Response(200, json={"text": 123}),
    ],
)
async def test_transcription_failure_is_sanitized(response):
    async with api(lambda _: response, configuration(openai_api_key=OPENAI_KEY)) as client:
        result = await client.post("/transcribe", content=WAV, headers=headers())
    assert result.status_code == 503
    assert "private" not in result.text


async def test_silence_is_a_retryable_input_error():
    async with api(lambda _: httpx.Response(200, json={"text": "  "}), configuration(openai_api_key=OPENAI_KEY)) as client:
        result = await client.post("/transcribe", content=WAV, headers=headers())
    assert result.status_code == 422
    assert result.json()["detail"] == "No speech detected"


async def test_transcription_concurrency_and_timeout():
    started = asyncio.Event()

    async def blocked(_request):
        started.set()
        await asyncio.Event().wait()

    async with api(
        blocked, configuration(openai_api_key=OPENAI_KEY, stt_timeout_seconds=0.1)
    ) as client:
        first = asyncio.create_task(client.post("/transcribe", content=WAV, headers=headers()))
        await started.wait()
        second = await client.post("/transcribe", content=WAV, headers=headers())
        assert second.status_code == 429
        assert (await first).status_code == 504
