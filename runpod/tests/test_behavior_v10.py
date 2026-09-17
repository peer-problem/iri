"""V10 changes general generation only; these are request-contract tests."""

import json

import httpx
import pytest

from runpod.inference.behavior import TRIM_V10
from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.service import ChatService, generation_messages, output_guard_messages
from runpod.tests.helpers import completion, configuration

HISTORY = [
    {"role": "user", "content": "첫 질문"},
    {"role": "assistant", "content": "이전 답변"},
    {"role": "user", "content": "지금 질문"},
]


async def capture(profile, age, replies):
    settings = configuration(behavior_profile=profile)
    responses = iter(replies)
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(next(responses), settings)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ChatService(ModelProvider(settings, client)).respond(age, HISTORY)
    return result, calls


@pytest.mark.parametrize("age", ["4-6", "7-10"])
@pytest.mark.parametrize("decision", ["allow", "support", "redirect", "clarify"])
@pytest.mark.parametrize("output", ["allow", "block"])
async def test_v10_preserves_v3_routes_and_guard_requests(age, decision, output):
    replies = [json.dumps({"decision": decision}), "CANDIDATE", json.dumps({"decision": output})]
    old, before = await capture("safety_v3", age, replies)
    new, after = await capture("trim_v10", age, replies)
    assert old == new
    assert before[0] == after[0]
    assert before[2:] == after[2:]
    if decision == "allow":
        assert len(after) == 3
        assert after[1]["messages"][0]["content"] == (
            before[1]["messages"][0]["content"] + "\n" + TRIM_V10
        )
        assert before[1]["messages"][1:] == after[1]["messages"][1:] == HISTORY
        assert {k: v for k, v in before[1].items() if k != "messages"} == {
            k: v for k, v in after[1].items() if k != "messages"
        }
        assert after[1]["max_tokens"] == 384
        assert after[1]["stream"] is False
        assert after[0]["max_tokens"] == after[2]["max_tokens"] == 80
    else:
        assert before == after


@pytest.mark.parametrize("age", ["4-6", "7-10"])
def test_v10_preserves_support_policy_history_and_default(age):
    assert generation_messages(age, HISTORY, "trim_v10", support=True) == generation_messages(
        age, HISTORY, "safety_v3", support=True
    )
    assert output_guard_messages(age, HISTORY, "CANDIDATE", "trim_v10") == output_guard_messages(
        age, HISTORY, "CANDIDATE", "safety_v3"
    )
    assert configuration().behavior_profile == "baseline"
    assert configuration(behavior_profile="trim_v10").behavior_profile == "trim_v10"


@pytest.mark.parametrize("stage", ["input_guard", "output_guard"])
@pytest.mark.parametrize("verdict", ["not-json", '{"decision":"allow","extra":true}'])
async def test_v10_keeps_strict_verdict_validation(stage, verdict):
    replies = [verdict] if stage == "input_guard" else ['{"decision":"allow"}', "PRIVATE", verdict]
    with pytest.raises(ModelUnavailable) as error:
        await capture("trim_v10", "4-6", replies)
    assert error.value.stage == stage
    assert error.value.code == "invalid_verdict"
    assert "PRIVATE" not in str(error.value)
