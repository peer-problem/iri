"""Re-score stored generations after label review, without a model or GPU call."""

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from runpod.operations.artifacts import code_manifest
from runpod.operations.data import load_scenarios
from runpod.operations.evaluate import summarize
from runpod.operations.experiments import digest


def rescore(run: Path, data: Path, output: Path):
    metadata = json.loads((run / "metadata.json").read_text())
    if metadata.get("state") not in {"completed", "completed_with_errors"}:
        raise ValueError("Only finalized runs can be rescored")
    if digest(run / "results.jsonl") != metadata.get("results_sha256"):
        raise ValueError("Original results have changed")
    if (
        metadata.get("dataset_snapshot_sha256")
        and digest(run / "dataset.jsonl") != metadata["dataset_snapshot_sha256"]
    ):
        raise ValueError("Original dataset snapshot has changed")
    old = {item.id: item for item in load_scenarios([run / "dataset.jsonl"])}
    new = {item.id: item for item in load_scenarios([data])}
    if old.keys() != new.keys() or set(metadata["scenario_ids"]) != old.keys():
        raise ValueError("Re-scoring requires the identical scenario set")
    if any(item.review_status != "reviewed" or item.split != "dev" for item in new.values()):
        raise ValueError("Re-scoring requires reviewed development labels")
    if digest(run / "policy.json") != metadata["policy_sha256"]:
        raise ValueError("Original policy has changed")
    for key, item in new.items():
        if item.inputs != old[key].inputs or item.age_band != old[key].age_band:
            raise ValueError(f"Generation inputs changed: {key}; re-run inference")
    rows, seen = [], set()
    for line in (run / "results.jsonl").read_text().splitlines():
        row = json.loads(line)
        key = (row["id"], row["mode"])
        if key in seen or row["id"] not in old or row["mode"] not in {"raw", "guarded"}:
            raise ValueError("Invalid or duplicate original result")
        seen.add(key)
        item = new[row["id"]]
        if row["age_band"] != item.age_band:
            raise ValueError("Stored age band differs from generation inputs")
        questions = [turn["question"] for turn in row["turns"]]
        if questions != item.inputs[: len(questions)] or (
            not row["error"] and len(questions) != len(item.inputs)
        ):
            raise ValueError("Stored turns do not match original generation inputs")
        row.update(
            category=item.category, rubric=item.rubric, expected_actions=item.expected_actions
        )
        for index, turn in enumerate(row["turns"]):
            turn["expected_action"] = item.expected_actions[index]
        row["action_match"] = (
            (not row["error"] and all(t["action"] == t["expected_action"] for t in row["turns"]))
            if row["mode"] == "guarded"
            else None
        )
        rows.append(row)
    modes = {mode for _, mode in seen}
    if not modes or seen != {(key, mode) for key in new for mode in modes}:
        raise ValueError("Original result set is incomplete")
    output.mkdir(parents=True, exist_ok=False)
    (output / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )
    (output / "dataset.jsonl").write_bytes(data.read_bytes())
    (output / "policy.json").write_bytes((run / "policy.json").read_bytes())
    (output / "summary.json").write_text(json.dumps(summarize(rows), ensure_ascii=False, indent=2))
    metadata.update(
        evaluation_kind="rescored",
        rescored_at=datetime.now(UTC).isoformat(),
        original_run=str(run.resolve()),
        original_metadata_sha256=digest(run / "metadata.json"),
        original_data_sha256=metadata["data_sha256"],
        original_results_sha256=metadata["results_sha256"],
        data_sha256=digest(data),
        dataset_snapshot_sha256=digest(output / "dataset.jsonl"),
        results_sha256=digest(output / "results.jsonl"),
        review_status="reviewed",
        rescore_code_sha256=code_manifest()["sha256"],
        latency_note="Generation timings retained from the original run; no new inference was performed.",
    )
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    fields = [
        "id",
        "mode",
        "age_band",
        "rubric",
        "reviewer",
        "harmful_exposure",
        "over_refusal",
        "correct",
        "age_appropriate",
        "support_appropriate",
        "notes",
    ]
    with (output / "review.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in ("id", "mode", "age_band", "rubric")} for row in rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        f"Rescored {rescore(args.run, args.data, args.output)} stored results; no inference performed"
    )


if __name__ == "__main__":
    main()
