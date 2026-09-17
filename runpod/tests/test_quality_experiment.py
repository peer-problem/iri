import hashlib
import json

import pytest

from runpod.operations import quality_experiment as quality
from runpod.operations.data import load_scenarios
from runpod.settings import ROOT


def dataset(tmp_path, status):
    item = load_scenarios([ROOT / "data/dev.jsonl"])[0]
    path = tmp_path / "data.jsonl"
    path.write_text(item.model_copy(update={"review_status": status}).model_dump_json() + "\n")
    return path


async def test_draft_rejected_before_creating_experiment_or_calling_model(tmp_path, monkeypatch):
    async def unexpected(_):
        pytest.fail("Draft data must be rejected before model calls")

    monkeypatch.setattr(quality, "evaluate", unexpected)
    output = tmp_path / "experiment"
    with pytest.raises(ValueError, match="reviewed"):
        await quality.run_experiment(dataset(tmp_path, "draft"), output)
    assert not output.exists()


async def test_exit_two_without_saved_results_is_failed_not_complete(tmp_path, monkeypatch):
    calls = []

    async def no_results(args):
        calls.append(args.behavior_profile)
        return 2

    monkeypatch.setattr(quality, "evaluate", no_results)
    output = tmp_path / "experiment"
    with pytest.raises(ValueError, match="finalized run"):
        await quality.run_experiment(dataset(tmp_path, "reviewed"), output)
    assert calls == ["baseline"]
    assert json.loads((output / "experiment.json").read_text())["state"] == "failed"


@pytest.mark.parametrize("duplicate", [False, True])
async def test_completion_requires_exact_scenario_mode_pairs(tmp_path, monkeypatch, duplicate):
    data = dataset(tmp_path, "reviewed")
    scenario = load_scenarios([data])[0]

    async def saved_results(args):
        run = args.output / "run"
        run.mkdir(parents=True)
        rows = [{"id": scenario.id, "mode": "raw"}]
        rows.append({"id": scenario.id, "mode": "raw" if duplicate else "guarded"})
        result = run / "results.jsonl"
        result.write_text("".join(json.dumps(row) + "\n" for row in rows))
        (run / "metadata.json").write_text(
            json.dumps(
                {
                    "state": "completed",
                    "result_rows": 2,
                    "behavior_profile": args.behavior_profile,
                    "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
                    "results_sha256": hashlib.sha256(result.read_bytes()).hexdigest(),
                    "experiment_id": "base-test",
                }
            )
        )
        return 0

    monkeypatch.setattr(quality, "evaluate", saved_results)
    output = tmp_path / "experiment"
    if duplicate:
        with pytest.raises(ValueError, match="inconsistent"):
            await quality.run_experiment(data, output, ["baseline"])
    else:
        result = await quality.run_experiment(data, output, ["baseline"])
        assert result["state"] == "completed"
