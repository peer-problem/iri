import json

import httpx

from api.tests.test_api import KEY, api, completion, configuration
from api.tests.test_speech import MP3


async def test_transcript_to_guarded_answer_to_speech():
    settings = configuration(openai_api_key="test-only-openai-key")
    transcript = "비는 왜 내려?"
    answer = "구름 속 물방울이 무거워지면 비로 떨어져."
    model_outputs = iter(['{"decision":"allow"}', answer, '{"decision":"allow"}'])
    called = []

    def handler(request):
        called.append(request.url.path)
        if request.url.path == "/v1/audio/transcriptions":
            return httpx.Response(200, json={"text": transcript})
        body = json.loads(request.content)
        if request.url.path == "/v1/chat/completions":
            assert transcript in body["messages"][-1]["content"]
            return completion(next(model_outputs), settings)
        assert request.url.path == "/v1/audio/speech"
        assert body["input"] == answer
        return httpx.Response(200, content=MP3)

    async with api(handler, settings) as client:
        headers = {"Authorization": f"Bearer {KEY}"}
        transcribed = await client.post(
            "/transcribe",
            headers={**headers, "Content-Type": "audio/webm", "X-Audio-Consent": "true"},
            content=b"\x1a\x45\xdf\xa3test-audio",
        )
        assert transcribed.status_code == 200
        assert transcribed.json()["requires_confirmation"] is True
        assert called == ["/v1/audio/transcriptions"]
        chat = await client.post(
            "/chat",
            headers=headers,
            json={"age_band": "4-6", "message": transcribed.json()["text"]},
        )
        assert chat.status_code == 200
        assert chat.json()["action"] == "answer"
        spoken = await client.post("/speech", headers=headers, json={"text": chat.json()["answer"]})
        assert spoken.status_code == 200
        assert spoken.content == MP3
        assert spoken.headers["content-type"] == "audio/mpeg"
    assert called == ["/v1/audio/transcriptions", *["/v1/chat/completions"] * 3, "/v1/audio/speech"]
