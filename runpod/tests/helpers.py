import httpx

from runpod.settings import Settings

MODEL_KEY = "test-only-model-key-" + "y" * 32
REVISION = "a" * 40


def configuration(**updates):
    values = {"model_api_key": MODEL_KEY, "model_revision": REVISION}
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
