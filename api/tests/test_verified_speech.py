import base64
from contextlib import asynccontextmanager
import json

import httpx
import pytest

from api.app.settings import Settings
from api.app.speech import SpeechIncomplete, SpeechUnavailable, Synthesizer

OPENAI_KEY = "test-only-openai-key"
PCM = b"\x00\x00\x01\x00\xff\x7f\x00\x80"


def configuration(**updates):
    values = dict(openai_api_key=OPENAI_KEY)
    values.update(updates)
    return Settings(_env_file=None, **values)


def speech_events(pcm=PCM, *, done=True, field="audio"):
    events = [
        {"type": "speech.audio.delta", field: base64.b64encode(pcm).decode()}
    ]
    if done:
        events.append({"type": "speech.audio.done"})
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events).encode()


@asynccontextmanager
async def synthesizer(handler, **settings):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), trust_env=False
    ) as client:
        yield Synthesizer(configuration(**settings), client)


async def test_verified_speech_requires_sse_done_and_matching_transcript():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/audio/speech":
            body = json.loads(request.content)
            assert body["response_format"] == "pcm"
            assert body["stream_format"] == "sse"
            return httpx.Response(200, content=speech_events(field="audio"))
        assert request.url.path == "/v1/audio/transcriptions"
        assert request.content.startswith(b"--")
        assert b"RIFF" in request.content and b"WAVE" in request.content
        return httpx.Response(200, json={"text": "안녕, 마지막까지 말해도 돼."})

    async with synthesizer(handler) as current:
        audio = await current.synthesize_verified_pcm("안녕, 마지막까지 말해도 돼.")

    assert audio == PCM
    assert len(requests) == 2


@pytest.mark.parametrize(
    "events",
    [
        speech_events(done=False),
        speech_events(pcm=b"\x00"),
        b'data: {"type":"speech.audio.delta","audio":"%%%"}\n\n',
        b'data: {"type":"speech.unknown"}\n\n',
    ],
)
async def test_verified_speech_rejects_invalid_or_incomplete_sse(events):
    def handler(request):
        if request.url.path == "/v1/audio/speech":
            return httpx.Response(200, content=events)
        pytest.fail("Invalid speech must not reach transcription")

    async with synthesizer(handler) as current:
        with pytest.raises(SpeechUnavailable):
            await current.synthesize_verified_pcm("끝까지 말해 줘.")


async def test_verified_speech_retries_only_the_failed_segment():
    transcripts = iter(["마지막 절 앞에서", "마지막 절까지 말해도 돼."])
    calls = {"speech": 0, "transcription": 0}

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            calls["speech"] += 1
            return httpx.Response(200, content=speech_events())
        calls["transcription"] += 1
        return httpx.Response(200, json={"text": next(transcripts)})

    async with synthesizer(handler) as current:
        segments = [
            segment
            async for segment in current.verified_segments("마지막 절까지 말해도 돼.")
        ]

    assert [segment.pcm for segment in segments] == [PCM]
    assert [segment.attempts for segment in segments] == [2]
    assert calls == {"speech": 2, "transcription": 2}


async def test_verified_speech_fails_closed_after_bounded_retry():
    calls = {"speech": 0, "transcription": 0}

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            calls["speech"] += 1
            return httpx.Response(200, content=speech_events())
        calls["transcription"] += 1
        return httpx.Response(200, json={"text": "마지막 절 앞에서"})

    async with synthesizer(handler) as current:
        with pytest.raises(SpeechIncomplete):
            await current.synthesize_verified_pcm("마지막 절까지 말해도 돼.")

    assert calls == {"speech": 2, "transcription": 2}


async def test_verified_speech_preserves_segment_order():
    spoken = []

    def handler(request):
        if request.url.path == "/v1/audio/speech":
            text = json.loads(request.content)["input"]
            spoken.append(text)
            sample = len(spoken).to_bytes(2, "little")
            return httpx.Response(200, content=speech_events(sample))
        return httpx.Response(200, json={"text": spoken[-1]})

    text = "첫 번째 문장은 끝까지 정확하게 읽어 줘. 두 번째 문장도 순서대로 정확하게 읽어 줘."
    async with synthesizer(handler, tts_segment_max_chars=30) as current:
        audio = await current.synthesize_verified_pcm(text)

    assert spoken == [
        "첫 번째 문장은 끝까지 정확하게 읽어 줘.",
        "두 번째 문장도 순서대로 정확하게 읽어 줘.",
    ]
    assert audio == b"\x01\x00\x02\x00"
