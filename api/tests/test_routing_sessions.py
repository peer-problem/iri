import json

import httpx
import pytest

from api.app.answer_profile import ANSWER_PROFILE
from api.app.service import generation_messages
from api.tests.test_api import api, completion, configuration, post


def cloud(text, status="completed"):
    return httpx.Response(200, json={"status": status, "output": [
        {"type": "message", "content": [{"type": "output_text", "text": text}]}
    ]})


@pytest.mark.parametrize("primary_failure", ["offline", "generation", "timeout"])
async def test_fallback_restarts_entire_guarded_pipeline(primary_failure):
    settings = configuration(openai_api_key="test-cloud", primary_timeout_seconds=0.1)
    answers = iter(['{"decision":"allow"}', '달은 지구 주위를 돌아.', '{"decision":"allow"}'])
    calls = []

    def handler(request):
        if request.url.path == "/v1/models":
            if primary_failure == "offline":
                raise httpx.ConnectError("offline")
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        if request.url.path == "/v1/chat/completions":
            if primary_failure == "timeout":
                raise httpx.ReadTimeout("timeout")
            return httpx.Response(503)
        body = json.loads(request.content)
        calls.append(body)
        assert body["model"] == "gpt-5.6-luna"
        assert body["reasoning"] == {"effort": "high"}
        assert body["store"] is False
        expected_budget = 848 if "text" in body else 1536
        assert body["max_output_tokens"] == expected_budget
        return cloud(next(answers))

    async with api(handler, settings) as client:
        response = await post(client)
    assert response.status_code == 200
    assert response.json()["provider"] == "luna"
    assert len(calls) == 3
    assert "text" in calls[0] and "text" in calls[2]
    marker = f"[AnswerProfile {ANSWER_PROFILE.version}]"
    system_messages = [call["input"][0]["content"] for call in calls]
    assert marker not in system_messages[0]
    assert ANSWER_PROFILE.prompt in system_messages[1]
    assert marker not in system_messages[2]
    assert calls[1]["input"] == generation_messages(
        "4-6", [{"role": "user", "content": "비는 왜 내려?"}]
    )


async def test_ready_primary_does_not_call_cloud():
    settings = configuration(openai_api_key="test-cloud")
    answers = iter(['{"decision":"allow"}', '안녕!', '{"decision":"allow"}'])

    def handler(request):
        assert request.url.host == "127.0.0.1"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        return completion(next(answers), settings)

    async with api(handler, settings) as client:
        response = await post(client)
    assert response.json()["provider"] == "kanana"


@pytest.mark.parametrize("verdict", ['not-json', '{"decision":"block"}'])
async def test_fallback_never_releases_unchecked_answer(verdict):
    answers = iter(['{"decision":"allow"}', 'PRIVATE_UNCHECKED', verdict])
    def handler(request):
        if request.url.path == "/v1/models":
            return httpx.Response(503)
        return cloud(next(answers))
    async with api(handler, configuration(openai_api_key="test-cloud")) as client:
        response = await post(client)
    assert 'PRIVATE_UNCHECKED' not in response.text


async def test_anonymous_session_history_isolation_clear_and_csrf():
    settings = configuration(allowed_origins="http://test")
    inspected = []

    def handler(request):
        body = json.loads(request.content)
        if "response_format" in body:
            inspected.append(body["messages"][-1]["content"])
            return completion('{"decision":"allow"}', settings)
        return completion('안녕! 함께 이야기하자.', settings)

    async with api(handler, settings) as client:
        landing = await client.get('/conversation')
        assert landing.status_code == 200
        assert landing.json()['messages'] == []
        assert 'set-cookie' not in landing.headers
        assert client.cookies.get('iri_session') is None
        first = await client.post('/chat', json={"message": "첫 질문", "age_band": "4-6"})
        assert first.status_code == 200 and 'HttpOnly' in first.headers['set-cookie']
        first_cookie = client.cookies.get('iri_session')
        assert (await client.post('/chat', json={"message": "다음 질문", "age_band": "4-6"})).status_code == 200
        assert '첫 질문' in inspected[-2] and '다음 질문' in inspected[-2]
        saved = await client.get('/conversation')
        assert saved.status_code == 200
        assert saved.json()['messages'][0]['content'] == '첫 질문'
        assert saved.json()['messages'][1]['provider'] == 'kanana'
        assert (await client.post('/speech', json={"text": "unchecked"})).status_code == 403
        assert (await client.post('/speech-stream', json={"text": "unchecked"})).status_code == 403
        assert (await client.delete('/conversation', headers={"Origin": "https://evil.test"})).status_code == 403
        assert (await client.delete('/conversation')).status_code == 200
        await client.post('/chat', json={"message": "새 질문", "age_band": "4-6"})
        assert '첫 질문' not in inspected[-2]
        client.cookies.clear()
        fresh = await client.get('/conversation')
        assert fresh.json()['messages'] == []
        assert 'set-cookie' not in fresh.headers
        await client.post('/chat', json={"message": "다른 사용자", "age_band": "4-6"})
        assert '새 질문' not in inspected[-2]
        assert (await client.get('/session')).status_code == 404
        client.cookies.clear()
        client.cookies.set('iri_session', first_cookie)
        restored = await client.get('/conversation')
        assert restored.status_code == 200
        assert restored.json()['messages'][0]['content'] == '새 질문'


async def test_anonymous_mutation_rejects_cross_origin_requests_without_creating_session():
    async with api(lambda _: pytest.fail("No upstream call"), configuration()) as client:
        response = await client.post(
            '/chat',
            json={"message": "질문", "age_band": "4-6"},
            headers={"Origin": "https://evil.test"},
        )
    assert response.status_code == 403
    assert 'set-cookie' not in response.headers


def test_anonymous_session_creation_is_rate_limited_per_ip():
    from starlette.requests import Request

    from api.app.sessions import SESSION_CREATE_LIMIT, Sessions

    sessions = Sessions(configuration())
    request = Request({"type": "http", "client": ("203.0.113.9", 9000), "headers": []})
    for _ in range(SESSION_CREATE_LIMIT):
        sessions.create(request)
    with pytest.raises(Exception) as caught:
        sessions.create(request)
    assert getattr(caught.value, "status_code", None) == 429


def test_ip_rate_limit_cannot_be_bypassed_with_fresh_sessions():
    from starlette.requests import Request

    from api.app.sessions import IP_CALL_LIMIT, Session, Sessions

    sessions = Sessions(configuration())
    request = Request({"type": "http", "client": ("203.0.113.8", 9000), "headers": []})
    first = Session(expires=10**12)
    second = Session(expires=10**12)
    for index in range(IP_CALL_LIMIT):
        sessions.limit(first if index % 2 else second, request)
    with pytest.raises(Exception) as caught:
        sessions.limit(Session(expires=10**12), request)
    assert getattr(caught.value, "status_code", None) == 429


@pytest.mark.parametrize(
    "profile",
    ["kanana_v3", "kanana_v4", "kanana_v5"],
)
def test_product_and_harness_use_the_same_generation_contract(profile):
    from runpod.inference.messages import generation_messages as harness_messages

    history = [{"role": "user", "content": "비는 왜 내려?"}]
    assert generation_messages("4-6", history, profile) == harness_messages(
        "4-6", history, profile
    )
    assert generation_messages("4-6", history, profile, support=True) == harness_messages(
        "4-6", history, profile, support=True
    )
