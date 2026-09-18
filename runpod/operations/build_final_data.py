"""Expand the Codex-authored final scenario groups into age-balanced JSONL."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from runpod.operations.data import Scenario, validate_final
from runpod.settings import ROOT

SOURCE = ROOT / "data/final_v1_source.txt"
DATA = ROOT / "data/final_v1.jsonl"
MANIFEST = ROOT / "data/final_v1_manifest.json"
CATEGORIES = {"normal": 60, "harmful": 45, "boundary": 30, "multiturn": 15}
ACTIONS = {"answer", "redirect", "support", "clarify"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand(source: Path, *, reviewed: bool) -> list[Scenario]:
    groups = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("~")
        if len(fields) != 5:
            raise ValueError(f"Source line {number}: expected five fields")
        category, younger, older, actions_text, rubric = fields
        actions = actions_text.split(",")
        if (
            category not in CATEGORIES
            or not rubric.strip()
            or any(action not in ACTIONS for action in actions)
        ):
            raise ValueError(f"Source line {number}: invalid category, action or rubric")
        group_id = f"final-v1-group-{len(groups) + 1:03d}"
        pair = []
        for age, prompts in (("4-6", younger), ("7-10", older)):
            inputs = prompts.split(" || ")
            if len(inputs) != len(actions):
                raise ValueError(f"Source line {number}: action and turn counts differ")
            pair.append(
                Scenario(
                    id=f"final-v1-{len(groups) + 1:03d}-{age}",
                    source_id="codex-authored-final-v1",
                    scenario_id=group_id,
                    age_band=age,
                    category=category,
                    inputs=inputs,
                    expected_actions=actions,
                    rubric=rubric,
                    reference="runpod/configs/policy.json; final_v1_source.txt",
                    review_status="reviewed" if reviewed else "draft",
                    review_scope="project",
                    split="test",
                )
            )
        groups.append(pair)
    if Counter(pair[0].category for pair in groups) != CATEGORIES:
        raise ValueError("Final source needs 60/45/30/15 scenario groups")
    return [item for pair in groups for item in pair]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed", action="store_true")
    parser.add_argument("--output", type=Path, default=DATA)
    args = parser.parse_args()
    items = expand(SOURCE, reviewed=args.reviewed)
    if args.reviewed:
        validate_final(items)
    args.output.write_text(
        "".join(item.model_dump_json() + "\n" for item in items), encoding="utf-8"
    )
    manifest = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": digest(SOURCE),
        "data": str(args.output.relative_to(ROOT))
        if args.output.is_relative_to(ROOT)
        else str(args.output),
        "data_sha256": digest(args.output),
        "groups": 150,
        "scenarios": len(items),
        "categories": dict(Counter(item.category for item in items)),
        "age_bands": dict(Counter(item.age_band for item in items)),
        "review": "single_codex_direct" if args.reviewed else "pending",
        "human_review": False,
        "blinded": False,
    }
    if args.output == DATA:
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
