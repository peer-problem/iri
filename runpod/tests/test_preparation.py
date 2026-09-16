import json
import zipfile

import pytest

from runpod.operations.artifacts import code_files
from runpod.operations.bundle import build_bundle
from runpod.operations.prepare_training import (
    TrainingRow,
    distribution,
    from_candidates,
    load_split_plan,
    partition,
    validate_split_sizes,
)
from runpod.operations.source_square import candidates, question_group
from runpod.operations.training_data import encode_row, load_training, pad_batch
from runpod.settings import ROOT


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
    with pytest.raises(ValueError, match="No reviewed"):
        from_candidates(path)


def test_group_split_is_stable_and_keeps_age_variants_together():
    rows = [training_row(i) for i in range(80)]
    rows.append(
        training_row(80, scenario_id="group-0", question="다른 나이의 표현", age_band="7-10")
    )
    train, validation = partition(rows, [(ROOT / "data/dev.jsonl")])
    train2, validation2 = partition(list(reversed(rows)), [(ROOT / "data/dev.jsonl")])
    assert {r.id for r in train} == {r.id for r in train2}
    assert {r.id for r in validation} == {r.id for r in validation2}
    assert all(
        len({r.split for r in [*train, *validation] if r.scenario_id == group}) == 1
        for group in {r.scenario_id for r in rows}
    )


def test_training_evaluation_overlap_rejected():
    rows = [training_row(0, question="비는 왜 내려?")]
    with pytest.raises(ValueError, match="overlaps evaluation"):
        partition(rows, [(ROOT / "data/dev.jsonl")])


def test_explicit_plan_meets_sizes_and_keeps_age_variants_together():
    rows = [
        training_row(i, scenario_id=f"group-{i // 2}", age_band="4-6" if i % 2 == 0 else "7-10")
        for i in range(60)
    ]
    plan = {("test-fixture", f"group-{i}"): "train" if i < 25 else "validation" for i in range(30)}
    train, validation = partition(rows, [ROOT / "data/dev.jsonl"], plan)
    validate_split_sizes(train, validation)
    assert (len(train), len(validation)) == (50, 10)
    assert (train, validation) == partition(list(reversed(rows)), [ROOT / "data/dev.jsonl"], plan)
    assert {row.scenario_id for row in train}.isdisjoint(row.scenario_id for row in validation)
    counts = distribution(validation)
    assert counts["groups"] == 5
    assert counts["age_action_counts"]["4-6"] == {
        "answer": 5,
        "redirect": 0,
        "support": 0,
        "clarify": 0,
    }


@pytest.mark.parametrize("groups", [[], ["group-0", "extra"]])
def test_split_plan_must_cover_exact_approved_groups(groups):
    plan = {("test-fixture", group): "train" for group in groups}
    with pytest.raises(ValueError, match="exactly all approved"):
        partition([training_row()], [ROOT / "data/dev.jsonl"], plan)


def test_split_plan_cannot_override_evaluation_exclusion():
    row = training_row(question="비는 왜 내려?")
    with pytest.raises(ValueError, match="overlaps evaluation"):
        partition([row], [ROOT / "data/dev.jsonl"], {("test-fixture", "group-0"): "train"})


def test_split_plan_rejects_duplicate_groups(tmp_path):
    path = tmp_path / "plan.json"
    record = {"source_id": "test-fixture", "scenario_id": "group-0", "split": "train"}
    path.write_text(json.dumps([record, {**record, "split": "validation"}]))
    with pytest.raises(ValueError, match="Duplicate split-plan group"):
        load_split_plan(path)


@pytest.mark.parametrize("sizes", [(49, 10), (50, 9)])
def test_minimum_split_sizes_are_enforced(sizes):
    with pytest.raises(ValueError, match="at least 50 train and 10 validation"):
        validate_split_sizes(
            [training_row(i) for i in range(sizes[0])],
            [training_row(i + 100) for i in range(sizes[1])],
        )


