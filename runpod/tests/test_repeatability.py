import json

import httpx
import pytest

from runpod.operations import repeatability
from runpod.operations.data import load_scenarios
from runpod.operations.serve_model import build_command
from runpod.settings import ROOT
from runpod.tests.helpers import completion, configuration


def test_probe_does_not_count_errors_or_missing_rows_as_repeatability():
    row = {"id": "a", "pass": 0, "request_sha256": "request", "answer_sha256": "one", "error": None}
    with pytest.raises(ValueError, match="Missing or duplicate"):
        repeatability.summarize([row, row], ["a"], 2)
    changed = {**row, "pass": 1, "answer_sha256": "two"}
    assert repeatability.summarize([row, changed], ["a"], 2)["response_mismatch_ids"] == ["a"]
    failed = {**changed, "error": "timeout", "answer_sha256": None}
    summary = repeatability.summarize([row, failed], ["a"], 2)
    assert summary["error_ids"] == ["a"]
    assert summary["observed_repeatable"] is False
    assert summary["response_mismatch_ids"] == []


async def test_probe_records_identical_request_bytes_and_reversed_order(tmp_path):
    settings = configuration()
    data = tmp_path / "reviewed-fixture.jsonl"
    data.write_text(
        "".join(
            item.model_copy(update={"review_status": "reviewed"}).model_dump_json() + "\n"
            for item in load_scenarios([ROOT / "data/dev.jsonl"])
        )
    )
    launch = tmp_path / "launch.json"
    launch.write_text(json.dumps({"revision": settings.model_revision, "variant": "base"}))
    requests = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        requests.append(json.loads(request.content))
        return completion("same answer", settings)

    output = tmp_path / "probe"
    summary = await repeatability.run(
        data, output, launch, passes=2, settings=settings, transport=httpx.MockTransport(handler)
    )
    rows = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 40
    assert [r["id"] for r in rows[:20]] == [r["id"] for r in rows[20:]][::-1]
    assert requests[:20] == requests[20:][::-1]
    assert summary["observed_repeatable"] is True
    assert "authorization" not in (output / "results.jsonl").read_text().lower()


async def test_draft_probe_refused_before_creating_output(tmp_path):
    with pytest.raises(ValueError, match="reviewed"):
        await repeatability.run(
            ROOT / "data/dev.jsonl", tmp_path / "probe", tmp_path / "missing.json"
        )
    assert not (tmp_path / "probe").exists()


def test_prefix_caching_options_are_explicit_and_default_unchanged():
    base = build_command(configuration(), "/bin/vllm")
    assert not any("prefix-caching" in argument for argument in base)
    assert build_command(configuration(), "/bin/vllm", prefix_caching="off") == base + [
        "--no-enable-prefix-caching"
    ]
    assert build_command(configuration(), "/bin/vllm", prefix_caching="on") == base + [
        "--enable-prefix-caching"
    ]
