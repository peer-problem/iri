import argparse
import json
from pathlib import Path

import httpx
import pytest

from backend.provider import ModelUnavailable
from scripts import evaluate
from scripts.compare import compare
from scripts.data import load_scenarios, validate_development
from scripts.serve_model import build_command
from tests.test_api import completion, configuration


def test_development_data_is_balanced_and_explicitly_draft():
    items = load_scenarios([Path("data/dev.jsonl")])
    validate_development(items)
    assert all(item.review_status == "draft" for item in items)
    assert all(item.source_id == "team-authored-dev-v1" for item in items)


@pytest.mark.parametrize("mutation", ["duplicate", "scenario_leak", "text_leak", "bad_turns"])
def test_dataset_rejects_corruption_and_leaks(tmp_path, mutation):
    original = load_scenarios([Path("data/dev.jsonl")])[0].model_dump()
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
    args = argparse.Namespace(
        data=Path("data/dev.jsonl"), output=tmp_path, allow_draft=False, limit=None, mode="both"
    )
    with pytest.raises(ValueError, match="Human review"):
        await evaluate.evaluate(args)
    assert not list(tmp_path.iterdir())


async def test_evaluation_refuses_unreachable_model_without_fake_results(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate, "Settings", lambda: configuration(model_revision=""))
    args = argparse.Namespace(
        data=Path("data/dev.jsonl"), output=tmp_path, allow_draft=True, limit=1, mode="both"
    )
    with pytest.raises(ModelUnavailable):
        await evaluate.evaluate(args)
    assert not list(tmp_path.iterdir())


async def test_evaluation_records_independent_multiturn_histories(tmp_path, monkeypatch):
    settings = configuration()
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
    item = load_scenarios([Path("data/dev.jsonl")])[-2]
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
    settings = configuration(model_profile="gemma")
    command = build_command(settings, "/path/to/vllm")
    assert command[command.index("--revision") + 1] == settings.model_revision
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert "--language-model-only" in command
    assert "--no-enable-log-requests" in command
    assert settings.model_api_key.get_secret_value() not in " ".join(command)
