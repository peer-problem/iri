import argparse
import asyncio
import hashlib
import json
from typing import get_args

import httpx
import pytest

from runpod.inference.behavior import BehaviorProfile
from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.service import ChatService
from runpod.inference.trace import TurnTrace
from runpod.operations import evaluate
from runpod.operations.data import load_scenarios
from runpod.operations.quality_experiment import verify_stage_traces
from runpod.settings import ROOT
from runpod.tests.helpers import MODEL_KEY, completion, configuration


async def response_with_trace(profile, replies, trace):
    settings = configuration(behavior_profile=profile)
    outputs = iter(replies)
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return completion(next(outputs), settings)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ChatService(ModelProvider(settings, client)).respond(
            "7-10", [{"role": "user", "content": "PRIVATE_QUESTION"}], trace=trace
        )
    return result, requests


@pytest.mark.parametrize("profile", get_args(BehaviorProfile))
@pytest.mark.parametrize("decision", ["allow", "redirect", "support", "clarify"])
@pytest.mark.parametrize("output_decision", ["allow", "block"])
async def test_trace_does_not_change_requests_responses_or_call_count(
    profile, decision, output_decision
):
    replies = [
        json.dumps({"decision": decision}),
        "PRIVATE_ANSWER",
        json.dumps({"decision": output_decision}),
    ]
    if decision == "allow" and profile in {"harm_audit_v50", "legacy_harm_v63"}:
        replies.insert(1, "allow" if profile == "harm_audit_v50" else '{"decision":"allow"}')
    original = await response_with_trace(profile, replies, None)
    trace = TurnTrace()
    observed = await response_with_trace(profile, replies, trace)
    assert observed == original
    result, requests = observed
    snapshot = trace.snapshot()
    assert snapshot["final_action"] == result[1]
    assert snapshot["fallback_used"] == (result[0] != "PRIVATE_ANSWER")
    assert snapshot["stages"]["input_guard"]["decision"] == decision
    ran = [stage for stage in snapshot["stages"].values() if stage["status"] == "completed"]
    assert len(ran) == len(requests)
    assert all(stage["seconds"] >= 0 for stage in ran)
    if len(requests) == 1:
        assert snapshot["stages"]["generation"]["seconds"] is None
        assert snapshot["stages"]["output_guard"]["decision"] is None
    else:
        assert snapshot["stages"]["output_guard"]["decision"] == output_decision
    assert "PRIVATE" not in json.dumps(snapshot)
    assert MODEL_KEY not in json.dumps(snapshot)


@pytest.mark.parametrize("stage_index", [0, 1, 2])
@pytest.mark.parametrize("failure", ["invalid", "timeout", "http", "cancel"])
async def test_failed_stage_is_not_success_and_does_not_leak(stage_index, failure):
    settings = configuration(behavior_profile="safety_v3")
    calls = 0

    def handler(request):
        nonlocal calls
        index = calls
        calls += 1
        if index == stage_index:
            if failure == "timeout":
                raise httpx.ReadTimeout("PRIVATE_EXCEPTION", request=request)
            if failure == "cancel":
                raise asyncio.CancelledError("PRIVATE_EXCEPTION")
            if failure == "http":
                return httpx.Response(500, text="PRIVATE_EXCEPTION")
            return completion("" if index == 1 else "PRIVATE_BAD_JSON", settings)
        return completion("PRIVATE_ANSWER" if index == 1 else '{"decision":"allow"}', settings)

    trace = TurnTrace()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ModelUnavailable, TimeoutError, asyncio.CancelledError)):
            await ChatService(ModelProvider(settings, client)).respond("4-6", [], trace=trace)
    stages = list(trace.snapshot()["stages"].values())
    assert calls == stage_index + 1
    assert stages[stage_index]["status"] == ("interrupted" if failure == "cancel" else "error")
    assert stages[stage_index]["error_code"]
    assert stages[stage_index]["seconds"] >= 0
    assert all(stage["status"] == "not_run" for stage in stages[stage_index + 1 :])
    assert trace.final_action is None and trace.fallback_used is None
    assert "PRIVATE" not in json.dumps(trace.snapshot())


