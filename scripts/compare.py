import argparse
import json
from pathlib import Path


def compare(paths: list[Path]) -> str:
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
    lines = [
        "# 기본 모델 비교",
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
                f"| {meta['profile']} ({meta['revision'][:8]}) | {group} | {values['scenarios']} | {values['errors']} | {match if match is not None else '미측정'} | {values['p50_seconds']} | {values['p95_seconds']} |"
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    if len(args.runs) < 2:
        parser.error("Provide at least two run directories")
    print(compare(args.runs))


if __name__ == "__main__":
    main()
