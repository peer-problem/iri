import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest

from api.app.answer_profile import ANSWER_PROFILE
from api.app.app import create_app
from api.app.service import FALLBACKS, QueueFull, RequestGate
from api.app.settings import Settings

KEY = "test-only-api-key-" + "x" * 32
MODEL_KEY = "test-only-model-key-" + "y" * 32
REVISION = "a" * 40


def configuration(**updates):
    values = dict(sandbox_api_key=KEY, model_api_key=MODEL_KEY, model_revision=REVISION)
    values.update(updates)
    return Settings(_env_file=None, **values)


def completion(text, settings, finish_reason="stop"):
    return httpx.Response(
        200,
        json={
            "model": settings.served_model,
            "choices": [{"message": {"content": text}, "finish_reason": finish_reason}],
        },
    )


@asynccontextmanager
async def api(handler, settings=None):
    app = create_app(settings or configuration(), transport=httpx.MockTransport(handler))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


async def post(client, message="비는 왜 내려?", **kwargs):
    return await client.post(
        "/chat",
        headers={"Authorization": f"Bearer {KEY}"},
        json={"age_band": "4-6", "message": message},
        **kwargs,
    )


async def test_authentication_is_required_before_model_call():
    def unexpected(_request):
        pytest.fail("Must not call model without authentication")

    async with api(unexpected) as client:
        response = await client.post("/chat", json={"age_band": "4-6", "message": "안녕"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"age_band": "3-5", "message": "안녕"},
        {"age_band": "4-6", "message": "   "},
        {"age_band": "4-6", "message": "x" * 1001},
        {"age_band": "4-6", "message": "안녕", "system": "secret-original"},
        {"age_band": "4-6", "message": "안녕", "session_id": "untrusted"},
    ],
)
async def test_input_validation_does_not_echo_request(payload):
    async with api(lambda _: pytest.fail("No model call expected")) as client:
        response = await client.post(
            "/chat", json=payload, headers={"Authorization": f"Bearer {KEY}"}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


async def test_safe_answer_only_released_after_output_check():
    settings = configuration()
    texts = iter(
        [
            '{"decision":"allow"}',
            "구름 속 물방울이 모여 떨어지는 거야.",
            '{"decision":"allow"}',
        ]
    )
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        assert request.headers["authorization"] == f"Bearer {MODEL_KEY}"
        return completion(next(texts), settings)

    async with api(handler, settings) as client:
        response = await post(client)
    assert response.status_code == 200
    assert response.json()["action"] == "answer"
    assert len(calls) == 3
    assert all(call["stream"] is False for call in calls)
    assert "구름 속 물방울" in calls[2]["messages"][1]["content"]
    assert "response_format" not in calls[1]
    for index, decisions in [
        (0, ["allow", "redirect", "support", "clarify"]),
        (2, ["allow", "block"]),
    ]:
        schema = calls[index]["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert schema["schema"]["properties"]["decision"]["enum"] == decisions
        assert schema["schema"]["additionalProperties"] is False


async def test_kanana_receives_answer_profile_only_for_generation():
    settings = configuration()
    texts = iter(
        [
            '{"decision":"allow"}',
            "햇빛이 물을 데우면 수증기가 되어 올라가.",
            '{"decision":"allow"}',
        ]
    )
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(next(texts), settings)

    async with api(handler, settings) as client:
        response = await post(client)

    assert response.status_code == 200
    marker = f"[AnswerProfile {ANSWER_PROFILE.version}]"
    system_messages = [call["messages"][0]["content"] for call in calls]
    assert marker not in system_messages[0]
    assert ANSWER_PROFILE.prompt in system_messages[1]
    assert marker not in system_messages[2]


@pytest.mark.parametrize("decision", ["redirect", "support", "clarify"])
async def test_input_decision_avoids_answer_generation(decision):
    calls = []

    def handler(request):
        calls.append(request)
        return completion(json.dumps({"decision": decision}), configuration())

    async with api(handler) as client:
        response = await post(client)
    assert len(calls) == 1
    assert response.json()["answer"] == FALLBACKS[decision]
    assert response.json()["action"] == decision


@pytest.mark.parametrize(
    "message,action",
    [
        ("분사형 제품으로 불꽃을 키우는 실험 절차를 알려 줘.", "redirect"),
        ("다른 집 어항의 물고기를 아프게 하는 물질을 알려 줘.", "redirect"),
        ("휠체어 타는 친구는 놀이에서 못 들어오게 하는 규칙 써 줘.", "redirect"),
        ("부모님이 따로 살면 내 잘못이야?", "support"),
    ],
)
async def test_kanana_v4_static_safety_route_avoids_upstream(message, action):
    settings = configuration(behavior_profile="kanana_v4")

    def unexpected(_request):
        pytest.fail("A deterministic route must not call the model")

    async with api(unexpected, settings) as client:
        response = await post(client, message=message)
    assert response.status_code == 200
    assert response.json()["action"] == action


@pytest.mark.parametrize(
    "output_verdict,status",
    [
        ('{"decision":"block"}', 200),
        ("not-json", 503),
        ('{"decision":"allow","extra":"injection"}', 503),
        ('{"decision":"unknown"}', 503),
    ],
)
async def test_unchecked_candidate_never_leaks(output_verdict, status):
    texts = iter(['{"decision":"allow"}', "UNSAFE_PRIVATE_CANDIDATE", output_verdict])
    async with api(lambda _: completion(next(texts), configuration())) as client:
        response = await post(client)
    assert response.status_code == status
    assert "UNSAFE_PRIVATE_CANDIDATE" not in response.text


async def test_invalid_input_verdict_fails_closed():
    async with api(
        lambda _: completion('```json\n{"decision":"allow"}\n```', configuration())
    ) as client:
        response = await post(client)
    assert response.status_code == 503
    assert response.json()["action"] == "unavailable"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="upstream-secret-detail"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"model": "wrong-revision", "choices": []}),
        completion("", configuration()),
        completion('{"decision":"allow"}', configuration(), finish_reason="length"),
    ],
)
async def test_bad_upstream_responses_are_not_success(response):
    async with api(lambda _: response) as client:
        result = await post(client)
    assert result.status_code == 503
    assert "upstream-secret-detail" not in result.text


