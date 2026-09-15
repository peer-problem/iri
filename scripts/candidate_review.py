"""Round-trip reviewer edits while preserving original source identity and content."""

import argparse
import csv
import json
from pathlib import Path

from scripts.prepare_training import TrainingRow

EDITABLE = (
    "adapted_question",
    "approved_answer",
    "age_band",
    "expected_action",
    "reference",
    "review_status",
    "reviewer",
)
CONTEXT = ("id", "source_question", "source_answer")


def spreadsheet_safe(value: str) -> str:
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def export_csv(source: Path, output: Path):
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    with output.open("x", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[*CONTEXT, *EDITABLE])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: spreadsheet_safe(str(row.get(key, ""))) for key in [*CONTEXT, *EDITABLE]}
            )
    return len(rows)


def import_csv(source: Path, edits: Path, output: Path):
    originals = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    by_id = {row["id"]: row for row in originals}
    if len(by_id) != len(originals):
        raise ValueError("Duplicate source ID")
    seen = set()
    with edits.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not {"id", *EDITABLE} <= set(reader.fieldnames or []):
            raise ValueError("Missing editable columns")
        for edit in reader:
            if edit["id"] not in by_id or edit["id"] in seen:
                raise ValueError("Unknown or duplicate candidate ID")
            seen.add(edit["id"])
            record = by_id[edit["id"]]
            for field in EDITABLE:
                record[field] = (edit[field] or "").strip()
            if record["review_status"] not in {"draft", "reviewed", "rejected"}:
                raise ValueError("Review status must be draft, reviewed or rejected")
            if record["review_status"] == "reviewed":
                TrainingRow(
                    id=record["id"],
                    source_id=record["source_id"],
                    scenario_id=record["scenario_id"],
                    age_band=record["age_band"],
                    question=record["adapted_question"],
                    answer=record["approved_answer"],
                    expected_action=record["expected_action"],
                    reference=record["reference"],
                    review_status="reviewed",
                    reviewer=record["reviewer"],
                )
    with output.open("x") as file:
        file.write("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in originals))
    return {
        status: sum(row["review_status"] == status for row in originals)
        for status in ("draft", "reviewed", "rejected")
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for operation in ("export", "import"):
        command = sub.add_parser(operation)
        command.add_argument("source", type=Path)
        command.add_argument("--output", type=Path, required=True)
        if operation == "import":
            command.add_argument("--edits", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        print(f"Exported {export_csv(args.source, args.output)} candidates")
    else:
        print(json.dumps(import_csv(args.source, args.edits, args.output), indent=2))


if __name__ == "__main__":
    main()
