import json
import zipfile
from pathlib import Path

import pytest

from app.operations.artifacts import code_files
from app.operations.bundle import build_bundle
from app.operations.prepare_training import TrainingRow, from_candidates, partition
from app.operations.source_square import candidates, question_group
from app.operations.training_data import encode_row, load_training, pad_batch


def training_row(index=0, **updates):
    value = dict(
        id=f"train-{index}",
        source_id="test-fixture",
        scenario_id=f"group-{index}",
        age_band="4-6",
        question=f"테스트 질문 {index}",
        answer="테스트 답변",
        expected_action="answer",
        reference="test fixture",
        review_status="reviewed",
        reviewer="test-reviewer",
        split="train",
    )
    value.update(updates)
    return TrainingRow(**value)


def test_source_candidates_are_unique_unapproved_and_never_use_unacceptable_answers():
    records = [
        {"question": "학교 친구", "response": "one", "acceptable?": 1},
        {"question": "학교 친구", "response": "two", "acceptable?": 1},
        {"question": "아이", "response": "unacceptable", "acceptable?": 0},
    ]
    result = candidates(records, 10)
    assert len(result) == 1
    assert result[0]["review_status"] == "draft"
    assert result[0]["approved_answer"] == ""
    assert result[0]["source_answer"] != "unacceptable"
    assert question_group("학교 친구") == question_group("학교  친구")


def test_unreviewed_candidates_cannot_become_training_data(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text('{"review_status":"draft"}\n')
    with pytest.raises(ValueError, match="No human-reviewed"):
        from_candidates(path)


def test_group_split_is_stable_and_keeps_age_variants_together():
    rows = [training_row(i) for i in range(80)]
    rows.append(
        training_row(80, scenario_id="group-0", question="다른 나이의 표현", age_band="7-10")
    )
    train, validation = partition(rows, [Path("data/dev.jsonl")])
    train2, validation2 = partition(list(reversed(rows)), [Path("data/dev.jsonl")])
    assert {r.id for r in train} == {r.id for r in train2}
    assert {r.id for r in validation} == {r.id for r in validation2}
    assert all(
        len({r.split for r in [*train, *validation] if r.scenario_id == group}) == 1
        for group in {r.scenario_id for r in rows}
    )


def test_training_evaluation_overlap_rejected():
    rows = [training_row(0, question="비는 왜 내려?")]
    with pytest.raises(ValueError, match="overlaps evaluation"):
        partition(rows, [Path("data/dev.jsonl")])


def test_training_validation_overlap_rejected(tmp_path):
    train, valid = tmp_path / "train.jsonl", tmp_path / "valid.jsonl"
    train.write_text(training_row().model_dump_json())
    valid.write_text(training_row(1, scenario_id="group-0", split="validation").model_dump_json())
    with pytest.raises(ValueError, match="leakage"):
        load_training(train, valid)


class ToyTokenizer:
    def apply_chat_template(self, _messages, tokenize, add_generation_prompt):
        return [1, 2, 3] if add_generation_prompt else [1, 2, 3, 7, 9]


def test_only_assistant_tokens_contribute_to_loss_and_real_eos_is_kept():
    encoded = encode_row(training_row(), ToyTokenizer(), 10)
    assert encoded["labels"] == [-100, -100, -100, 7, 9]
    longer = {"input_ids": [1] * 7, "attention_mask": [1] * 7, "labels": [1] * 7}
    padded = pad_batch([encoded, longer], pad_token_id=9)
    assert padded["labels"][0] == [-100, -100, -100, 7, 9, -100, -100]
    assert padded["attention_mask"][0][-2:] == [0, 0]


def test_oversized_training_example_is_not_silently_truncated():
    with pytest.raises(ValueError, match="context limit"):
        encode_row(training_row(), ToyTokenizer(), 4)


def test_unexpected_template_boundary_rejected():
    class BrokenTokenizer(ToyTokenizer):
        def apply_chat_template(self, messages, tokenize, add_generation_prompt):
            return [1, 2, 3] if add_generation_prompt else [4, 5, 6, 7]

    with pytest.raises(ValueError, match="assistant boundary"):
        encode_row(training_row(), BrokenTokenizer(), 10)


def test_bundle_excludes_secrets_docs_models_and_symlinks(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "api").mkdir()
    for name in ("README.md", "api/pyproject.toml"):
        (root / name).write_text("public fixture")
    (root / ".env").write_text("SUPER_SECRET_KEY")
    (root / "api/data/raw").mkdir(parents=True)
    (root / "api/data/raw/private.json").write_text("PRIVATE_SOURCE")
    (root / "api/app/operations").mkdir(parents=True)
    (root / "api/app/secret.py").symlink_to(root / ".env")
    (root / "api/app/operations/example.py").write_text("PUBLIC_OPERATION = True")
    target = tmp_path / "source.zip"
    result = build_bundle(target, root)
    with zipfile.ZipFile(target) as archive:
        assert ".env" not in archive.namelist()
        assert "api/app/secret.py" not in archive.namelist()
        assert "api/data/raw/private.json" not in archive.namelist()
        assert "api/app/operations/example.py" in archive.namelist()
        assert "api/pyproject.toml" in archive.namelist()
        assert "SUPER_SECRET_KEY" not in str([archive.read(name) for name in archive.namelist()])
        assert len(json.loads(archive.read("bundle-manifest.json"))) == result["files"]
    with pytest.raises(FileExistsError):
        build_bundle(target, root)
    assert all(p.is_file() for p in code_files(root))


def test_init_local_creates_private_env_without_template(tmp_path, monkeypatch):
    from dotenv import dotenv_values

    from app.operations import init_local

    target = tmp_path / ".env"
    monkeypatch.setattr(init_local, "ENV_FILE", target)
    monkeypatch.chdir(tmp_path)
    init_local.main()
    values = dotenv_values(target)
    assert len(values["SANDBOX_API_KEY"]) >= 32
    assert values["SANDBOX_API_KEY"] != values["MODEL_API_KEY"]
    assert target.stat().st_mode & 0o777 == 0o600
    original = target.read_bytes()
    with pytest.raises(SystemExit, match="preserved"):
        init_local.main()
    assert target.read_bytes() == original
