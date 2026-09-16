import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.schemas import AgeBand
from runpod.operations.data import load_scenarios
from runpod.operations.source_square import normalized
from runpod.settings import ROOT


class TrainingRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    age_band: AgeBand
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=4000)
    expected_action: Literal["answer", "redirect", "support", "clarify"]
    reference: str = Field(min_length=1)
    review_status: Literal["reviewed"]
    reviewer: str = Field(min_length=1)
    review_scope: Literal["human", "project", "unspecified"] = "unspecified"
    split: Literal["train", "validation"] = "train"

    @model_validator(mode="after")
    def not_placeholder(self):
        if self.reviewer.casefold() in {"todo", "pending", "unknown"}:
            raise ValueError("A real reviewer identifier is required")
        if self.review_scope != "project" and self.reviewer.casefold().startswith(
            ("codex_ai", "ai_")
        ):
            raise ValueError("AI drafts require approval by an identified human reviewer")
        return self


class SplitGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    split: Literal["train", "validation"]


def load_split_plan(path: Path) -> dict[tuple[str, str], str]:
    records = json.loads(path.read_text())
    if not isinstance(records, list):
        raise ValueError("Split plan must be a list of source_id, scenario_id and split records")
    plan = {}
    for record in records:
        item = SplitGroup.model_validate(record)
        group = (item.source_id, item.scenario_id)
        if group in plan:
            raise ValueError(f"Duplicate split-plan group: {group}")
        plan[group] = item.split
    return plan


def validate_split_sizes(train: list[TrainingRow], validation: list[TrainingRow]):
    if len(train) < 50 or len(validation) < 10:
        raise ValueError(
            f"Need at least 50 train and 10 validation examples; got {len(train)} / {len(validation)}"
        )


def distribution(rows: list[TrainingRow]) -> dict:
    cells = Counter((row.age_band, row.expected_action) for row in rows)
    return {
        "rows": len(rows),
        "groups": len({(row.source_id, row.scenario_id) for row in rows}),
        "age_action_counts": {
            age: {
                action: cells[age, action]
                for action in ("answer", "redirect", "support", "clarify")
            }
            for age in ("4-6", "7-10")
        },
    }


def from_candidates(path: Path) -> list[TrainingRow]:
    result = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        candidate = json.loads(line)
        if candidate.get("review_status") != "reviewed":
            continue
        if candidate.get("source_split") != "train":
            raise ValueError("Only original training sources may be used for training")
        result.append(
            TrainingRow(
                id=candidate["id"],
                source_id=candidate["source_id"],
                scenario_id=candidate["scenario_id"],
                age_band=candidate["age_band"],
                question=candidate["adapted_question"],
                answer=candidate["approved_answer"],
                expected_action=candidate["expected_action"],
                reference=candidate["reference"],
                review_status="reviewed",
                reviewer=candidate["reviewer"],
                review_scope=candidate.get("review_scope", "unspecified"),
            )
        )
    if not result:
        raise ValueError("No reviewed training examples; draft answers cannot be trained")
    return result


