"""Run controlled behavior profiles and verify every result before declaring completion."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from runpod.inference.behavior import BehaviorProfile
from runpod.operations.data import load_scenarios
from runpod.operations.evaluate import evaluate

PROFILES = get_args(BehaviorProfile)
DEFAULT_PROFILES = ("baseline", "input_v2", "support_v2", "full_v2")


def preflight(data: Path) -> int:
    items = load_scenarios([data])
    if not items or any(item.split != "dev" or item.review_status != "reviewed" for item in items):
        raise ValueError("Quality comparison requires reviewed development scenarios")
    return len(items)


async def run_experiment(data: Path, output: Path, profiles=DEFAULT_PROFILES) -> dict:
    scenarios = preflight(data)
    if not profiles or len(set(profiles)) != len(profiles) or set(profiles) - set(PROFILES):
        raise ValueError("Use distinct supported behavior profiles")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "state": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "scenarios_per_profile": scenarios,
        "profiles": list(profiles),
        "runs": {},
    }
    target = output / "experiment.json"

    def save():
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    save()
    try:
        for profile in profiles:
            args = argparse.Namespace(
                data=data,
                output=output / profile,
                mode="both",
                allow_draft=False,
                limit=None,
                adapter_run=None,
                behavior_profile=profile,
            )
            code = await evaluate(args)
            files = list((output / profile).glob("*/metadata.json"))
            if len(files) != 1:
                raise ValueError("Evaluation did not produce exactly one finalized run")
            meta = json.loads(files[0].read_text())
            results = files[0].parent / "results.jsonl"
            rows = [json.loads(line) for line in results.read_text().splitlines()]
            expected_keys = {
                (item.id, mode) for item in load_scenarios([data]) for mode in ("raw", "guarded")
            }
            if (
                code not in {0, 2}
                or meta.get("state") not in {"completed", "completed_with_errors"}
                or meta.get("result_rows") != scenarios * 2
                or meta.get("behavior_profile") != profile
                or meta.get("data_sha256") != manifest["data_sha256"]
                or hashlib.sha256(results.read_bytes()).hexdigest() != meta.get("results_sha256")
                or len(rows) != len(expected_keys)
                or {(row["id"], row["mode"]) for row in rows} != expected_keys
            ):
                raise ValueError("Evaluation evidence is missing or inconsistent")
            manifest["runs"][profile] = {
                "path": str(files[0].parent.relative_to(output)),
                "state": meta["state"],
                "results_sha256": meta["results_sha256"],
                "experiment_id": meta["experiment_id"],
            }
            save()
        manifest["state"] = (
            "completed_with_errors"
            if any(r["state"] == "completed_with_errors" for r in manifest["runs"].values())
            else "completed"
        )
    except Exception as exc:
        manifest.update(state="failed", error_type=type(exc).__name__)
        raise
    finally:
        save()
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=DEFAULT_PROFILES)
    args = parser.parse_args()
    result = asyncio.run(run_experiment(args.data, args.output, args.profiles))
    print(f"Quality experiment {result['state']}")
    raise SystemExit(2 if result["state"] == "completed_with_errors" else 0)


if __name__ == "__main__":
    main()
