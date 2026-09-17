"""Verify live vLLM aliases and generated responses against a saved launch record."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from runpod.inference.provider import ModelProvider
from runpod.inference.service import generation_messages
from runpod.operations.data import load_scenarios
from runpod.operations.experiments import digest, evaluation_identity
from runpod.settings import ROOT, Settings


async def verify(run: Path, launch_record: Path, output: Path, settings: Settings, client):
    if output.exists():
        raise FileExistsError(output)
    identity = evaluation_identity(settings, run)
    record = json.loads(launch_record.read_text())
    if any(record.get(key) != value for key, value in identity.items()):
        raise ValueError("Server launch record does not match this adapter experiment")
    provider = ModelProvider(settings, client)
    if not await provider.ready():
        raise ValueError("Base and adapter aliases are not both ready")
    response = await client.get(
        f"{settings.model_base_url}/models", headers=provider.headers, timeout=5
    )
    response.raise_for_status()
    models = response.json()["data"]
    adapter = next(item for item in models if item["id"] == settings.adapter_name)
    if adapter.get("root") != record.get("adapter_directory") or not record.get(
        "adapter_directory"
    ):
        raise ValueError("Server adapter path differs from the recorded files")
    if adapter.get("parent") != settings.served_model:
        raise ValueError("Server adapter parent differs from the base alias")
    examples = load_scenarios([ROOT / "data/dev.jsonl"])[:5]
    responses = []
    for item in examples:
        answer = await provider.complete(
            generation_messages(item.age_band, [{"role": "user", "content": item.inputs[0]}])
        )
        responses.append({"id": item.id, "answer": answer})
    # Also prove that the guard alias responds independently of adapter generation.
    await provider.complete([{"role": "user", "content": "안녕하세요."}], guard=True)
    report = {
        **identity,
        "state": "serving_verified_behavior_pending",
        "launch_record_sha256": digest(launch_record),
        "models": models,
        "responses": responses,
        "evidence": "Launch file hashes, matching server root/parent, alias response checks and five generations. Quality review remains pending.",
    }
    with output.open("x") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("launch_record", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    async def execute():
        async with httpx.AsyncClient(trust_env=False) as client:
            await verify(args.run, args.launch_record, args.output, Settings(), client)

    asyncio.run(execute())
    print("Serving evidence saved; human behavior evaluation is still pending")


if __name__ == "__main__":
    main()
