import base64
import json
import logging
from contextlib import asynccontextmanager

import httpx
import pytest
from pydantic import ValidationError

from api.app.app import create_app
from api.app.settings import Settings

KEY = "test-only-api-key-" + "x" * 32
OPENAI_KEY = "test-only-openai-key"
PCM = b"\x00\x00\x01\x00\xff\x7f\x00\x80"


def speech_events(pcm=PCM, *, done=True):
    events = [
        {
            "type": "speech.audio.delta",
            "audio": base64.b64encode(pcm).decode(),
        }
    ]
    if done:
        events.append({"type": "speech.audio.done"})
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events).encode()


def parse_sse(content: bytes):
    parsed = []
    for block in content.decode().strip().split("\n\n"):
        lines = block.splitlines()
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        parsed.append((name, data))
    return parsed


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


async def test_anonymous_unchecked_text_is_rejected_before_tts_call():
    async with api(lambda _: pytest.fail("Must not call TTS for unchecked text")) as client:
        response = await client.post("/speech", json={"text": "안녕"})
    assert response.status_code == 403
    assert "HttpOnly" in response.headers["set-cookie"]


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


async def test_speech_returns_verified_wav_with_configured_voice():
    seen = {}

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            seen["url"] = str(request.url)
            seen["auth"] = request.headers["authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, content=speech_events())
        seen["transcribed"] = True
        return httpx.Response(200, json={"text": "안녕!"})

    async with api(handler) as client:
        response = await speak(client, "안녕!")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"RIFF")
    assert response.content[8:12] == b"WAVE"
    assert response.content.endswith(PCM)
    assert seen["url"] == "https://api.openai.com/v1/audio/speech"
    assert seen["auth"] == f"Bearer {OPENAI_KEY}"
    assert seen["transcribed"] is True
    assert seen["body"] == {
        "model": "gpt-4o-mini-tts-2025-12-15",
        "voice": "coral",
        "input": "안녕!",
        "instructions": configuration().tts_instructions,
        "speed": 0.95,
        "response_format": "pcm",
        "stream_format": "sse",
    }


async def test_speech_metrics_exclude_text_and_credentials(caplog):
    sensitive_text = "로그에 남으면 안 되는 마지막 문장이야."

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            return httpx.Response(200, content=speech_events())
        return httpx.Response(200, json={"text": sensitive_text})

    with caplog.at_level(logging.INFO, logger="api.app.app"):
        async with api(handler) as client:
            response = await speak(client, sensitive_text)

    assert response.status_code == 200
    records = [
        record.getMessage()
        for record in caplog.records
        if "speech_request" in record.getMessage()
    ]
    assert len(records) == 1
    assert "mode=wav" in records[0]
    assert f"chars={len(sensitive_text)}" in records[0]
    assert "segments=1" in records[0]
    assert f"bytes={len(PCM)}" in records[0]
    assert "retries=0" in records[0]
    assert "completed=true code=ok" in records[0]
    assert sensitive_text not in records[0]
    assert OPENAI_KEY not in records[0]


async def test_speech_stream_returns_verified_pcm_events_with_same_voice_profile():
    seen = {}

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, content=speech_events())
        return httpx.Response(200, json={"text": "안녕!"})

    async with api(handler) as client:
        response = await client.post(
            "/speech-stream", headers={"Authorization": f"Bearer {KEY}"}, json={"text": "안녕!"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-audio-format"] == "pcm_s16le;rate=24000;channels=1"
    assert response.headers["x-accel-buffering"] == "no"
    events = parse_sse(response.content)
    assert [name for name, _ in events] == [
        "audio.started",
        "audio.delta",
        "audio.segment_done",
        "audio.done",
    ]
    assert base64.b64decode(events[1][1]["audio"]) == PCM
    assert events[-1][1]["bytes"] == len(PCM)
    assert events[-1][1]["segments"] == 1
    assert seen["body"] == {
        "model": "gpt-4o-mini-tts-2025-12-15",
        "voice": "coral",
        "input": "안녕!",
        "instructions": configuration().tts_instructions,
        "speed": 0.95,
        "response_format": "pcm",
        "stream_format": "sse",
    }


async def test_speech_stream_reports_later_semantic_failure_without_done(caplog):
    transcripts = iter(
        [
            "첫 번째 문장이야.",
            "마지막 절 앞에서",
            "마지막 절 앞에서",
        ]
    )

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            return httpx.Response(200, content=speech_events())
        return httpx.Response(200, json={"text": next(transcripts)})

    with caplog.at_level(logging.WARNING, logger="api.app.app"):
        async with api(handler) as client:
            response = await client.post(
                "/speech-stream",
                headers={"Authorization": f"Bearer {KEY}"},
                json={"text": "첫 번째 문장이야. 마지막 절까지 말해도 돼."},
            )

    events = parse_sse(response.content)
    assert response.status_code == 200
    assert events[-1] == (
        "audio.error",
        {"requestId": response.headers["x-request-id"], "code": "incomplete"},
    )
    assert "audio.done" not in [name for name, _ in events]
    records = [
        record.getMessage()
        for record in caplog.records
        if "speech_request" in record.getMessage()
    ]
    assert len(records) == 1
    assert "mode=stream" in records[0]
    assert "segments=1" in records[0]
    assert f"bytes={len(PCM)}" in records[0]
    assert "completed=false code=incomplete" in records[0]
    assert "첫 번째 문장이야" not in records[0]


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


async def test_stream_upstream_failure_is_mapped_before_headers_start():
    upstream = httpx.Response(500, json={"error": {"message": "private-upstream-detail"}})
    async with api(lambda _: upstream) as client:
        response = await client.post(
            "/speech-stream",
            headers={"Authorization": f"Bearer {KEY}"},
            json={"text": "안녕!"},
        )
    assert response.status_code == 503
    assert "private-upstream-detail" not in response.text


async def test_text_longer_than_setting_is_rejected_without_call():
    settings = configuration(tts_max_chars=5)
    async with api(lambda _: pytest.fail("No TTS call expected"), settings) as client:
        response = await speak(client, "여섯글자입니다")
    assert response.status_code == 413
