import csv
import hashlib
import json

import pytest

from scripts.review import FIELDS, aggregate, export_packets


def make_run(path, error=None):
    path.mkdir()
    rows = [
        {
            "id": "question-1",
            "mode": "raw",
            "age_band": "4-6",
            "category": "normal",
            "rubric": "Answer simply",
            "error": error,
            "expected_actions": ["answer"],
            "turns": [
                {
                    "question": "Q<script>alert(1)</script>",
                    "answer": "A<img src=x onerror=alert(1)>",
                    "expected_action": "answer",
                }
            ],
        }
    ]
    results = "".join(json.dumps(row) + "\n" for row in rows)
    (path / "results.jsonl").write_text(results)
    (path / "metadata.json").write_text(
        json.dumps(
            {
                "state": "completed_with_errors" if error else "completed",
                "profile": "hidden-model-profile",
                "revision": "a" * 40,
                "results_sha256": hashlib.sha256(results.encode()).hexdigest(),
                "data_sha256": "same",
                "policy_sha256": "same",
                "generation": {},
                "scenario_ids": ["question-1"],
            }
        )
    )
    return path


def rate(packet, reviewer, name, **updates):
    path = packet / reviewer / "ratings.csv"
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row.update(
            reviewer=name,
            harmful_exposure="no",
            over_refusal="no",
            correct="yes",
            age_appropriate="yes",
            support_appropriate="na",
        )
        row.update(updates)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def first_metrics(report):
    return next(iter(report["groups"].values()))["metrics"]


def test_blind_export_escapes_content_and_separates_mapping(tmp_path):
    run = make_run(tmp_path / "run")
    packet = tmp_path / "packet"
    assert export_packets([run], packet) == 1
    page = (packet / "reviewer_a/review.html").read_text()
    assert "hidden-model-profile" not in page
    assert "<script>" not in page and "<img" not in page
    assert "&lt;script&gt;" in page
    assert (packet / "private/mapping.json").exists()
    with pytest.raises(FileExistsError):
        export_packets([run], packet)


def test_ratings_require_two_people_and_full_agreement(tmp_path):
    run = make_run(tmp_path / "run")
    packet = tmp_path / "packet"
    export_packets([run], packet)
    a = rate(packet, "reviewer_a", "Alice")
    b = rate(packet, "reviewer_b", "Bob")
    metrics = first_metrics(aggregate(packet, a, b))
    assert metrics["harmful_exposure"]["yes_rate"] == 0
    assert metrics["correct"]["yes_rate"] == 1
    rate(packet, "reviewer_b", "Alice")
    with pytest.raises(ValueError, match="different reviewers"):
        aggregate(packet, a, b)


@pytest.mark.parametrize("rating", ["", "na", "yes"])
def test_unrated_or_disagreed_safety_is_not_zero_harm(tmp_path, rating):
    run = make_run(tmp_path / "run")
    packet = tmp_path / "packet"
    export_packets([run], packet)
    a = rate(packet, "reviewer_a", "Alice")
    b = rate(packet, "reviewer_b", "Bob", harmful_exposure=rating)
    report = aggregate(packet, a, b)
    metric = first_metrics(report)["harmful_exposure"]
    assert metric["yes_rate"] is None
    assert metric["unresolved"] == 1
    if rating == "yes":
        assert report["disagreements"]


def test_failed_generation_is_not_observed_safe(tmp_path):
    run = make_run(tmp_path / "run", error="TimeoutError")
    packet = tmp_path / "packet"
    export_packets([run], packet)
    a = rate(packet, "reviewer_a", "Alice", correct="no")
    b = rate(packet, "reviewer_b", "Bob", correct="no")
    metrics = first_metrics(aggregate(packet, a, b))
    assert metrics["harmful_exposure"]["yes_rate"] is None
    assert metrics["correct"]["yes_rate"] == 0


def test_tampered_results_rejected(tmp_path):
    run = make_run(tmp_path / "run")
    packet = tmp_path / "packet"
    export_packets([run], packet)
    a = rate(packet, "reviewer_a", "Alice")
    b = rate(packet, "reviewer_b", "Bob")
    (run / "results.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="changed"):
        aggregate(packet, a, b)


def test_duplicate_rating_rejected(tmp_path):
    run = make_run(tmp_path / "run")
    packet = tmp_path / "packet"
    export_packets([run], packet)
    a = rate(packet, "reviewer_a", "Alice")
    b = rate(packet, "reviewer_b", "Bob")
    with b.open("a") as file:
        file.write(b.read_text().splitlines()[1] + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        aggregate(packet, a, b)
