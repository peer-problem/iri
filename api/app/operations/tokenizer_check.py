"""Check real chat templates without downloading model weights or generating answers."""

import argparse
import json
import re
from pathlib import Path

from app.operations.data import load_scenarios
from app.provider import format_messages
from app.service import generation_messages
from app.settings import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["kanana", "gemma"], required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, default=Path("runs/tokenizer-preflight.json"))
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.revision):
        parser.error("Use the full model revision SHA")
    from transformers import AutoTokenizer

    profile = json.loads((ROOT / "configs/models.json").read_text())[args.profile]
    tokenizer = AutoTokenizer.from_pretrained(profile["model_id"], revision=args.revision)
    rows = load_scenarios([ROOT / "data/dev.jsonl"])
    lengths, boundaries = [], []
    for row in rows:
        messages = format_messages(
            generation_messages(row.age_band, [{"role": "user", "content": row.inputs[0]}]),
            profile["fold_system"],
        )
        prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(
            [*messages, {"role": "assistant", "content": "안전하게 함께 생각해 보자."}],
            tokenize=True,
            add_generation_prompt=False,
        )
        lengths.append(len(full))
        boundaries.append(full[: len(prefix)] == prefix)
    report = {
        "model": profile["model_id"],
        "revision": args.revision,
        "purpose": "Template check with a placeholder answer. No model inference or training.",
        "examples": len(rows),
        "prefix_boundary_matches": sum(boundaries),
        "min_tokens": min(lengths),
        "max_tokens": max(lengths),
        "over_1024": sum(length > 1024 for length in lengths),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(boundaries) else 1)


if __name__ == "__main__":
    main()
