import csv
import json

import httpx
import pytest

from api.app.provider import ModelProvider, ModelUnavailable
from api.app.service import POLICY, ChatService
from runpod.operations.development_review import export, import_labels
from runpod.operations.experiments import digest, evaluation_identity
from runpod.operations.rescore import rescore
from runpod.operations.review import aggregate, export_packets
from runpod.operations.serve_model import build_command
from runpod.operations.verify_serving import verify
from runpod.settings import ROOT
from runpod.tests.helpers import configuration
from runpod.tests.test_preparation import training_row
from runpod.tests.test_review import make_run, rate


async def test_adapter_generation_and_base_guards_are_routed_separately():
    settings = configuration(adapter_name="test-adapter")
    calls = []

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200, json={"data": [{"id": settings.served_model}, {"id": settings.adapter_name}]}
            )
        body = json.loads(request.content)
        calls.append(body["model"])
        text = "안녕!" if body["model"] == settings.adapter_name else '{"decision":"allow"}'
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelProvider(settings, client)
        assert await provider.ready()
        assert await ChatService(provider).respond(
            "4-6", [{"role": "user", "content": "안녕"}]
        ) == ("안녕!", "answer")
    assert calls == [settings.served_model, settings.adapter_name, settings.served_model]


async def test_missing_adapter_or_silent_base_fallback_is_rejected():
    settings = configuration(adapter_name="test-adapter")

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": settings.served_model}]})
        return httpx.Response(
            200,
            json={
                "model": settings.served_model,
                "choices": [{"message": {"content": "base response"}, "finish_reason": "stop"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelProvider(settings, client)
        assert not await provider.ready()
        with pytest.raises(ModelUnavailable, match="Unexpected model"):
            await provider.complete([])


def adapter_fixture(path, settings):
    (path / "adapter").mkdir(parents=True)
    (path / "adapter/adapter_model.safetensors").write_bytes(b"test-fixture-not-a-real-model")
    (path / "adapter/adapter_config.json").write_text('{"r":16}')
    (path / "policy.json").write_text(POLICY)
    (path / "training-manifest.json").write_text(
        json.dumps(
            {
                "state": "reload_verified_behavior_pending",
                "model_id": settings.profile["model_id"],
                "revision": settings.model_revision,
                "adapter_sha256": digest(path / "adapter/adapter_model.safetensors"),
                "adapter_config_sha256": digest(path / "adapter/adapter_config.json"),
            }
        )
    )


def test_adapter_identity_and_launcher_require_verified_unchanged_files(tmp_path):
    settings = configuration(adapter_name="test-adapter")
    adapter_fixture(tmp_path, settings)
    identity = evaluation_identity(settings, tmp_path)
    assert identity["variant"] == "adapter" and identity["guard_model"] == settings.served_model
    command = build_command(settings, "/bin/vllm", tmp_path)
    module = json.loads(command[command.index("--lora-modules") + 1])
    assert module["name"] == settings.adapter_name
    assert module["base_model_name"] == settings.served_model
    assert command[command.index("--max-lora-rank") + 1] == "16"
    (tmp_path / "adapter/adapter_config.json").write_text('{"r":32}')
    with pytest.raises(ValueError, match="changed"):
        evaluation_identity(settings, tmp_path)
    with pytest.raises(ValueError, match="together"):
        evaluation_identity(settings)


def test_base_and_adapter_reviews_stay_separate_and_duplicate_experiments_fail(tmp_path):
    paths = [make_run(tmp_path / "base"), make_run(tmp_path / "adapter")]
    for path, name in zip(paths, ("base-test", "adapter-test"), strict=True):
        meta = json.loads((path / "metadata.json").read_text())
        meta["experiment_id"] = name
        (path / "metadata.json").write_text(json.dumps(meta))
    packet = tmp_path / "packet"
    assert export_packets(paths, packet) == 2
    a, b = rate(packet, "reviewer_a", "Alice"), rate(packet, "reviewer_b", "Bob")
    report = aggregate(packet, a, b)
    assert report["groups"]["base-test/raw/all"]["scenarios"] == 1
    assert report["groups"]["adapter-test/raw/all"]["scenarios"] == 1
    meta = json.loads((paths[1] / "metadata.json").read_text())
    meta["experiment_id"] = "base-test"
    (paths[1] / "metadata.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="same experiment"):
        export_packets(paths, tmp_path / "duplicate")


def test_ai_ratings_must_be_marked_as_ai(tmp_path):
    packet = tmp_path / "packet"
    export_packets([make_run(tmp_path / "run")], packet)
    a = rate(packet, "reviewer_a", "codex_ai_reviewer_a")
    b = rate(packet, "reviewer_b", "codex_ai_reviewer_b")
    with pytest.raises(ValueError, match="AI ratings"):
        aggregate(packet, a, b)
    assert aggregate(packet, a, b, review_kind="ai")["review_kind"] == "ai"


@pytest.mark.parametrize("bad_path", [False, True])
async def test_serving_verification_checks_server_root_and_aliases(tmp_path, bad_path):
    settings = configuration(adapter_name="test-adapter")
    run = tmp_path / "training"
    adapter_fixture(run, settings)
    record = tmp_path / "gpu-environment.json"
    identity = evaluation_identity(settings, run)
    adapter_path = str((run / "adapter").resolve())
    record.write_text(json.dumps({**identity, "adapter_directory": adapter_path}))
    calls = []

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": settings.served_model},
                        {
                            "id": settings.adapter_name,
                            "root": "wrong" if bad_path else adapter_path,
                            "parent": settings.served_model,
                        },
                    ]
                },
            )
        body = json.loads(request.content)
        calls.append(body["model"])
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"message": {"content": "fixture response"}, "finish_reason": "stop"}],
            },
        )

    output = tmp_path / "serving.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        if bad_path:
            with pytest.raises(ValueError, match="path differs"):
                await verify(run, record, output, settings, client)
            assert not output.exists() and not calls
        else:
            result = await verify(run, record, output, settings, client)
            assert len(result["responses"]) == 5
            assert calls == [settings.adapter_name] * 5 + [settings.served_model]


