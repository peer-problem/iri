"""CPU-testable assistant-only label preparation shared by the GPU trainer."""

import json
from pathlib import Path

from api.app.service import generation_messages
from runpod.operations.prepare_training import TrainingRow
from runpod.operations.source_square import normalized


def load_training(train_path: Path, validation_path: Path):
    splits = []
    groups, questions, identifiers = {}, {}, set()
    for path, split in ((train_path, "train"), (validation_path, "validation")):
        rows = [
            TrainingRow.model_validate_json(line)
            for line in path.read_text().splitlines()
            if line.strip()
        ]
        if not rows:
            raise ValueError(f"Empty {split} split")
        for row in rows:
            if row.split != split or row.id in identifiers:
                raise ValueError("Split label mismatch or duplicate training ID")
            identifiers.add(row.id)
            group = (row.source_id, row.scenario_id)
            question = normalized(row.question)
            if (group in groups and groups[group] != split) or (
                question in questions and questions[question] != split
            ):
                raise ValueError("Training and validation leakage")
            groups[group], questions[question] = split, split
        splits.append(rows)
    return splits


def encode_row(row: TrainingRow, tokenizer, max_length: int) -> dict:
    messages = generation_messages(row.age_band, [{"role": "user", "content": row.question}])
    prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(
        [*messages, {"role": "assistant", "content": row.answer}],
        tokenize=True,
        add_generation_prompt=False,
    )
    if full[: len(prefix)] != prefix or len(full) <= len(prefix):
        raise ValueError(f"Chat template does not preserve the assistant boundary: {row.id}")
    if len(full) > max_length:
        raise ValueError(f"Example exceeds context limit ({len(full)} > {max_length}): {row.id}")
    return {
        "input_ids": full,
        "attention_mask": [1] * len(full),
        "labels": [-100] * len(prefix) + full[len(prefix) :],
    }


def pad_batch(features: list[dict], pad_token_id: int) -> dict:
    length = max(len(feature["input_ids"]) for feature in features)
    return {
        key: [feature[key] + [padding] * (length - len(feature[key])) for feature in features]
        for key, padding in (("input_ids", pad_token_id), ("attention_mask", 0), ("labels", -100))
    }


def data_fingerprint(paths: list[Path]) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(
            {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, sort_keys=True
        ).encode()
    ).hexdigest()
