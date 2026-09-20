"""Replay the Phase 2 regression scenarios against the product chat endpoint.

This measures the deployed guarded path in `api/app`, not the research evaluation
path in `runpod/operations/evaluate.py`. Internal bearer authentication skips the
browser session, so every request is an independent single turn with no stored
history and no `previous_action`. Multi-turn support follow-ups are therefore
outside the scope of this run.

Usage:
    runpod/.venv/bin/python api/regression/run_regression.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "runpod/data/regression/phase2-failures.jsonl"
DEFAULT_OUTPUT = ROOT / "api/regression/runs"
ENV_FILE = ROOT / ".keys/.env"


def read_key() -> str:
    """Read the internal API key from the environment or `.keys/.env`."""
    key = os.environ.get("SANDBOX_API_KEY")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "SANDBOX_API_KEY":
                return value.strip().strip('"').strip("'")
    raise SystemExit("SANDBOX_API_KEY is not set in the environment or .keys/.env")


def git_state() -> dict:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                args, cwd=ROOT, capture_output=True, text=True, check=True
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return result.stdout.strip()

    status = run("git", "status", "--porcelain")
    return {
        "commit": run("git", "rev-parse", "HEAD"),
        "branch": run("git", "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
    }


def load_scenarios(path: Path) -> list[dict]:
    scenarios = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            scenarios.append(json.loads(stripped))
        except json.JSONDecodeError as reason:
            raise SystemExit(f"{path}:{number} is not valid JSON: {reason}") from reason
    return scenarios


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ask(base_url: str, key: str, scenario: dict, timeout: float) -> dict:
    """Send one scenario. A fresh client per call keeps the turns independent."""
    inputs = scenario.get("inputs") or []
    row = {
        "id": scenario.get("id"),
        "age_band": scenario.get("age_band"),
        "category": scenario.get("category"),
        "expected_actions": scenario.get("expected_actions"),
        "message": inputs[0] if inputs else None,
        "dropped_inputs": max(0, len(inputs) - 1),
        "status": None,
        "answer": None,
        "action": None,
        "provider": None,
        "request_id": None,
        "expected_match": None,
        "elapsed_ms": None,
        "error": None,
    }
    if row["message"] is None:
        row["error"] = "scenario has no inputs"
        return row

    body = {"age_band": row["age_band"], "message": row["message"]}
    headers = {"Authorization": f"Bearer {key}"}
    started = time.perf_counter()
    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            response = client.post("/chat", json=body, headers=headers)
    except httpx.HTTPError as reason:
        row["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        row["error"] = f"{type(reason).__name__}: {reason}"
        return row

    row["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    row["status"] = response.status_code
    if response.status_code != 200:
        row["error"] = response.text[:500]
        return row

    try:
        payload = response.json()
    except ValueError as reason:
        row["error"] = f"response is not JSON: {reason}"
        return row

    row["answer"] = payload.get("answer")
    row["action"] = payload.get("action")
    row["provider"] = payload.get("provider")
    row["request_id"] = payload.get("request_id")
    expected = row["expected_actions"] or []
    if row["action"] is not None and expected:
        row["expected_match"] = row["action"] in expected
    return row


def service_state(base_url: str, key: str, timeout: float) -> dict:
    """Record what the API reports about itself, so the run is interpretable later."""
    state = {}
    for endpoint in ("/health", "/ready"):
        try:
            with httpx.Client(base_url=base_url, timeout=timeout) as client:
                response = client.get(endpoint, headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError as reason:
            state[endpoint] = {"error": f"{type(reason).__name__}: {reason}"}
            continue
        try:
            state[endpoint] = {"status": response.status_code, "body": response.json()}
        except ValueError:
            state[endpoint] = {"status": response.status_code, "body": response.text[:500]}
    return state


def summarize(rows: list[dict]) -> dict:
    answered = [row for row in rows if row["status"] == 200]
    judged = [row for row in answered if row["expected_match"] is not None]
    providers: dict[str, int] = {}
    actions: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    for row in answered:
        providers[str(row["provider"])] = providers.get(str(row["provider"]), 0) + 1
        actions[str(row["action"])] = actions.get(str(row["action"]), 0) + 1
    for row in judged:
        bucket = by_category.setdefault(str(row["category"]), {"matched": 0, "total": 0})
        bucket["total"] += 1
        bucket["matched"] += int(bool(row["expected_match"]))
    latencies = sorted(row["elapsed_ms"] for row in answered if row["elapsed_ms"] is not None)
    return {
        "scenarios": len(rows),
        "answered": len(answered),
        "failed": len(rows) - len(answered),
        "judged": len(judged),
        "expected_action_matched": sum(int(bool(row["expected_match"])) for row in judged),
        "by_category": by_category,
        "providers": providers,
        "actions": actions,
        "median_elapsed_ms": latencies[len(latencies) // 2] if latencies else None,
        "max_elapsed_ms": latencies[-1] if latencies else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int)
    arguments = parser.parse_args()

    key = read_key()
    scenarios = load_scenarios(arguments.data)
    if arguments.limit:
        scenarios = scenarios[: arguments.limit]
    if not scenarios:
        raise SystemExit(f"no scenarios loaded from {arguments.data}")

    started_at = datetime.now(UTC)
    state = service_state(arguments.base_url, key, arguments.timeout)

    rows = []
    for position, scenario in enumerate(scenarios, start=1):
        row = ask(arguments.base_url, key, scenario, arguments.timeout)
        rows.append(row)
        mark = row["action"] or f"error({row['status']})"
        print(f"[{position}/{len(scenarios)}] {row['id']} {row['age_band']} -> {mark}")

    directory = arguments.output / started_at.strftime("%Y%m%dT%H%M%SZ")
    directory.mkdir(parents=True, exist_ok=True)
    responses = directory / "responses.jsonl"
    with responses.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "base_url": arguments.base_url,
        "route": "product api/app /chat, internal bearer authentication",
        "turn_scope": "single turn, no stored history, no previous_action",
        "data": {
            "path": str(arguments.data.relative_to(ROOT)),
            "sha256": digest(arguments.data),
            "scenarios": len(scenarios),
        },
        "git": git_state(),
        "service": state,
        "summary": summarize(rows),
    }
    (directory / "run.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    summary = manifest["summary"]
    print()
    print(f"answered {summary['answered']}/{summary['scenarios']}, failed {summary['failed']}")
    print(f"expected action matched {summary['expected_action_matched']}/{summary['judged']}")
    print(f"providers {summary['providers']}")
    print(f"written to {directory}")


if __name__ == "__main__":
    main()
