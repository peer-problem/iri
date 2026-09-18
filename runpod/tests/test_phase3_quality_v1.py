import json

import httpx

from runpod.inference.provider import ModelProvider
from runpod.inference.service import ChatService
from runpod.tests.helpers import completion, configuration


async def test_quality_candidate_uses_one_input_check_and_keeps_support_generation():
    settings = configuration(behavior_profile="phase3_quality_v1")
    calls = []
    replies = iter(['{"decision":"support"}', "도움을 요청해도 좋아.", '{"decision":"allow"}'])

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(next(replies), settings)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ChatService(ModelProvider(settings, client)).respond(
            "4-6", [{"role": "user", "content": "무서운 일을 겪었어."}]
        )

    assert result == ("도움을 요청해도 좋아.", "support")
    assert len(calls) == 3
    assert "무서운 장면" in calls[0]["messages"][0]["content"]
    assert "가해자가 부모나 교사" in calls[1]["messages"][0]["content"]
    assert "계속 지켜보는 능력" in calls[2]["messages"][0]["content"]
