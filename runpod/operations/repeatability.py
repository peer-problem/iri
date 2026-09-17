"""Replay identical first-turn model requests before comparing behavior changes."""

import argparse
import asyncio
import hashlib
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from runpod.inference.provider import ModelProvider, ModelUnavailable
from runpod.inference.service import generation_messages
from runpod.operations.artifacts import code_manifest
from runpod.operations.data import load_scenarios, validate_development
from runpod.operations.experiments import digest
from runpod.settings import Settings


def select_scenarios(items):
    """Fix 20 stratified probes before observing responses; do not tune on outcomes."""
    validate_development(items)
    if any(item.review_status != "reviewed" for item in items):
        raise ValueError("Repeatability probes require reviewed development data")
    selected = []
    for category, count in (("normal", 10), ("harmful", 5), ("boundary", 3), ("multiturn", 2)):
        group = sorted((item for item in items if item.category == category), key=lambda x: x.id)
        selected.extend(group[index * len(group) // count] for index in range(count))
    return selected


def summarize(rows, ids, passes):
    expected = {(sid, number) for sid in ids for number in range(passes)}
    actual = {(r["id"], r["pass"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("Missing or duplicate probe rows")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    changed_requests, changed_answers, errors = [], [], []
    for sid, values in grouped.items():
        if len({r["request_sha256"] for r in values}) != 1 or any(
            not r["request_sha256"] for r in values
        ):
            changed_requests.append(sid)
        if any(r["error"] for r in values):
            errors.append(sid)
        elif len({r["answer_sha256"] for r in values}) != 1:
            changed_answers.append(sid)
    return {
        "requests": len(rows),
        "scenarios": len(ids),
        "passes": passes,
        "request_mismatch_ids": sorted(changed_requests),
        "response_mismatch_ids": sorted(changed_answers),
        "error_ids": sorted(errors),
        "observed_repeatable": not (changed_requests or changed_answers or errors),
        "note": "First-turn diagnostic sample only; not a quality or universal determinism guarantee.",
    }


async def run(
    data: Path, output: Path, launch_record: Path, passes=3, settings=None, transport=None
):
    if passes < 2:
        raise ValueError("At least two passes required")
    items = select_scenarios(load_scenarios([data]))
    settings = settings or Settings()
    if settings.adapter_name:
        raise ValueError("This probe targets the fixed base model without LoRA")
    launch = json.loads(launch_record.read_text())
    if launch["revision"] != settings.model_revision or launch.get("variant") != "base":
        raise ValueError("Launch record must match the configured base model")
    output.mkdir(parents=True, exist_ok=False)
    (output / "dataset.jsonl").write_bytes(data.read_bytes())
    (output / "launch-record.json").write_bytes(launch_record.read_bytes())
    meta = {
        "state": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "data_sha256": digest(data),
        "launch_sha256": digest(launch_record),
        "revision": settings.model_revision,
        "model": settings.served_model,
        "code": code_manifest(),
        "scenario_ids": [item.id for item in items],
        "passes": passes,
        "selection": "20 evenly spaced items within category: normal 10, harmful 5, boundary 3, multiturn 2; first turn only",
        "pass_order": "forward, reverse, forward, ...; no response-dependent selection",
    }
    manifest = output / "metadata.json"
    manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    requests = []

    async def capture(request):
        if request.method == "POST":
            # Never persist headers or endpoint credentials.
            requests.append(json.loads(request.content))

    rows = []
    try:
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, event_hooks={"request": [capture]}
        ) as client:
            provider = ModelProvider(settings, client)
            if not await provider.ready():
                raise ValueError("Model endpoint is not ready")
            with (output / "results.jsonl").open("x") as stream:
                for number in range(passes):
                    order = items if number % 2 == 0 else list(reversed(items))
                    for item in order:
                        requests.clear()
                        started = time.monotonic()
                        answer, error = None, None
                        try:
                            answer = await provider.complete(
                                generation_messages(
                                    item.age_band, [{"role": "user", "content": item.inputs[0]}]
                                )
                            )
                        except (ModelUnavailable, TimeoutError) as exc:
                            error = getattr(exc, "code", "timeout")
                        body = requests[0] if len(requests) == 1 else None
                        row = {
                            "id": item.id,
                            "pass": number,
                            "request": body,
                            "request_sha256": hashlib.sha256(
                                json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
                            ).hexdigest()
                            if body is not None
                            else None,
                            "answer": answer,
                            "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()
                            if answer is not None
                            else None,
                            "error": error,
                            "seconds": round(time.monotonic() - started, 4),
                        }
                        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                        stream.flush()
                        rows.append(row)
                        print(
                            f"pass={number} {item.id} {'error' if error else 'recorded'}",
                            flush=True,
                        )
        summary = summarize(rows, meta["scenario_ids"], passes)
        (output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        )
        meta["state"] = "completed_with_errors" if summary["error_ids"] else "completed"
        return summary
    except BaseException:
        meta["state"] = "failed"
        raise
    finally:
        meta["completed_at"] = datetime.now(UTC).isoformat()
        meta["rows"] = len(rows)
        if (output / "results.jsonl").exists():
            meta["results_sha256"] = digest(output / "results.jsonl")
        manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launch-record", type=Path, required=True)
    parser.add_argument("--passes", type=int, default=3)
    args = parser.parse_args()
    result = asyncio.run(run(args.data, args.output, args.launch_record, args.passes))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2 if result["error_ids"] or result["request_mismatch_ids"] else 0)


if __name__ == "__main__":
    main()
