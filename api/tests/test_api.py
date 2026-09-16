import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest

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
