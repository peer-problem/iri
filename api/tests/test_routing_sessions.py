import json

import httpx
import pytest

from api.tests.test_api import api, completion, configuration, post


@pytest.mark.parametrize("failure", ["offline", "generation", "timeout"])
async def test_unavailable_kanana_never_calls_another_answer_model(failure):
    settings = configuration(openai_api_key="test-speech-key", primary_timeout_seconds=0.1)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        assert request.url.host == "127.0.0.1"
        if failure == "offline":
            raise httpx.ConnectError("offline")
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(503)

    async with api(handler, settings) as client:
        response = await post(client)
    assert response.status_code in {503, 504}
    assert response.json()["provider"] == "unavailable"
    assert calls and all("api.openai.com" not in call for call in calls)


async def test_ready_primary_uses_kanana():
    settings = configuration(openai_api_key="test-speech-key")
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
async def test_kanana_never_releases_unchecked_answer(verdict):
    answers = iter(['{"decision":"allow"}', 'PRIVATE_UNCHECKED', verdict])
    def handler(request):
        assert request.url.host == "127.0.0.1"
        return completion(next(answers), configuration())
    async with api(handler, configuration(openai_api_key="test-speech-key")) as client:
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
        assert (await client.post('/speech-stream', json={"text": "unchecked"})).status_code == 403
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