def partition(
    rows: list[TrainingRow],
    eval_paths: list[Path],
    split_plan: dict[tuple[str, str], str] | None = None,
) -> tuple[list[TrainingRow], list[TrainingRow]]:
    evaluation = load_scenarios(eval_paths)
    excluded_groups = {(item.source_id, item.scenario_id) for item in evaluation}
    excluded_questions = {normalized(q) for item in evaluation for q in item.inputs}
    seen_ids, seen_questions = set(), {}
    group_assignment = {}
    if split_plan is not None:
        groups = {(row.source_id, row.scenario_id) for row in rows}
        if set(split_plan) != groups:
            raise ValueError("Split plan must cover exactly all approved scenario groups")
        if any(split not in {"train", "validation"} for split in split_plan.values()):
            raise ValueError("Split plan contains an invalid split")
    train, validation = [], []
    for row in rows:
        group = (row.source_id, row.scenario_id)
        question = normalized(row.question)
        if row.id in seen_ids:
            raise ValueError(f"Duplicate training id: {row.id}")
        seen_ids.add(row.id)
        if group in excluded_groups or question in excluded_questions:
            raise ValueError(f"Training overlaps evaluation: {row.id}")
        # Different group IDs for the same question must be fixed, not randomly split.
        if question in seen_questions and seen_questions[question] != group:
            raise ValueError(f"Same prompt has multiple scenario IDs: {row.id}")
        seen_questions[question] = group
        bucket = int(hashlib.sha256(json.dumps(group).encode()).hexdigest()[:8], 16) % 10
        group_assignment[group] = (
            split_plan[group]
            if split_plan is not None
            else "validation"
            if bucket == 0
            else "train"
        )
        row = row.model_copy(update={"split": group_assignment[group]})
        (validation if row.split == "validation" else train).append(row)
    if not train or not validation:
        raise ValueError(
            "Need more independent reviewed scenario groups for both train and validation"
        )
    train.sort(key=lambda row: row.id)
    validation.sort(key=lambda row: row.id)
    return train, validation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--evaluation", type=Path, nargs="+", default=[(ROOT / "data/dev.jsonl")])
    parser.add_argument("--output", type=Path, default=(ROOT / "data/prepared"))
    parser.add_argument("--split-plan", type=Path, help="Explicit group assignments in a JSON list")
    parser.add_argument(
        "--semantic-review", type=Path, help="Completed review tied to source hashes"
    )
    args = parser.parse_args()
    rows = from_candidates(args.candidates)
    plan = load_split_plan(args.split_plan) if args.split_plan else None
    train, validation = partition(rows, args.evaluation, plan)
    validate_split_sizes(train, validation)
    semantic_review = {
        "status": "required",
        "note": "Automatic checks cover IDs and exact prompts only",
    }
    if args.semantic_review:
        report = json.loads(args.semantic_review.read_text())
        if (
            report.get("reviewed_sha256")
            != hashlib.sha256(args.candidates.read_bytes()).hexdigest()
            or len(args.evaluation) != 1
            or report.get("development_sha256")
            != hashlib.sha256(args.evaluation[0].read_bytes()).hexdigest()
            or report.get("semantic_overlap_review", {}).get("status") != "completed"
        ):
            raise ValueError("Semantic review is incomplete or refers to different data")
        semantic_review = {
            "status": "completed",
            "review_scope": report["review_scope"],
            "report_sha256": hashlib.sha256(args.semantic_review.read_bytes()).hexdigest(),
            "report": str(args.semantic_review),
        }
    args.output.mkdir(parents=True, exist_ok=False)
    for name, subset in (("train", train), ("validation", validation)):
        (args.output / f"{name}.jsonl").write_text(
            "".join(item.model_dump_json() + "\n" for item in subset)
        )
    (args.output / "manifest.json").write_text(
        json.dumps(
            {
                "source_sha256": hashlib.sha256(args.candidates.read_bytes()).hexdigest(),
                "train": len(train),
                "validation": len(validation),
                "evaluation_hashes": {
                    str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.evaluation
                },
                "split_method": "Explicit scenario-group plan"
                if plan is not None
                else "Stable SHA256 group buckets, validation bucket 0 of 10",
                "split_plan_sha256": hashlib.sha256(args.split_plan.read_bytes()).hexdigest()
                if args.split_plan
                else None,
                "group_assignments": [
                    {"source_id": source, "scenario_id": scenario, "split": split}
                    for (source, scenario), split in sorted(
                        {
                            (row.source_id, row.scenario_id): row.split
                            for row in [*train, *validation]
                        }.items()
                    )
                ],
                "distribution": {
                    "train": distribution(train),
                    "validation": distribution(validation),
                },
                "semantic_overlap_review": semantic_review,
            },
            indent=2,
        )
    )
    print(f"Prepared {len(train)} train / {len(validation)} validation examples")


if __name__ == "__main__":
    main()
