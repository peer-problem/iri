"""Fetch the pinned official training split and prepare unapproved review candidates."""

import argparse
import hashlib
import json
import os
import unicodedata
from collections import Counter
from pathlib import Path

import httpx

REPOSITORY = "naver-ai/korean-safety-benchmarks"
REVISION = "e32837cd19c45564ab00083fbb2a4b89ecdf83f3"
SOURCE_PATH = "data/SQuARe/response_train.json"
CHILD_CONTEXT = (
    "학교",
    "친구",
    "부모",
    "아이",
    "선생",
    "장난",
    "괴롭",
    "욕",
    "게임",
    "어린",
    "동생",
)


def normalized(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


def question_group(question: str) -> str:
    return hashlib.sha256(normalized(question).encode()).hexdigest()


def git_blob_sha(path: Path) -> str:
    digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def candidates(records: list[dict], limit: int) -> list[dict]:
    pool = []
    for item in records:
        if item.get("acceptable?") != 1:
            continue
        question, answer = item.get("question", ""), item.get("response", "")
        if not isinstance(question, str) or not isinstance(answer, str):
            continue
        score = sum(word in question for word in CHILD_CONTEXT)
        if not score or not 1 <= len(question) <= 200 or not 1 <= len(answer) <= 1500:
            continue
        identity = hashlib.sha256((question + "\0" + answer).encode()).hexdigest()
        pool.append((-score, identity, item))
    selected, groups = [], set()
    for _, identity, item in sorted(pool, key=lambda row: (row[0], row[1])):
        group = question_group(item["question"])
        if group in groups:
            continue
        groups.add(group)
        selected.append(
            {
                "id": f"square-{identity[:20]}",
                "source_id": "naver-square",
                "source_revision": REVISION,
                "scenario_id": group,
                "source_split": "train",
                "source_question": item["question"],
                "source_answer": item["response"],
                "source_acceptable": True,
                "source_category": item.get("question_category"),
                "adapted_question": "",
                "approved_answer": "",
                "age_band": "",
                "expected_action": "",
                "review_status": "draft",
                "reviewer": "",
                "reference": "",
                "selection_note": "Keyword-ranked review candidate. Adult acceptability is not child suitability.",
            }
        )
        if len(selected) == limit:
            break
    return selected


def fetch_and_prepare(output: Path, limit: int):
    output.mkdir(parents=True, exist_ok=True)
    path = output / "response_train.json"
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        tree = client.get(
            f"https://api.github.com/repos/{REPOSITORY}/git/trees/{REVISION}",
            params={"recursive": "1"},
        )
        tree.raise_for_status()
        entry = next(item for item in tree.json()["tree"] if item["path"] == SOURCE_PATH)
        if not path.exists():
            temporary = output / ".response_train.part"
            try:
                with client.stream(
                    "GET",
                    f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/{SOURCE_PATH}",
                ) as response:
                    response.raise_for_status()
                    with temporary.open("xb") as file:
                        total = 0
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > entry["size"]:
                                raise ValueError("Source exceeded its pinned size")
                            file.write(chunk)
                if git_blob_sha(temporary) != entry["sha"]:
                    raise ValueError("Source checksum mismatch")
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        if git_blob_sha(path) != entry["sha"]:
            raise ValueError("Cached source checksum mismatch")
        notices = {}
        for filename in ("LICENSE", "NOTICE"):
            response = client.get(
                f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/{filename}"
            )
            response.raise_for_status()
            notices[filename] = response.text
    records = json.loads(path.read_text())
    selected = candidates(records, limit)
    # Never overwrite a human's edited candidate file.
    target = output / "candidates.jsonl"
    if target.exists():
        raise ValueError("Candidate file already exists; human edits were preserved")
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected))
    provenance = {
        "source": f"https://github.com/{REPOSITORY}",
        "revision": REVISION,
        "file": SOURCE_PATH,
        "git_blob_sha": entry["sha"],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_records": len(records),
        "source_acceptability": dict(Counter(str(r.get("acceptable?")) for r in records)),
        "candidate_records": len(selected),
        "review_status": "draft",
        "training_records_approved": 0,
        "original_notices": notices,
    }
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2))
    return {
        key: provenance[key]
        for key in (
            "revision",
            "source_records",
            "source_acceptability",
            "candidate_records",
            "training_records_approved",
        )
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw/square"))
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    print(json.dumps(fetch_and_prepare(args.output, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
