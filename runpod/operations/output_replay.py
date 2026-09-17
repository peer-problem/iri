"""Freeze recorded development answers, then replay only the existing output guard."""

import argparse
import asyncio
import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.schemas import OutputVerdict
from runpod.inference.service import FALLBACKS, POLICY, output_guard_messages
from runpod.inference.trace import TurnTrace
from runpod.operations.artifacts import code_manifest
from runpod.operations.data import load_scenarios, validate_development
from runpod.operations.experiments import digest
from runpod.settings import Settings

SOURCE_FILES = ("metadata.json", "dataset.jsonl", "results.jsonl", "policy.json")
PROFILES = ("baseline", "safety_v3")


def json_hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_source(source: Path):
    meta = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    items = load_scenarios([source / "dataset.jsonl"])
    validate_development(items)
    if (
        meta.get("state") != "completed"
        or meta.get("variant") != "base"
        or meta.get("adapter_sha256") is not None
        or any(item.review_status != "reviewed" for item in items)
        or meta.get("results_sha256") != digest(source / "results.jsonl")
        or meta.get("dataset_snapshot_sha256", meta.get("data_sha256"))
        != digest(source / "dataset.jsonl")
        or meta.get("policy_sha256") != digest(source / "policy.json")
    ):
        raise ValueError("Replay source must be a verified completed base-model dev100 run")
    rows = [
        json.loads(line)
        for line in (source / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    expected = {(item.id, mode) for item in items for mode in ("raw", "guarded")}
    if (
        meta.get("result_rows") != 200
        or len(rows) != 200
        or {(row["id"], row["mode"]) for row in rows} != expected
    ):
        raise ValueError("Replay source must contain all 200 unique development results")
    by_id = {item.id: item for item in items}
    for row in rows:
        item = by_id[row["id"]]
        turns = row["turns"]
        if (
            row.get("error") is not None
            or row["age_band"] != item.age_band
            or len(turns) != len(item.inputs)
            or [turn["question"] for turn in turns] != item.inputs
            or [turn["expected_action"] for turn in turns] != item.expected_actions
            or any(
                not isinstance(turn["answer"], str)
                or not turn["answer"].strip()
                or len(turn["answer"]) > 8000
                for turn in turns
            )
        ):
            raise ValueError("Replay source turns do not match the frozen development data")
    return meta, rows


def build_cases(rows, ids, mode):
    known = {row["id"] for row in rows}
    if mode not in {"raw", "guarded"} or not ids or len(set(ids)) != len(ids) or set(ids) - known:
        raise ValueError("Select distinct existing scenario IDs and one source mode")
    cases = []
    for row in sorted(rows, key=lambda row: row["id"]):
        if row["id"] not in ids or row["mode"] != mode:
            continue
        history = []
        for number, turn in enumerate(row["turns"], 1):
            history.append({"role": "user", "content": turn["question"]})
            case = {
                "id": row["id"],
                "mode": mode,
                "turn": number,
                "age_band": row["age_band"],
                "conversation": [dict(message) for message in history],
                "candidate": turn["answer"],
                "source_action": turn["action"],
                "candidate_kind": "fallback_text"
                if turn["answer"] in FALLBACKS.values()
                else "recorded_response",
            }
            case["candidate_context_sha256"] = json_hash(case)
            cases.append(case)
            history.append({"role": "assistant", "content": turn["answer"]})
    return cases


def prepare(source: Path, output: Path, ids=None, mode="guarded"):
    """Local only: no Settings(), credentials, model connection or new generation."""
    meta, rows = read_source(source)
    selected = sorted(ids if ids is not None else {row["id"] for row in rows})
    document = {
        "version": 1,
        "purpose": "fixed_output_guard_diagnostic_not_a_quality_score",
        "source_sha256": {name: digest(source / name) for name in SOURCE_FILES},
        "source_experiment_id": meta["experiment_id"],
        "source_behavior_profile": meta["behavior_profile"],
        "selection": {"ids": selected, "mode": mode},
        "cases": build_cases(rows, selected, mode),
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "source").mkdir()
    for name in SOURCE_FILES:
        shutil.copyfile(source / name, output / "source" / name)
    save_json(output / "packet.json", document)
    packet_hash = digest(output / "packet.json")
    load_packet(output, packet_hash)
    return {"packet_sha256": packet_hash, "candidates": len(document["cases"])}


def load_packet(packet: Path, expected_sha256: str):
    if digest(packet / "packet.json") != expected_sha256:
        raise ValueError("Frozen packet hash changed")
    document = json.loads((packet / "packet.json").read_text(encoding="utf-8"))
    if document.get("version") != 1 or document.get("source_sha256") != {
        name: digest(packet / "source" / name) for name in SOURCE_FILES
    }:
        raise ValueError("Frozen source hashes changed")
    meta, rows = read_source(packet / "source")
    selection = document["selection"]
    if (
        document["source_experiment_id"] != meta["experiment_id"]
        or document["source_behavior_profile"] != meta["behavior_profile"]
        or document["cases"] != build_cases(rows, selection["ids"], selection["mode"])
    ):
        raise ValueError("Frozen candidates differ from their source conversations")
    return document, meta


def validate_launch(launch, settings, source_meta):
    command = launch.get("command", [])
    if not isinstance(command, list):
        raise ValueError("Invalid launch command record")

    def flag(name):
        return (
            command[command.index(name) + 1]
            if command.count(name) == 1 and command.index(name) + 1 < len(command)
            else None
        )

    if (
        settings.adapter_name
        or source_meta["revision"] != settings.model_revision
        or source_meta["model_id"] != settings.profile["model_id"]
        or source_meta["policy_sha256"] != hashlib.sha256(POLICY.encode("utf-8")).hexdigest()
        or launch.get("revision") != settings.model_revision
        or launch.get("model_id") != settings.profile["model_id"]
        or launch.get("variant") != "base"
        or launch.get("adapter_sha256") is not None
        or launch.get("vllm") != "0.29.0"
        or launch.get("prefix_caching_requested") != "on"
        or launch.get("batch_invariant") != "1"
        or flag("--dtype") != "bfloat16"
        or flag("--max-num-seqs") != "1"
        or flag("--max-model-len") != "4096"
        or flag("--revision") != settings.model_revision
        or flag("--tokenizer-revision") != settings.model_revision
        or flag("--served-model-name") != settings.served_model
        or "--enable-prefix-caching" not in command
        or "--no-enable-prefix-caching" in command
        or "--enable-lora" in command
        or "--lora-modules" in command
    ):
        raise ValueError(
            "Replay requires the matching base model, policy and fixed server conditions"
        )
    # Only allowlisted environment fields are copied; command/headers/keys are not logged.
    return {
        key: launch.get(key)
        for key in (
            "revision",
            "model_id",
            "variant",
            "gpu",
            "vllm",
            "prefix_caching_requested",
            "batch_invariant",
        )
    } | {
        "dtype": flag("--dtype"),
        "max_num_seqs": flag("--max-num-seqs"),
        "max_model_len": flag("--max-model-len"),
    }


async def run(
    packet,
    expected_sha256,
    output,
    launch_record,
    profiles=PROFILES,
    passes=1,
    *,
    settings=None,
    transport=None,
):
    document, source_meta = load_packet(packet, expected_sha256)
    if not profiles or len(set(profiles)) != len(profiles) or set(profiles) - set(PROFILES):
        raise ValueError("Use distinct supported output guard profiles")
    if type(passes) is not int or not 1 <= passes <= 10:
        raise ValueError("Replay passes must be between 1 and 10")
    settings = settings or Settings()
    launch = json.loads(launch_record.read_text(encoding="utf-8"))
    environment = validate_launch(launch, settings, source_meta)
    output.mkdir(parents=True, exist_ok=False)
    (output / "source").mkdir()
    for name in SOURCE_FILES:
        shutil.copyfile(packet / "source" / name, output / "source" / name)
    shutil.copyfile(packet / "packet.json", output / "packet.json")
    load_packet(output, expected_sha256)
    meta = {
        "state": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "kind": "output_guard_only",
        "packet_sha256": expected_sha256,
        "launch_sha256": digest(launch_record),
        "environment": environment,
        "profiles": list(profiles),
        "passes": passes,
        "code": code_manifest(),
        "expected_calls": len(document["cases"]) * len(profiles) * passes,
        "guard_max_tokens": 80,
        "temperature": 0,
        "seed": 42,
        "note": "Selected recorded responses, not original blocked candidates; no generation, input guard or quality score. Launch record is not live hardware attestation.",
    }
    manifest = output / "metadata.json"
    save_json(manifest, meta)
    rows = []
    request_hashes = []

    async def capture(request):
        if request.method == "POST":
            request_hashes.append(json_hash(json.loads(request.content)))

    try:
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, event_hooks={"request": [capture]}
        ) as client:
            provider = ModelProvider(settings, client)
            if not await provider.ready():
                raise ModelUnavailable("Model is not ready", code="not_ready")
            with (output / "results.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
                for profile in profiles:
                    for number in range(1, passes + 1):
                        for case in document["cases"]:
                            request_hashes.clear()
                            trace = TurnTrace()
                            try:
                                async with asyncio.timeout(settings.request_timeout_seconds):
                                    with trace.measure("output_guard") as stage:
                                        checked = OutputVerdict.model_validate_json(
                                            await provider.complete(
                                                output_guard_messages(
                                                    case["age_band"],
                                                    case["conversation"],
                                                    case["candidate"],
                                                    profile,
                                                ),
                                                max_tokens=80,
                                                guard=True,
                                                response_schema=OutputVerdict.model_json_schema(),
                                            )
                                        )
                                        stage.decision = checked.decision
                            except (ModelUnavailable, TimeoutError, ValidationError):
                                pass  # Failed judgement stays an error, never a synthetic block.
                            finally:
                                row = {
                                    "id": case["id"],
                                    "mode": case["mode"],
                                    "turn": case["turn"],
                                    "profile": profile,
                                    "pass": number,
                                    "candidate_context_sha256": case["candidate_context_sha256"],
                                    "candidate_characters": len(case["candidate"]),
                                    "request_sha256": request_hashes[0]
                                    if len(request_hashes) == 1
                                    else None,
                                    "request_count": len(request_hashes),
                                    "output_guard": asdict(trace.stages["output_guard"]),
                                }
                                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                                stream.flush()
                                rows.append(row)
                            print(
                                f"{profile} pass={number} {case['id']} turn={case['turn']}: recorded",
                                flush=True,
                            )
        expected = {
            (profile, number, case["id"], case["mode"], case["turn"])
            for profile in profiles
            for number in range(1, passes + 1)
            for case in document["cases"]
        }
        actual = {
            (row["profile"], row["pass"], row["id"], row["mode"], row["turn"]) for row in rows
        }
        if (
            len(rows) != len(expected)
            or actual != expected
            or any(row["request_count"] != 1 for row in rows)
        ):
            raise ValueError("Replay request pairs are missing or duplicated")
        meta["errors"] = sum(row["output_guard"]["status"] != "completed" for row in rows)
        meta["state"] = "completed_with_errors" if meta["errors"] else "completed"
        return meta
    except BaseException:
        meta["state"] = "failed"
        raise
    finally:
        meta["finished_at"] = datetime.now(UTC).isoformat()
        meta["rows"] = len(rows)
        if (output / "results.jsonl").exists():
            meta["results_sha256"] = digest(output / "results.jsonl")
        save_json(manifest, meta)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("prepare", help="Local-only snapshot preparation")
    freeze.add_argument("--run", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--ids", nargs="+")
    freeze.add_argument("--mode", choices=("raw", "guarded"), default="guarded")
    execute = commands.add_parser("run", help="Calls a running model server; preflight required")
    execute.add_argument("--packet", type=Path, required=True)
    execute.add_argument("--expected-sha256", required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--launch-record", type=Path, required=True)
    execute.add_argument("--profiles", nargs="+", choices=PROFILES, default=PROFILES)
    execute.add_argument("--passes", type=int, default=1)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.run, args.output, args.ids, args.mode)
        else:
            result = asyncio.run(
                run(
                    args.packet,
                    args.expected_sha256,
                    args.output,
                    args.launch_record,
                    args.profiles,
                    args.passes,
                )
            )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        # Parser errors can contain source text. Do not print raw exception bodies.
        parser.exit(
            2, f"Output replay failed ({type(exc).__name__}); check inputs and saved metadata.\n"
        )
    if args.command == "run" and result["state"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
