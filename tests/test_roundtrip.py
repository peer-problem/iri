import csv
import json

import pytest

from backend.service import POLICY
from scripts.candidate_review import export_csv, import_csv
from scripts.source_square import candidates
from scripts.verify_adapter import validate_manifest
from tests.test_api import configuration


def test_candidate_edits_preserve_original_source_and_validate_approval(tmp_path):
    records = candidates(
        [{"question": "학교 친구 이야기", "response": "원문 답변", "acceptable?": 1}], 1
    )
    source, edit, output = (
        tmp_path / "source.jsonl",
        tmp_path / "edit.csv",
        tmp_path / "reviewed.jsonl",
    )
    source.write_text(json.dumps(records[0], ensure_ascii=False) + "\n")
    assert export_csv(source, edit) == 1
    with edit.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0].update(
        source_question="TAMPERED SOURCE",
        adapted_question="검수한 질문",
        approved_answer="검수한 답변",
        age_band="4-6",
        expected_action="answer",
        reference="test reference",
        review_status="reviewed",
        reviewer="test-reviewer",
    )
    with edit.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert import_csv(source, edit, output)["reviewed"] == 1
    imported = json.loads(output.read_text())
    assert imported["source_question"] == records[0]["source_question"]
    assert imported["scenario_id"] == records[0]["scenario_id"]
    assert imported["approved_answer"] == "검수한 답변"
    assert json.loads(source.read_text())["review_status"] == "draft"


def test_adapter_verification_rejects_wrong_revision_before_loading_gpu(tmp_path):
    (tmp_path / "training-manifest.json").write_text(
        json.dumps(
            {
                "state": "trained_reload_pending",
                "revision": "b" * 40,
                "model_id": configuration().profile["model_id"],
            }
        )
    )
    with pytest.raises(ValueError, match="differ"):
        validate_manifest(tmp_path, configuration())


def test_adapter_verification_rejects_missing_weights(tmp_path):
    (tmp_path / "training-manifest.json").write_text(
        json.dumps(
            {
                "state": "trained_reload_pending",
                "revision": configuration().model_revision,
                "model_id": configuration().profile["model_id"],
            }
        )
    )
    (tmp_path / "policy.json").write_text(POLICY)
    with pytest.raises(ValueError, match="missing"):
        validate_manifest(tmp_path, configuration())