def rescore_fixture(tmp_path):
    run = tmp_path / "original"
    run.mkdir()
    item = json.loads((ROOT / "data/dev.jsonl").read_text().splitlines()[0])
    data = tmp_path / "reviewed.jsonl"
    (run / "dataset.jsonl").write_text(json.dumps(item) + "\n")
    item.update(review_status="reviewed", expected_actions=["clarify"], rubric="Reviewed fixture")
    data.write_text(json.dumps(item) + "\n")
    row = {
        "id": item["id"],
        "mode": "guarded",
        "age_band": item["age_band"],
        "category": item["category"],
        "rubric": "old",
        "expected_actions": ["answer"],
        "turns": [
            {
                "question": item["inputs"][0],
                "answer": "stored fixture answer",
                "action": "clarify",
                "expected_action": "answer",
            }
        ],
        "error": None,
        "seconds": 1.5,
        "action_match": False,
    }
    (run / "results.jsonl").write_text(json.dumps(row) + "\n")
    (run / "policy.json").write_text(POLICY)
    (run / "metadata.json").write_text(
        json.dumps(
            {
                "state": "completed",
                "scenario_ids": [item["id"]],
                "data_sha256": "old-data",
                "results_sha256": digest(run / "results.jsonl"),
                "policy_sha256": digest(run / "policy.json"),
            }
        )
    )
    return run, data


def test_rescore_preserves_original_generations_and_tracks_provenance(tmp_path):
    run, data = rescore_fixture(tmp_path)
    before = {p.name: digest(p) for p in run.iterdir()}
    output = tmp_path / "rescored"
    assert rescore(run, data, output) == 1
    row = json.loads((output / "results.jsonl").read_text())
    assert row["action_match"] is True
    assert row["turns"][0]["answer"] == "stored fixture answer" and row["seconds"] == 1.5
    assert (
        json.loads((output / "metadata.json").read_text())["original_results_sha256"]
        == before["results.jsonl"]
    )
    assert before == {p.name: digest(p) for p in run.iterdir()}


