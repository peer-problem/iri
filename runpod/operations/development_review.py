"""Import scoped label reviews without editing generation inputs."""

import argparse
import csv
import json
from pathlib import Path

from runpod.operations.candidate_review import spreadsheet_safe
from runpod.operations.data import Scenario, load_scenarios, validate_development
from runpod.operations.experiments import digest

FIELDS = (
    "id",
    "age_band",
    "category",
    "inputs",
    "expected_actions",
    "rubric",
    "reference",
    "review_status",
    "reviewer",
    "notes",
)


def export(source: Path, output: Path):
    items = load_scenarios([source])
    validate_development(items)
    with output.open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for item in items:
            row = item.model_dump()
            row["inputs"] = json.dumps(item.inputs, ensure_ascii=False)
            row["expected_actions"] = json.dumps(item.expected_actions)
            writer.writerow({key: spreadsheet_safe(str(row.get(key, ""))) for key in FIELDS})


def import_labels(source: Path, edits: Path, output: Path, review_scope: str = "human"):
    if review_scope not in {"human", "project"}:
        raise ValueError("Review scope must be human or project")
    original = load_scenarios([source])
    by_id = {item.id: item for item in original}
    decisions, updates = {}, {}
    with edits.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            key = row["id"]
            if key not in by_id or key in updates:
                raise ValueError("Unknown or duplicate development ID")
            status, reviewer = row["review_status"].strip(), row["reviewer"].strip()
            if status == "reviewed" and (
                not reviewer
                or reviewer.casefold() in {"todo", "pending", "unknown"}
                or (review_scope == "human" and reviewer.casefold().startswith(("codex_ai", "ai_")))
            ):
                raise ValueError("Human approval requires an identified human reviewer")
            changed = by_id[key].model_dump()
            changed.update(
                expected_actions=json.loads(row["expected_actions"]),
                rubric=row["rubric"].strip(),
                reference=row["reference"].strip(),
                review_status=status,
                review_scope=review_scope,
            )
            if status == "reviewed" and not changed["reference"]:
                raise ValueError("Reviewed labels require a reference or written rationale")
            updates[key] = Scenario.model_validate(changed)
            decisions[key] = {
                "reviewer": reviewer,
                "notes": row["notes"],
                "review_status": status,
                "review_scope": review_scope,
            }
    if updates.keys() != by_id.keys():
        raise ValueError("Review must cover all 100 development scenarios")
    items = [updates[item.id] for item in original]
    validate_development(items)
    output.mkdir(parents=True, exist_ok=False)
    (output / "dev.jsonl").write_text("".join(item.model_dump_json() + "\n" for item in items))
    (output / "review-manifest.json").write_text(
        json.dumps(
            {
                "source_sha256": digest(source),
                "edits_sha256": digest(edits),
                "data_sha256": digest(output / "dev.jsonl"),
                "generation_inputs_changed": False,
                "review_scope": review_scope,
                "decisions": decisions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return sum(item.review_status == "reviewed" for item in items)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "import"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        command.add_argument("--output", type=Path, required=True)
        if name == "import":
            command.add_argument("--edits", type=Path, required=True)
            command.add_argument("--review-scope", choices=("human", "project"), default="human")
    args = parser.parse_args()
    if args.command == "export":
        export(args.source, args.output)
        print("Exported 100 scenarios for human label review")
    else:
        count = import_labels(args.source, args.edits, args.output, args.review_scope)
        print(f"Imported {count} reviewed labels ({args.review_scope})")


if __name__ == "__main__":
    main()
