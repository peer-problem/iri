import argparse
import json

import httpx
import pytest

from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.operations import evaluate
from runpod.operations.compare import compare
from runpod.operations.data import (
    load_scenarios,
    validate_development,
    validate_final,
    validate_final_manifest,
)
from runpod.operations.experiments import evaluation_identity
from runpod.operations.serve_model import build_command
from runpod.settings import ROOT
from runpod.tests.helpers import completion, configuration


def test_development_data_is_balanced_and_has_explicit_review_status():
    items = load_scenarios([(ROOT / "data/dev.jsonl")])
    validate_development(items)
    assert all(item.review_status in {"draft", "reviewed"} for item in items)
    assert all(item.source_id == "team-authored-dev-v1" for item in items)


@pytest.mark.parametrize("mutation", ["duplicate", "scenario_leak", "text_leak", "bad_turns"])
def test_dataset_rejects_corruption_and_leaks(tmp_path, mutation):
    original = load_scenarios([(ROOT / "data/dev.jsonl")])[0].model_dump()
    modified = {**original, "id": "new-id"}
    if mutation == "duplicate":
        modified["id"] = original["id"]
    elif mutation == "scenario_leak":
        modified["split"] = "test"
        modified["inputs"] = ["다른 연령 표현"]
    elif mutation == "text_leak":
        modified.update(split="test", scenario_id="different-group")
    else:
        modified["expected_actions"] = []
    path = tmp_path / "data.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in [original, modified]))
    with pytest.raises(ValueError):
        load_scenarios([path])


async def test_real_evaluation_requires_explicit_draft_opt_in(tmp_path):
    dataset = tmp_path / "draft.jsonl"
    item = load_scenarios([(ROOT / "data/dev.jsonl")])[0]
    dataset.write_text(item.model_copy(update={"review_status": "draft"}).model_dump_json() + "\n")
    output = tmp_path / "results"
    args = argparse.Namespace(
        data=dataset, output=output, allow_draft=False, limit=None, mode="both"
    )
    with pytest.raises(ValueError, match="Scenario review"):
        await evaluate.evaluate(args)
    assert not output.exists()


def test_final_validation_rejects_dev_data_and_unreviewed_scenarios():
    dev = load_scenarios([(ROOT / "data/dev.jsonl")])
    with pytest.raises(ValueError, match="300 final"):
        validate_final(dev)
    paired = []
    for index in range(150):
        for age in ("4-6", "7-10"):
            original = dev[0]
            paired.append(
                original.model_copy(
                    update={
                        "id": f"final-{index}-{age}",
                        "scenario_id": f"final-group-{index}",
                        "split": "test",
                        "age_band": age,
                        "review_status": "draft",
                    }
                )
            )
    with pytest.raises(ValueError, match="category distribution"):
        validate_final(paired)


def test_final_v1_has_direct_review_and_locked_bytes(tmp_path):
    data = ROOT / "data/final_v1.jsonl"
    items = load_scenarios([ROOT / "data/dev.jsonl", data])
    final = [item for item in items if item.split == "test"]
    validate_final(final)
    assert validate_final_manifest(data)["groups"] == 150
    copied = tmp_path / data.name
    copied.write_bytes(data.read_bytes() + b"\n")
    (tmp_path / "final_v1_manifest.json").write_bytes(
        (ROOT / "data/final_v1_manifest.json").read_bytes()
    )
    with pytest.raises(ValueError, match="differs"):
        validate_final_manifest(copied)


