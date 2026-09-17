import json

import httpx
import pytest

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
        return cloud(next(answers))

    async with api(handler, settings) as client:
        response = await post(client)
    assert response.status_code == 200
    assert response.json()["provider"] == "luna"
    assert len(calls) == 3
    assert "text" in calls[0] and "text" in calls[2]


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


async def test_demo_session_history_isolation_clear_logout_and_csrf():
    settings = configuration(demo_access_code="test-code", allowed_origins="http://test")
    inspected = []

    def handler(request):
        body = json.loads(request.content)
        if "response_format" in body:
            inspected.append(body["messages"][-1]["content"])
            return completion('{"decision":"allow"}', settings)
        return completion('안녕! 함께 이야기하자.', settings)

    async with api(handler, settings) as client:
        assert (await client.post('/session', json={"code": "wrong"})).status_code == 401
        login = await client.post('/session', json={"code": "test-code"})
        assert login.status_code == 200 and 'HttpOnly' in login.headers['set-cookie']
        first_cookie = client.cookies.get('iri_session')
        assert (await client.post('/chat', json={"message": "첫 질문", "age_band": "4-6"})).status_code == 200
        assert (await client.post('/chat', json={"message": "다음 질문", "age_band": "4-6"})).status_code == 200
        assert '첫 질문' in inspected[-2] and '다음 질문' in inspected[-2]
        saved = await client.get('/conversation')
        assert saved.status_code == 200
        assert saved.json()['messages'][0]['content'] == '첫 질문'
        assert (await client.post('/speech', json={"text": "unchecked"})).status_code == 403
        assert (await client.delete('/conversation', headers={"Origin": "https://evil.test"})).status_code == 403
        assert (await client.delete('/conversation')).status_code == 200
        await client.post('/chat', json={"message": "새 질문", "age_band": "4-6"})
        assert '첫 질문' not in inspected[-2]
        await client.post('/session', json={"code": "test-code"})
        await client.post('/chat', json={"message": "다른 사용자", "age_band": "4-6"})
        assert '새 질문' not in inspected[-2]
        await client.delete('/session')
        assert (await client.get('/session')).status_code == 401
        client.cookies.set('iri_session', first_cookie)
        assert (await client.get('/session')).status_code == 200


async def test_login_rate_limit_and_cross_origin_protection():
    async with api(lambda _: pytest.fail("No upstream call"), configuration(demo_access_code="test")) as client:
        assert (await client.post('/session', json={"code": "test"}, headers={"Origin": "https://evil.test"})).status_code == 403
        for _ in range(10):
            assert (await client.post('/session', json={"code": "wrong"})).status_code == 401
        assert (await client.post('/session', json={"code": "test"})).status_code == 429