def test_prepare_writes_explicit_plan_and_distribution(tmp_path, monkeypatch):
    from runpod.operations import prepare_training

    source = tmp_path / "reviewed.jsonl"
    rows = [training_row(i) for i in range(60)]
    source.write_text(
        "".join(
            json.dumps(
                {
                    **row.model_dump(),
                    "source_split": "train",
                    "adapted_question": row.question,
                    "approved_answer": row.answer,
                }
            )
            + "\n"
            for row in rows
        )
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            [
                {
                    "source_id": row.source_id,
                    "scenario_id": row.scenario_id,
                    "split": "train" if i < 50 else "validation",
                }
                for i, row in enumerate(rows)
            ]
        )
    )
    output = tmp_path / "prepared"
    monkeypatch.setattr(
        "sys.argv",
        ["prepare_training", str(source), "--split-plan", str(plan), "--output", str(output)],
    )
    prepare_training.main()
    manifest = json.loads((output / "manifest.json").read_text())
    assert (manifest["train"], manifest["validation"]) == (50, 10)
    assert len(manifest["group_assignments"]) == 60
    assert manifest["split_plan_sha256"]
    assert manifest["distribution"]["validation"]["rows"] == 10
    assert manifest["semantic_overlap_review"]["status"] == "required"


def test_training_rejects_small_data_before_gpu_imports(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from runpod.operations import train

    monkeypatch.setattr(train, "load_dotenv", lambda *_: None)
    monkeypatch.setattr(train, "Settings", lambda: SimpleNamespace(model_revision="test-revision"))
    monkeypatch.setattr(train, "load_training", lambda *_: ([training_row()], [training_row(1)]))
    monkeypatch.setattr("sys.argv", ["train", "--output", str(tmp_path / "out")])
    with pytest.raises(ValueError, match="at least 50 train and 10 validation"):
        train.main()
    assert not (tmp_path / "out").exists()


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
    (root / "api/app").mkdir(parents=True)
    (root / ".keys").mkdir()
    (root / "runpod").mkdir()
    for name in ("README.md", "runpod/pyproject.toml"):
        (root / name).write_text("public fixture")
    (root / ".keys/.env").write_text("SUPER_SECRET_KEY")
    (root / ".keys/runpod-ed25519").write_text("PRIVATE_SSH_KEY")
    (root / "runpod/known_hosts").write_text("PRIVATE_HOST_HISTORY")
    (root / ".keys/runpod-ed25519.pub").write_text("SSH_PUBLIC_KEY")
    (root / ".keys/credentials.json").write_text("PRIVATE_SERVICE_CREDENTIALS")
    (root / "runpod/data/raw").mkdir(parents=True)
    (root / "runpod/data/raw/private.json").write_text("PRIVATE_SOURCE")
    (root / "runpod/operations").mkdir(parents=True)
    (root / "api/app/secret.py").symlink_to(root / ".keys/.env")
    (root / "runpod/operations/example.py").write_text("PUBLIC_OPERATION = True")
    target = tmp_path / "source.zip"
    result = build_bundle(target, root)
    with zipfile.ZipFile(target) as archive:
        assert not any(name.startswith(".keys/") for name in archive.namelist())
        assert ".keys/runpod-ed25519" not in archive.namelist()
        assert "runpod/known_hosts" not in archive.namelist()
        assert "api/app/secret.py" not in archive.namelist()
        assert "runpod/data/raw/private.json" not in archive.namelist()
        assert "runpod/operations/example.py" in archive.namelist()
        assert "runpod/pyproject.toml" in archive.namelist()
        assert "SUPER_SECRET_KEY" not in str([archive.read(name) for name in archive.namelist()])
        assert len(json.loads(archive.read("bundle-manifest.json"))) == result["files"]
    with pytest.raises(FileExistsError):
        build_bundle(target, root)
    assert all(p.is_file() for p in code_files(root))
