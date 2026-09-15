import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas import AgeBand


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_id: str
    scenario_id: str
    age_band: AgeBand
    category: Literal["normal", "harmful", "boundary", "multiturn"]
    inputs: list[str] = Field(min_length=1, max_length=5)
    expected_actions: list[Literal["answer", "redirect", "support", "clarify"]]
    rubric: str = Field(min_length=1)
    reference: str
    review_status: Literal["draft", "reviewed"]
    split: Literal["train", "dev", "test"]

    @model_validator(mode="after")
    def check_turns(self):
        if len(self.inputs) != len(self.expected_actions):
            raise ValueError("Each turn must have an expected action")
        if any(not message.strip() or len(message) > 1000 for message in self.inputs):
            raise ValueError("Each input must contain 1 to 1000 characters")
        if (self.category == "multiturn") != (len(self.inputs) > 1):
            raise ValueError("Only multiturn scenarios may contain multiple inputs")
        return self


def load_scenarios(paths: list[Path]) -> list[Scenario]:
    items = []
    ids: set[str] = set()
    groups: dict[tuple[str, str], str] = {}
    texts: dict[str, str] = {}
    for path in paths:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = Scenario.model_validate_json(line)
            if item.id in ids:
                raise ValueError(f"Duplicate id: {item.id}")
            ids.add(item.id)
            group = (item.source_id, item.scenario_id)
            if group in groups and groups[group] != item.split:
                raise ValueError(f"Scenario leaks across splits: {item.scenario_id}")
            groups[group] = item.split
            # Exact normalized prompt duplicates across splits are also rejected.
            for prompt in item.inputs:
                normalized = "".join(prompt.split()).casefold()
                if normalized in texts and texts[normalized] != item.split:
                    raise ValueError(f"Prompt leaks across splits: {item.id}")
                texts[normalized] = item.split
            items.append(item)
    if not items:
        raise ValueError("Dataset is empty")
    return items


def validate_development(items: list[Scenario]):
    if len(items) != 100 or any(item.split != "dev" for item in items):
        raise ValueError("Expected exactly 100 development scenarios")
    if Counter(item.category for item in items) != {
        "normal": 40,
        "harmful": 30,
        "boundary": 20,
        "multiturn": 10,
    }:
        raise ValueError("Unexpected category distribution")
    if Counter(item.age_band for item in items) != {"4-6": 50, "7-10": 50}:
        raise ValueError("Expected 50 scenarios in each age band")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("data/dev.jsonl")])
    parser.add_argument("--phase-one", action="store_true")
    args = parser.parse_args()
    items = load_scenarios(args.paths)
    if args.phase_one:
        validate_development(items)
    print(
        json.dumps(
            {
                "count": len(items),
                "categories": dict(Counter(item.category for item in items)),
                "age_bands": dict(Counter(item.age_band for item in items)),
                "review_status": dict(Counter(item.review_status for item in items)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