@pytest.mark.parametrize(
    "field,value", [("inputs", ["다른 질문"]), ("age_band", "7-10"), ("review_status", "draft")]
)
def test_rescore_rejects_input_changes_or_unreviewed_labels(tmp_path, field, value):
    run, data = rescore_fixture(tmp_path)
    row = json.loads(data.read_text())
    row[field] = value
    data.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError):
        rescore(run, data, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_development_review_keeps_inputs_and_records_human_provenance(tmp_path):
    source, edits = ROOT / "data/dev.jsonl", tmp_path / "review.csv"
    before = digest(source)
    export(source, edits)
    with edits.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fields, rows = reader.fieldnames, list(reader)
    rows[0].update(
        review_status="reviewed",
        reviewer="Test human",
        inputs='["tampered"]',
        rubric="Fixture rationale",
        reference="Test fixture",
    )
    with edits.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert import_labels(source, edits, tmp_path / "output") == 1
    imported = json.loads((tmp_path / "output/dev.jsonl").read_text().splitlines()[0])
    assert imported["inputs"] != ["tampered"] and imported["review_status"] == "reviewed"
    assert digest(source) == before


def test_training_requires_reviewed_evaluation_labels_before_gpu_imports(
    tmp_path, monkeypatch, capsys
):
    from runpod.operations import train

    monkeypatch.setattr(train, "load_dotenv", lambda *_: None)
    monkeypatch.setattr(train, "Settings", configuration)
    monkeypatch.setattr(
        train,
        "load_training",
        lambda *_: (
            [training_row(i) for i in range(50)],
            [training_row(i + 50) for i in range(10)],
        ),
    )
    monkeypatch.setattr("sys.argv", ["train", "--output", str(tmp_path / "out")])
    with pytest.raises(SystemExit):
        train.main()
    assert "Finalize reviewed evaluation labels" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_project_review_is_explicit_and_preserved_in_training_rows(tmp_path):
    from runpod.operations.prepare_training import from_candidates

    row = {
        "id": "project-test",
        "source_id": "test",
        "scenario_id": "group-test",
        "source_split": "train",
        "adapted_question": "질문",
        "approved_answer": "답변",
        "age_band": "4-6",
        "expected_action": "answer",
        "reference": "검수 근거",
        "review_status": "reviewed",
        "reviewer": "phase2-project-review",
        "review_scope": "project",
    }
    path = tmp_path / "source.jsonl"
    path.write_text(json.dumps(row) + "\n")
    result = from_candidates(path)[0]
    assert result.review_scope == "project"
    row["reviewer"] = ""
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError):
        from_candidates(path)


def test_project_development_review_keeps_scope_and_all_generation_inputs(tmp_path):
    source, edits = ROOT / "data/dev.jsonl", tmp_path / "review.csv"
    export(source, edits)
    with edits.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        row.update(review_status="reviewed", reviewer="phase2-project-review", reference="근거")
    with edits.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    output = tmp_path / "approved"
    assert import_labels(source, edits, output, review_scope="project") == 100
    original = [json.loads(line) for line in source.read_text().splitlines()]
    imported = [json.loads(line) for line in (output / "dev.jsonl").read_text().splitlines()]
    assert all(r["review_scope"] == "project" for r in imported)
    assert [r["inputs"] for r in original] == [r["inputs"] for r in imported]
    assert json.loads((output / "review-manifest.json").read_text())["review_scope"] == "project"


def test_behavior_experiments_have_distinct_identities():
    from runpod.operations.experiments import evaluation_identity
    from runpod.tests.helpers import configuration

    settings = configuration()
    baseline = evaluation_identity(settings)
    candidate = evaluation_identity(settings.model_copy(update={"behavior_profile": "input_v2"}))
    assert baseline["experiment_id"] != candidate["experiment_id"]
    assert baseline["behavior_profile"] == "baseline"
    assert candidate["behavior_profile"] == "input_v2"
    assert baseline["base_revision"] == candidate["base_revision"]