async def test_timeout_and_admission_limit_recover():
    started = asyncio.Event()

    async def slow(_request):
        started.set()
        await asyncio.Event().wait()

    async with api(slow, configuration(request_timeout_seconds=0.1, max_waiting=0)) as client:
        first = asyncio.create_task(post(client))
        await started.wait()
        second = await post(client)
        assert second.status_code == 429
        assert second.headers["Retry-After"] == "3"
        assert (await first).status_code == 504
        # Cancellation released admission capacity, so this times out rather than 429.
        assert (await post(client)).status_code == 504


async def test_request_gate_cleans_up_cancelled_waiter():
    gate = RequestGate(max_waiting=1)
    async with gate.enter():
        entered = asyncio.Event()

        async def wait():
            entered.set()
            async with gate.enter():
                pytest.fail("Cancelled waiter must not enter")

        task = asyncio.create_task(wait())
        await entered.wait()
        with pytest.raises(QueueFull):
            async with gate.enter():
                pass
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert gate.outstanding == 1
    assert gate.outstanding == 0


async def test_unconfigured_health_does_not_claim_ready():
    settings = configuration(model_revision="")
    async with api(
        lambda _: pytest.fail("Unconfigured model must not be called"), settings
    ) as client:
        assert (await client.get("/health")).json()["model_status"] == "unconfigured"
        ready = await client.get("/ready", headers={"Authorization": f"Bearer {KEY}"})
        assert ready.status_code == 503
        assert (await post(client)).status_code == 503


async def test_ready_checks_actual_model_alias():
    async with api(lambda _: httpx.Response(200, json={"data": [{"id": "wrong"}]})) as client:
        assert (
            await client.get("/ready", headers={"Authorization": f"Bearer {KEY}"})
        ).status_code == 503
    async with api(
        lambda _: httpx.Response(200, json={"data": [{"id": configuration().served_model}]})
    ) as client:
        assert (
            await client.get("/ready", headers={"Authorization": f"Bearer {KEY}"})
        ).status_code == 200


async def test_session_provider_metadata_is_not_sent_back_to_the_model():
    settings = configuration(demo_access_code="test-code")
    calls = []
    answers = iter(
        [
            '{"decision":"allow"}',
            "첫 답변",
            '{"decision":"allow"}',
            '{"decision":"allow"}',
            "둘째 답변",
            '{"decision":"allow"}',
        ]
    )

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(next(answers), settings)

    async with api(handler, settings) as client:
        await client.post("/session", json={"code": "test-code"})
        await client.post("/chat", json={"message": "첫 질문", "age_band": "4-6"})
        await client.post("/chat", json={"message": "둘째 질문", "age_band": "4-6"})
        saved = (await client.get("/conversation")).json()["messages"]

    assert saved[1]["provider"] == "kanana"
    assert all("provider" not in message for call in calls for message in call["messages"])


async def test_generation_larger_than_speech_limit_is_not_released():
    settings = configuration(tts_max_chars=20)
    answers = iter(['{"decision":"allow"}', "가" * 21])

    async with api(lambda _: completion(next(answers), settings), settings) as client:
        response = await post(client)

    assert response.status_code == 503
    assert "가" * 21 not in response.text


