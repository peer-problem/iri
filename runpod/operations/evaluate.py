import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args
from uuid import uuid4

import httpx

from runpod.inference.behavior import BehaviorProfile
from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.service import POLICY, ChatService, generation_messages
from runpod.operations.artifacts import code_manifest
from runpod.operations.data import load_scenarios
from runpod.operations.experiments import evaluation_identity
from runpod.settings import ROOT, Settings


def percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    return round(sorted(values)[max(0, math.ceil(len(values) * proportion) - 1)], 3)


def summarize(rows: list[dict]) -> dict:
    result = {}
    for mode in sorted({row["mode"] for row in rows}):
        for age in ("all", "4-6", "7-10"):
            subset = [
                r for r in rows if r["mode"] == mode and (age == "all" or r["age_band"] == age)
            ]
            successful = [r for r in subset if not r["error"]]
            result[f"{mode}/{age}"] = {
                "scenarios": len(subset),
                "errors": len(subset) - len(successful),
                # Not a safety metric. A raw text response has no action classifier.
                "action_matches": sum(r["action_match"] is True for r in subset)
                if mode == "guarded"
                else None,
                "p50_seconds": percentile([r["seconds"] for r in successful], 0.5),
                "p95_seconds": percentile([r["seconds"] for r in successful], 0.95),
            }
    return result


async def evaluate(args):
    settings = Settings()
    if getattr(args, "behavior_profile", None):
        settings = settings.model_copy(update={"behavior_profile": args.behavior_profile})
    experiment = evaluation_identity(settings, getattr(args, "adapter_run", None))
    items = load_scenarios([args.data])
    if any(item.split != "dev" for item in items):
        raise ValueError("This command only runs development data")
    if not args.allow_draft and any(item.review_status != "reviewed" for item in items):
        raise ValueError("Human review is pending. Use --allow-draft only for exploratory runs")
    if args.limit:
        items = items[: args.limit]
    async with httpx.AsyncClient(trust_env=False) as client:
        provider = ModelProvider(settings, client)
        if not await provider.ready():
            raise ModelUnavailable("Model not ready. Follow README.md")
        service = ChatService(provider)
        run_dir = (
            args.output
            / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{settings.model_profile}-{uuid4().hex[:8]}"
        )
        run_dir.mkdir(parents=True, exist_ok=False)
        git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        metadata = {
            **experiment,
            "state": "running",
            "created_at": datetime.now(UTC).isoformat(),
            "model_id": settings.profile["model_id"],
            "revision": settings.model_revision,
            "profile": settings.model_profile,
            "fold_system": False,  # Preserve historical metadata format; Kanana uses system roles.
            "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
            "policy_sha256": hashlib.sha256(POLICY.encode()).hexdigest(),
            "git_commit": git.stdout.strip() if git.returncode == 0 else None,
            "git_dirty": bool(status.stdout.strip()),
            "python": platform.python_version(),
            "packages": {
                name: importlib.metadata.version(name) for name in ("httpx", "pydantic", "pydantic-settings")
            },
            "generation": {
                "temperature": 0,
                "seed": 42,
                "max_tokens": 384,
                "guard_max_tokens": 80,
                "guard_response_format": "json_schema",
            },
            "scenarios": len(items),
            "scenario_ids": [item.id for item in items],
            "code_sha256": code_manifest()["sha256"],
            "review_status": "draft"
            if any(i.review_status == "draft" for i in items)
            else "reviewed",
            "gpu_manifest": "Attach runs/gpu-environment.json and gpu-packages.txt from the Pod",
        }
        (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        (run_dir / "dataset.jsonl").write_text(
            "".join(item.model_dump_json() + "\n" for item in items)
        )
        metadata["dataset_snapshot_sha256"] = hashlib.sha256(
            (run_dir / "dataset.jsonl").read_bytes()
        ).hexdigest()
        (run_dir / "policy.json").write_text(POLICY)
        rows = []
        modes = ("raw", "guarded") if args.mode == "both" else (args.mode,)
        with (run_dir / "results.jsonl").open("w") as output:
            for item in items:
                for mode in modes:
                    history, turns, error, error_detail = [], [], None, None
                    start = time.monotonic()
                    for question, expected in zip(item.inputs, item.expected_actions, strict=True):
                        history.append({"role": "user", "content": question})
                        try:
                            async with asyncio.timeout(settings.request_timeout_seconds):
                                if mode == "raw":
                                    answer = await provider.complete(
                                        generation_messages(
                                            item.age_band, history, settings.behavior_profile
                                        )
                                    )
                                    action = None
                                else:
                                    answer, action = await service.respond(item.age_band, history)
                            turns.append(
                                {
                                    "question": question,
                                    "answer": answer,
                                    "action": action,
                                    "expected_action": expected,
                                }
                            )
                            history.append({"role": "assistant", "content": answer})
                        except (ModelUnavailable, TimeoutError) as exc:
                            error = type(exc).__name__
                            error_detail = {
                                "code": exc.code
                                if isinstance(exc, ModelUnavailable)
                                else "timeout",
                                "stage": (exc.stage or "generation")
                                if isinstance(exc, ModelUnavailable)
                                else "turn",
                                "turn": len(turns) + 1,
                            }
                            break
                    row = {
                        "id": item.id,
                        "age_band": item.age_band,
                        "category": item.category,
                        "mode": mode,
                        "turns": turns,
                        "error": error,
                        "error_detail": error_detail,
                        "seconds": round(time.monotonic() - start, 3),
                        "action_match": (
                            not error and all(t["action"] == t["expected_action"] for t in turns)
                        )
                        if mode == "guarded"
                        else None,
                        "rubric": item.rubric,
                        "expected_actions": item.expected_actions,
                    }
                    rows.append(row)
                    output.write(json.dumps(row, ensure_ascii=False) + "\n")
                    output.flush()
                    print(f"{item.id} {mode}: {'error' if error else 'recorded'}", flush=True)
        summary = summarize(rows)
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        fields = [
            "id",
            "mode",
            "age_band",
            "rubric",
            "reviewer",
            "harmful_exposure",
            "over_refusal",
            "correct",
            "age_appropriate",
            "support_appropriate",
            "notes",
        ]
        with (run_dir / "review.csv").open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row[key] for key in ("id", "mode", "age_band", "rubric")})
        print(f"Results: {run_dir}")
        metadata["state"] = (
            "completed_with_errors" if any(row["error"] for row in rows) else "completed"
        )
        metadata["result_rows"] = len(rows)
        metadata["results_sha256"] = hashlib.sha256(
            (run_dir / "results.jsonl").read_bytes()
        ).hexdigest()
        (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 2 if any(row["error"] for row in rows) else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=(ROOT / "data/dev.jsonl"))
    parser.add_argument("--output", type=Path, default=(ROOT / "runs"))
    parser.add_argument("--mode", choices=["raw", "guarded", "both"], default="both")
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--adapter-run", type=Path)
    parser.add_argument("--behavior-profile", choices=get_args(BehaviorProfile))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        raise SystemExit(asyncio.run(evaluate(args)))
    except (ValueError, ModelUnavailable) as exc:
        # Only locally constructed errors are printed, never upstream bodies or keys.
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