def test_stage_clock_and_snapshots_are_independent(monkeypatch):
    clock = iter([10.0, 10.25])
    monkeypatch.setattr("runpod.inference.trace.time.monotonic", lambda: next(clock))
    first, second = TurnTrace(), TurnTrace()
    with first.measure("input_guard") as stage:
        stage.decision = "allow"
    saved = first.snapshot()
    first.stages["input_guard"].decision = "support"
    assert saved["stages"]["input_guard"]["seconds"] == 0.25
    assert saved["stages"]["input_guard"]["decision"] == "allow"
    assert second.stages["input_guard"].status == "not_run"


async def test_outer_timeout_preserves_interrupted_stage():
    async def handler(request):
        await asyncio.sleep(1)
        pytest.fail("Outer timeout should cancel the model call")

    trace = TurnTrace()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.01):
                await ChatService(ModelProvider(configuration(), client)).respond(
                    "4-6", [], trace=trace
                )
    assert trace.stages["input_guard"].status == "interrupted"
    assert trace.stages["generation"].status == "not_run"
    assert trace.final_action is None


@pytest.mark.parametrize("trace_enabled", [False, True])
@pytest.mark.parametrize("fail_second_turn", [False, True])
async def test_evaluation_sidecar_is_separate_hashed_and_preserves_failed_turn(
    tmp_path, monkeypatch, trace_enabled, fail_second_turn
):
    settings = configuration(behavior_profile="safety_v3")
    generated = {"raw": 0, "guarded": 0}
    in_guarded = False

    def handler(request):
        nonlocal in_guarded
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        body = json.loads(request.content)
        is_guard = "response_format" in body
        if is_guard:
            in_guarded = True
            if (
                fail_second_turn
                and generated["guarded"] == 1
                and "입력 검사기" in body["messages"][0]["content"]
            ):
                return completion("PRIVATE_INVALID_JSON", settings)
            return completion('{"decision":"allow"}', settings)
        mode = "guarded" if in_guarded else "raw"
        generated[mode] += 1
        return completion("PRIVATE_ANSWER", settings)

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        evaluate.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(evaluate, "Settings", lambda: settings)
    item = load_scenarios([ROOT / "data/dev.jsonl"])[-2]
    data = tmp_path / "data.jsonl"
    data.write_text(item.model_dump_json() + "\n", encoding="utf-8")
    args = argparse.Namespace(
        data=data,
        output=tmp_path / "runs",
        mode="both",
        allow_draft=True,
        limit=None,
        trace_stages=trace_enabled,
    )
    assert await evaluate.evaluate(args) == (2 if fail_second_turn else 0)
    run = next(args.output.iterdir())
    rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
    meta = json.loads((run / "metadata.json").read_text())
    assert len(rows) == 2 and len(rows[0]["turns"]) == 2
    assert len(rows[1]["turns"]) == (1 if fail_second_turn else 2)
    assert "stage_trace" not in rows[0]
    trace_path = run / "stage-traces.jsonl"
    assert trace_path.exists() is trace_enabled
    if not trace_enabled:
        return
    assert verify_stage_traces(run, meta, rows) == meta["stage_trace"]
    saved = trace_path.read_text(encoding="utf-8")
    assert "PRIVATE" not in saved and MODEL_KEY not in saved
    traces = [json.loads(line) for line in saved.splitlines()]
    assert [t["turn"] for t in traces[1]["turns"]] == [1, 2]
    assert traces[0]["turns"][0]["stages"]["input_guard"]["status"] == "not_run"
    last = traces[1]["turns"][1]
    assert last["stages"]["input_guard"]["status"] == ("error" if fail_second_turn else "completed")
    assert last["final_action"] == (None if fail_second_turn else "answer")
    assert meta["stage_trace"]["sha256"] == hashlib.sha256(trace_path.read_bytes()).hexdigest()
    # Hash and pair/turn validation are independent of the quality scoring code.
    trace_path.write_text(saved + saved.splitlines()[0] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent"):
        verify_stage_traces(run, meta, rows)
    meta["stage_trace"]["sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="pairs"):
        verify_stage_traces(run, meta, rows)
    traces[1]["turns"].pop()
    trace_path.write_text("".join(json.dumps(row) + "\n" for row in traces), encoding="utf-8")
    meta["stage_trace"]["sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="turns"):
        verify_stage_traces(run, meta, rows)
