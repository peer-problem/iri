import argparse
import json
from pathlib import Path

from runpod.operations.experiments import experiment_key


def compare(paths: list[Path]) -> str:
    if not paths:
        raise ValueError("At least one run is required")
    runs = [
        (
            json.loads((p / "metadata.json").read_text()),
            json.loads((p / "summary.json").read_text()),
        )
        for p in paths
    ]
    for key in ("data_sha256", "policy_sha256", "scenarios", "generation"):
        if any(meta[key] != runs[0][0][key] for meta, _ in runs):
            raise ValueError(f"Incomparable runs: {key} differs")
    for key in ("code_sha256", "guard_model"):
        if any(meta.get(key) != runs[0][0].get(key) for meta, _ in runs):
            raise ValueError(f"Incomparable runs: {key} differs")
    identities = [experiment_key(meta) for meta, _ in runs]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate experiment")
    lines = [
        "# 모델 실험 비교",
        "",
        "행동 일치는 검사 경로의 라벨 일치이며 안전성 또는 정답률이 아니다. 의미 평가는 review.csv에 별도로 기록한다.",
        "",
        "| 모델 | 경로/연령 | 문항 | 오류 | 행동 일치 | p50초 | p95초 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for meta, summary in runs:
        for group, values in summary.items():
            match = values["action_matches"]
            lines.append(
                f"| {experiment_key(meta)} | {group} | {values['scenarios']} | {values['errors']} | {match if match is not None else '미측정'} | {values['p50_seconds']} | {values['p95_seconds']} |"
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    print(compare(args.runs))


if __name__ == "__main__":
    main()
