import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.schemas import AgeBand
from scripts.data import load_scenarios
from scripts.source_square import normalized


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
    split: Literal["train", "validation"] = "train"

    @model_validator(mode="after")
    def not_placeholder(self):
        if self.reviewer.casefold() in {"todo", "pending", "unknown"}:
            raise ValueError("A real reviewer identifier is required")
        return self


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
            )
        )
    if not result:
        raise ValueError("No human-reviewed training examples; draft answers cannot be trained")
    return result


def partition(
    rows: list[TrainingRow], eval_paths: list[Path]
) -> tuple[list[TrainingRow], list[TrainingRow]]:
    evaluation = load_scenarios(eval_paths)
    excluded_groups = {(item.source_id, item.scenario_id) for item in evaluation}
    excluded_questions = {normalized(q) for item in evaluation for q in item.inputs}
    seen_ids, seen_questions = set(), {}
    group_assignment = {}
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
        group_assignment[group] = "validation" if bucket == 0 else "train"
        row = row.model_copy(update={"split": group_assignment[group]})
        (validation if row.split == "validation" else train).append(row)
    if not train or not validation:
        raise ValueError(
            "Need more independent reviewed scenario groups for both train and validation"
        )
    return train, validation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--evaluation", type=Path, nargs="+", default=[Path("data/dev.jsonl")])
    parser.add_argument("--output", type=Path, default=Path("data/prepared"))
    args = parser.parse_args()
    rows = from_candidates(args.candidates)
    train, validation = partition(rows, args.evaluation)
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
                "split_method": "Stable SHA256 group buckets, validation bucket 0 of 10",
                "semantic_overlap_review": "required; automatic checks only cover IDs and normalized identical prompts",
            },
            indent=2,
        )
    )
    print(f"Prepared {len(train)} train / {len(validation)} validation examples")


if __name__ == "__main__":
    main()
