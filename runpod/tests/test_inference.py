import json

import httpx
import pytest

from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.service import FALLBACKS, ChatService, generation_messages
from runpod.tests.helpers import MODEL_KEY, completion, configuration


async def respond(texts, profile="baseline", decision_question="도움이 필요해"):
    settings = configuration(behavior_profile=profile)
    replies = iter(texts)
    calls = []

    def handler(request):
        assert request.headers["authorization"] == f"Bearer {MODEL_KEY}"
        calls.append(json.loads(request.content))
        return completion(next(replies), settings)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ChatService(ModelProvider(settings, client)).respond(
            "4-6", [{"role": "user", "content": decision_question}]
        )
    return result, calls


async def test_safe_answer_requires_both_guards():
    result, calls = await respond(['{"decision":"allow"}', "검사할 답변", '{"decision":"allow"}'])
    assert result == ("검사할 답변", "answer")
    assert len(calls) == 3
    assert all(call["stream"] is False for call in calls)
    assert "검사할 답변" in calls[2]["messages"][1]["content"]
    assert "response_format" not in calls[1]
    for index, decisions in [
        (0, ["allow", "redirect", "support", "clarify"]),
        (2, ["allow", "block"]),
    ]:
        schema = calls[index]["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert schema["schema"]["properties"]["decision"]["enum"] == decisions
        assert schema["schema"]["additionalProperties"] is False


@pytest.mark.parametrize("decision", ["redirect", "support", "clarify"])
async def test_non_generation_decisions_use_one_model_call(decision):
    result, calls = await respond([json.dumps({"decision": decision})])
    assert result == (FALLBACKS[decision], decision)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "verdict", ["not-json", '{"decision":"allow","extra":"injection"}', '{"decision":"unknown"}']
)
async def test_invalid_output_verdict_never_releases_candidate(verdict):
    with pytest.raises(ModelUnavailable) as error:
        await respond(['{"decision":"allow"}', "PRIVATE_CANDIDATE", verdict])
    assert error.value.stage == "output_guard"
    assert error.value.code == "invalid_verdict"
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize(
    "texts,stage,code",
    [
        (["private-invalid-json"], "input_guard", "invalid_verdict"),
        (['{"decision":"allow"}', ""], "generation", "empty_response"),
        (
            ['{"decision":"allow"}', "private-candidate", "invalid"],
            "output_guard",
            "invalid_verdict",
        ),
    ],
)
async def test_failures_preserve_stage_without_private_text(texts, stage, code):
    with pytest.raises(ModelUnavailable) as error:
        await respond(texts)
    assert error.value.stage == stage
    assert error.value.code == code
    assert "private" not in str(error.value)


@pytest.mark.parametrize("profile", ["support_v2", "full_v2", "support_v3", "safety_v3"])
@pytest.mark.parametrize("output_decision", ["allow", "block"])
async def test_support_output_check_preserves_support_route(profile, output_decision):
    result, calls = await respond(
        ['{"decision":"support"}', "SUPPORT_CANDIDATE", json.dumps({"decision": output_decision})],
        profile,
    )
    expected = "SUPPORT_CANDIDATE" if output_decision == "allow" else FALLBACKS["support"]
    assert result == (expected, "support")
    assert len(calls) == 3
    assert "가해자로 지목된 사람" in calls[1]["messages"][0]["content"]


@pytest.mark.parametrize("profile", ["input_v2", "input_v3"])
async def test_input_only_profile_preserves_static_support(profile):
    result, calls = await respond(['{"decision":"support"}'], profile)
    assert result == (FALLBACKS["support"], "support")
    assert len(calls) == 1


@pytest.mark.parametrize("decision", ["allow", "support"])
async def test_v3_keeps_policy_and_separate_output_rules(decision):
    result, calls = await respond(
        [json.dumps({"decision": decision}), "후보 답변", '{"decision":"block"}'], "safety_v3"
    )
    action = "support" if decision == "support" else "redirect"
    assert result == (FALLBACKS[action], action)
    assert "누가 무엇을 겪었고" in calls[0]["messages"][0]["content"]
    assert "현실의 위험 행동" in calls[2]["messages"][0]["content"]
    for index in (0, 2):
        assert '"output_checks"' in calls[index]["messages"][0]["content"]


def test_v3_raw_generation_requests_are_identical():
    history = [{"role": "user", "content": "질문"}]
    baseline = generation_messages("4-6", history)
    for profile in ("input_v3", "support_v3", "safety_v3"):
        assert generation_messages("4-6", history, profile) == baseline


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="upstream-secret-detail"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"model": "wrong-revision", "choices": []}),
        completion("", configuration()),
        completion("partial", configuration(), finish_reason="length"),
    ],
)
async def test_bad_upstream_responses_are_not_success(response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as client:
        with pytest.raises(ModelUnavailable) as error:
            await ModelProvider(configuration(), client).complete([])
    assert "upstream-secret-detail" not in str(error.value)
