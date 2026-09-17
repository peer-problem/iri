"""Report readiness without printing secrets or issuing billable API requests."""

import argparse
import asyncio
import json
import platform
import shutil
import subprocess

import httpx
from dotenv import dotenv_values
from pydantic import ValidationError

from runpod.inference.provider import ModelProvider
from runpod.operations.data import load_scenarios, validate_development
from runpod.settings import ENV_FILE, REPO_ROOT, ROOT, Settings


async def inspect(online: bool = False) -> dict:
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    add(
        "python",
        "pass" if platform.python_version_tuple()[:2] == ("3", "12") else "fail",
        platform.python_version(),
    )
    try:
        settings = Settings()
        add("configuration", "pass", "Settings schema is valid; secret values are hidden")
    except ValidationError as exc:
        add(
            "configuration",
            "fail",
            {"invalid_fields": sorted({str(error["loc"][0]) for error in exc.errors()})},
        )
        settings = None
    env = ENV_FILE
    add(
        "private_env",
        "pass" if env.exists() and env.stat().st_mode & 0o077 == 0 else "pending",
        "Use runpod.operations.init_local for a private .keys/.env",
    )
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "AGENTS.md",
            ".agents/MASTERPLAN.md",
            ".keys/.env",
            ".keys/runpod-ed25519",
            ".keys/runpod-ed25519.pub",
            "runpod/known_hosts",
            "runpod/runs/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    add(
        "git_exclusions",
        "pass" if len(ignored.stdout.splitlines()) == 7 else "fail",
        "AGENTS.md, .agents, credentials in .keys and runs must stay excluded",
    )
    try:
        items = load_scenarios([(ROOT / "data/dev.jsonl")])
        validate_development(items)
        drafts = sum(item.review_status != "reviewed" for item in items)
        add("development_data", "pass", {"count": len(items), "drafts": drafts})
        add(
            "human_review",
            "pending" if drafts else "pass",
            "Draft labels need human review before formal evaluation",
        )
    except (ValueError, OSError):
        add(
            "development_data",
            "fail",
            "Run runpod.operations.data --phase-one to locate invalid data",
        )
    values = dotenv_values(env) if env.exists() else {}
    import os

    hf_present = bool(os.environ.get("HF_TOKEN") or values.get("HF_TOKEN"))
    add(
        "hf_token",
        "pass" if hf_present else "pending",
        "Download token presence only; no value printed",
    )
    add("model_connection", "pending", "Use --online to check the configured model endpoint")
    if settings:
        add(
            "model_revision",
            "pass" if settings.model_revision else "pending",
            "Set the resolved commit SHA before GPU execution",
        )
        if online:
            async with httpx.AsyncClient(trust_env=False) as client:
                ready = await ModelProvider(settings, client).ready()
            checks[:] = [c for c in checks if c["name"] != "model_connection"]
            add(
                "model_connection",
                "pass" if ready else "pending",
                "Read-only /models readiness check",
            )
    add(
        "nvidia_gpu",
        "pass" if shutil.which("nvidia-smi") else "pending",
        "GPU is not required for local inference tests",
    )
    return {
        "checks": checks,
        "failures": sum(c["status"] == "fail" for c in checks),
        "pending": sum(c["status"] == "pending" for c in checks),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(inspect(args.online))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["failures"] else 0)


if __name__ == "__main__":
    main()
