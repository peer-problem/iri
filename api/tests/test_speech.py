import json
from contextlib import asynccontextmanager

import httpx
import pytest
from pydantic import ValidationError

from api.app.app import create_app
from api.app.settings import Settings

KEY = "test-only-api-key-" + "x" * 32
OPENAI_KEY = "test-only-openai-key"
MP3 = b"ID3" + b"\x00" * 64
PCM = b"\x00\x00\x01\x00\xff\x7f\x00\x80"


def configuration(**updates):
    values = dict(sandbox_api_key=KEY, openai_api_key=OPENAI_KEY)
    values.update(updates)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("speed", [0.25, 0.95, 4.0])
def test_tts_speed_accepts_supported_values(speed):
    assert configuration(tts_speed=speed).tts_speed == speed


@pytest.mark.parametrize("speed", [0.24, 4.01])
def test_tts_speed_rejects_unsupported_values(speed):
    with pytest.raises(ValidationError):
        configuration(tts_speed=speed)


@asynccontextmanager
async def api(handler, settings=None):
    app = create_app(settings or configuration(), transport=httpx.MockTransport(handler))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def speak(client, text="비는 구름 속 물방울이 무거워져서 떨어지는 거야.", **kwargs):
    return await client.post(
        "/speech", headers={"Authorization": f"Bearer {KEY}"}, json={"text": text}, **kwargs
    )


async def test_authentication_is_required_before_tts_call():
    async with api(lambda _: pytest.fail("Must not call TTS without authentication")) as client:
        response = await client.post("/speech", json={"text": "안녕"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [{"text": "   "}, {"text": "x" * 1001}, {"text": "안녕", "voice": "untrusted"}, {}],
)
async def test_invalid_speech_request_does_not_echo(payload):
    async with api(lambda _: pytest.fail("No TTS call expected")) as client:
        response = await client.post(
            "/speech", json=payload, headers={"Authorization": f"Bearer {KEY}"}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


async def test_speech_returns_mp3_with_configured_voice():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})

    async with api(handler) as client:
        response = await speak(client, "안녕!")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == MP3
    assert seen["url"] == "https://api.openai.com/v1/audio/speech"
    assert seen["auth"] == f"Bearer {OPENAI_KEY}"
    assert seen["body"] == {
        "model": "gpt-4o-mini-tts-2025-12-15",
        "voice": "coral",
        "input": "안녕!",
        "instructions": configuration().tts_instructions,
        "speed": 0.95,
        "response_format": "mp3",
    }


async def test_speech_stream_returns_pcm_with_same_voice_profile():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=PCM, headers={"content-type": "application/octet-stream"})

    async with api(handler) as client:
        response = await client.post(
            "/speech-stream", headers={"Authorization": f"Bearer {KEY}"}, json={"text": "안녕!"}
        )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-audio-format"] == "pcm_s16le;rate=24000;channels=1"
    assert response.content == PCM
    assert seen["body"] == {
        "model": "gpt-4o-mini-tts-2025-12-15",
        "voice": "coral",
        "input": "안녕!",
        "instructions": configuration().tts_instructions,
        "speed": 0.95,
        "response_format": "pcm",
    }


async def test_missing_openai_key_is_unavailable_without_call():
    settings = configuration(openai_api_key="")
    async with api(lambda _: pytest.fail("No TTS call expected"), settings) as client:
        response = await speak(client)
    assert response.status_code == 503


@pytest.mark.parametrize(
    "upstream",
    [
        httpx.Response(500, json={"error": {"message": "upstream-secret-detail"}}),
        httpx.Response(200, content=b""),
        httpx.Response(200, json={"error": "not audio"}),
    ],
)
async def test_upstream_failure_is_hidden(upstream):
    async with api(lambda _: upstream) as client:
        response = await speak(client)
    assert response.status_code == 503
    assert "upstream-secret-detail" not in response.text


async def test_upstream_timeout_is_gateway_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    async with api(handler) as client:
        response = await speak(client)
    assert response.status_code == 504


async def test_text_longer_than_setting_is_rejected_without_call():
    settings = configuration(tts_max_chars=5)
    async with api(lambda _: pytest.fail("No TTS call expected"), settings) as client:
        response = await speak(client, "여섯글자입니다")
    assert response.status_code == 413