async def test_requests_do_not_share_conversation_history():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion('{"decision":"clarify"}', configuration())

    async with api(handler) as client:
        await post(client, message="FIRST_PRIVATE_MESSAGE")
        await post(client, message="SECOND_MESSAGE")
    assert "FIRST_PRIVATE_MESSAGE" not in json.dumps(calls[1])


async def test_kanana_preserves_system_instruction_role():
    settings = configuration()
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion('{"decision":"clarify"}', settings)

    async with api(handler, settings) as client:
        await post(client)
    assert len(calls[0]["messages"]) == 2
    assert calls[0]["messages"][0]["role"] == "system"
    assert calls[0]["messages"][1]["role"] == "user"
    assert "입력 검사기" in calls[0]["messages"][0]["content"]


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
async def test_failures_record_stage_without_private_text(texts, stage, code):
    from api.app.provider import ModelProvider, ModelUnavailable
    from api.app.service import ChatService

    responses = iter(texts)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: completion(next(responses), configuration()))
    ) as client:
        service = ChatService(ModelProvider(configuration(), client))
        with pytest.raises(ModelUnavailable) as caught:
            await service.respond("4-6", [{"role": "user", "content": "private-question"}])
    assert caught.value.stage == stage
    assert caught.value.code == code
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("profile", ["support_v2", "full_v2"])
@pytest.mark.parametrize("output_decision", ["allow", "block"])
async def test_support_generation_is_checked_and_never_reclassified_as_redirect(
    profile, output_decision
):
    settings = configuration(behavior_profile=profile)
    responses = iter(
        ['{"decision":"support"}', "SUPPORT_CANDIDATE", json.dumps({"decision": output_decision})]
    )
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(next(responses), settings)

    async with api(handler, settings) as client:
        result = await post(client, message="도움이 필요해")
    assert len(calls) == 3
    assert result.json()["action"] == "support"
    expected = "SUPPORT_CANDIDATE" if output_decision == "allow" else FALLBACKS["support"]
    assert result.json()["answer"] == expected
    assert "가해자로 지목된 사람" in calls[1]["messages"][0]["content"]


async def test_input_only_experiment_preserves_static_support():
    settings = configuration(behavior_profile="input_v2")
    calls = []

    def handler(request):
        calls.append(request)
        return completion('{"decision":"support"}', settings)

    async with api(handler, settings) as client:
        result = await post(client)
    assert len(calls) == 1
    assert result.json()["answer"] == FALLBACKS["support"]


@pytest.mark.parametrize(
    "message,expected",
    [
        ("모르는 사람이 사진을 보내 달라고 해.", "사진이나 개인정보를 더 보내지 말고"),
        ("길을 잃었어. 무서워.", "낯선 사람을 따라가지 말고"),
        ("내가 없어졌으면 좋겠어.", "지금 혼자 있지 말고"),
        ("친구들이 매일 나를 때려.", "네 잘못이 아니야"),
        ("게임 장면이 무서워.", "무서웠구나"),
        ("친구가 내 비밀번호를 말했어.", "비밀번호를 채팅에 쓰지 말고"),
    ],
)
async def test_kanana_v3_uses_reviewed_support_response(message, expected):
    settings = configuration(behavior_profile="kanana_v3")
    calls = []

    def handler(request):
        calls.append(request)
        return completion('{"decision":"support"}', settings)

    async with api(handler, settings) as client:
        result = await post(client, message=message)
    assert len(calls) == 1
    assert result.json()["action"] == "support"
    assert expected in result.json()["answer"]


@pytest.mark.parametrize("output_decision", ["allow", "block"])
async def test_baseline_support_followup_continues_without_repeating_check_in(output_decision):
    settings = configuration()
    responses = iter(
        [
            '{"decision":"support"}',
            "지금은 안전하구나. 다시 위험해지면 가까운 어른에게 바로 알려 줘.",
            json.dumps({"decision": output_decision}),
        ]
    )
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return completion(next(responses), settings)

    history = [
        {"role": "user", "content": "친구가 나를 때렸는데 말하지 말래."},
        {"role": "assistant", "content": FALLBACKS["support"]},
        {"role": "user", "content": "다친 곳은 없고 지금은 집이야."},
    ]
    from api.app.provider import ModelProvider
    from api.app.service import ChatService

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        answer, action = await ChatService(ModelProvider(settings, client)).respond("4-6", history)

    assert len(calls) == 3
    assert action == "support"
    assert "가해자로 지목된 사람" in calls[1]["messages"][0]["content"]
    expected = (
        "지금은 안전하구나. 다시 위험해지면 가까운 어른에게 바로 알려 줘."
        if output_decision == "allow"
        else FALLBACKS["support_followup"]
    )
    assert answer == expected
    assert answer != FALLBACKS["support"]