async def test_qwen_candidate_uses_pinned_model_identity_and_sampling():
    settings = configuration(model_profile="qwen3_4b_instruct_2507")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return completion("답변", settings)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelProvider(settings, client)
        assert await provider.complete([{"role": "user", "content": "안녕"}]) == "답변"
        assert (
            await provider.complete(
                [{"role": "user", "content": "검사"}],
                guard=True,
                response_schema={"type": "object"},
            )
            == "답변"
        )
    assert settings.profile["model_id"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert calls[0]["temperature"] == 0.7
    assert calls[0]["top_p"] == 0.8 and calls[0]["top_k"] == 20
    assert calls[1]["temperature"] == 0 and "top_k" not in calls[1]
    assert evaluation_identity(settings)["model_id"] == settings.profile["model_id"]


async def test_evaluation_refuses_unreachable_model_without_fake_results(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate, "Settings", lambda: configuration(model_revision=""))
    args = argparse.Namespace(
        data=(ROOT / "data/dev.jsonl"), output=tmp_path, allow_draft=True, limit=1, mode="both"
    )
    with pytest.raises(ModelUnavailable):
        await evaluate.evaluate(args)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("profile", ["baseline", "legacy_harm_v63"])
async def test_evaluation_records_independent_multiturn_histories(tmp_path, monkeypatch, profile):
    settings = configuration(behavior_profile=profile)
    calls = []

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        body = json.loads(request.content)
        calls.append(body)
        prompt = body["messages"][0]["content"]
        if "입력 검사기" in prompt or "출력 검사기" in prompt:
            return completion('{"decision":"allow"}', settings)
        return completion(f"TEST_RESPONSE_{len(calls)}", settings)

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        evaluate.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(evaluate, "Settings", lambda: settings)
    item = load_scenarios([(ROOT / "data/dev.jsonl")])[-2]
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(item.model_dump_json() + "\n")
    output = tmp_path / "runs"
    args = argparse.Namespace(
        data=dataset, output=output, allow_draft=True, limit=None, mode="both"
    )
    assert await evaluate.evaluate(args) == 0
    run_dir = next(output.iterdir())
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    assert all(len(row["turns"]) == 2 for row in rows)
    assert rows[0]["action_match"] is None
    assert rows[1]["action_match"] is True
    raw_first = rows[0]["turns"][0]["answer"]
    guarded_calls = calls[2:]
    assert raw_first not in json.dumps(guarded_calls)
    assert (run_dir / "review.csv").exists()
    assert settings.model_api_key.get_secret_value() not in (run_dir / "metadata.json").read_text()
    metadata = json.loads((run_dir / "metadata.json").read_text())
    assert metadata["input_recheck_response_format"] == (
        "json_schema" if profile == "legacy_harm_v63" else None
    )


def test_summary_does_not_count_errors_as_success_or_raw_actions():
    rows = [
        {"mode": "guarded", "age_band": "4-6", "error": None, "action_match": True, "seconds": 1},
        {
            "mode": "guarded",
            "age_band": "4-6",
            "error": "TimeoutError",
            "action_match": False,
            "seconds": 90,
        },
        {"mode": "raw", "age_band": "7-10", "error": None, "action_match": None, "seconds": 2},
    ]
    result = evaluate.summarize(rows)
    assert result["guarded/all"]["errors"] == 1
    assert result["guarded/all"]["action_matches"] == 1
    assert result["guarded/all"]["p95_seconds"] == 1
    assert result["raw/all"]["action_matches"] is None


def test_comparison_rejects_different_data(tmp_path):
    paths = []
    for index in range(2):
        path = tmp_path / str(index)
        path.mkdir()
        (path / "metadata.json").write_text(json.dumps({"data_sha256": str(index)}))
        (path / "summary.json").write_text("{}")
        paths.append(path)
    with pytest.raises(ValueError, match="data_sha256"):
        compare(paths)


def test_gpu_launcher_uses_pinned_revision_local_bind_and_no_key_in_command():
    settings = configuration(model_serve_port=8123)
    command = build_command(settings, "/path/to/vllm")
    assert command[command.index("--revision") + 1] == settings.model_revision
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "8123"
    assert command[command.index("--dtype") + 1] == "bfloat16"
    assert "--no-enable-log-requests" in command
    assert settings.model_api_key.get_secret_value() not in " ".join(command)


async def test_evaluation_records_safe_failure_diagnostics(tmp_path, monkeypatch):
    settings = configuration()

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        return completion("PRIVATE_INVALID_VERDICT", settings)

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        evaluate.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(evaluate, "Settings", lambda: settings)
    args = argparse.Namespace(
        data=ROOT / "data/dev.jsonl", output=tmp_path, allow_draft=True, limit=1, mode="guarded"
    )
    assert await evaluate.evaluate(args) == 2
    run = next(tmp_path.iterdir())
    row = json.loads((run / "results.jsonl").read_text())
    assert row["error_detail"] == {"code": "invalid_verdict", "stage": "input_guard", "turn": 1}
    assert "PRIVATE_INVALID_VERDICT" not in (run / "results.jsonl").read_text()
    assert (
        json.loads((run / "metadata.json").read_text())["generation"]["guard_response_format"]
        == "json_schema"
    )


async def test_evaluation_identifies_second_turn_upstream_status_without_body(
    tmp_path, monkeypatch
):
    settings = configuration()
    calls = 0

    def handler(request):
        nonlocal calls
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        calls += 1
        if calls == 4:
            return httpx.Response(422, text="PRIVATE_UPSTREAM_ERROR_BODY")
        body = json.loads(request.content)
        if "response_format" in body:
            return completion('{"decision":"allow"}', settings)
        return completion("첫 질문에 답했어.", settings)

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        evaluate.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(evaluate, "Settings", lambda: settings)
    item = next(item for item in load_scenarios([ROOT / "data/dev.jsonl"]) if item.id == "dev-092")
    data = tmp_path / "dev-092.jsonl"
    data.write_text(item.model_dump_json() + "\n", encoding="utf-8")
    args = argparse.Namespace(
        data=data,
        output=tmp_path / "runs",
        allow_draft=True,
        limit=None,
        mode="guarded",
        trace_stages=True,
    )

    assert await evaluate.evaluate(args) == 2
    run = next(args.output.iterdir())
    row = json.loads((run / "results.jsonl").read_text(encoding="utf-8"))
    assert len(row["turns"]) == 1
    assert row["error_detail"] == {
        "code": "upstream_http_error",
        "stage": "input_guard",
        "turn": 2,
        "http_status": 422,
    }
    trace = json.loads((run / "stage-traces.jsonl").read_text(encoding="utf-8"))
    assert trace["turns"][1]["stages"]["input_guard"]["status"] == "error"
    assert "PRIVATE_UPSTREAM_ERROR_BODY" not in (run / "results.jsonl").read_text()
