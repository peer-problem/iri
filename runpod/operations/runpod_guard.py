"""Local Runpod stop watchdog. Never creates, starts, deletes or funds resources."""

import argparse
import json
import os
import re
import subprocess
import sys
import time

import httpx
from dotenv import dotenv_values

from runpod.settings import ENV_FILE, REPO_ROOT

API = "https://rest.runpod.io/v1"
STATE_DIR = REPO_ROOT / ".logs/runpod/watchdog"
POD_NAME = "kids-sandbox-baseline"
KNOWN_PODS = {
    "agp8j1pz448x2k": "iri-phase2-evaluation-20260917",
    "alj5yk19zuhnvp": "iri-phase3-codex-quality-20260918",
    "hclryy4t144uwg": "iri-kanana-v2-final-20260919",
    "srmzsnz2ukpjee": "iri-kanana-v2-eval-20260919",
    "5h41hdsnogjaib": "iri-kanana-v2-eval2-20260919",
    "egw5ndth2lsus8": POD_NAME,
    "9l7neo7d5wu3ec": "iri-phase3-v3-preferred-20260917",
    "ttb34ziuu2ovrd": "iri-v10-full-new-20260917-01",
    "ihxof0nqownkzw": "iri-phase3-quality-20260917",
    "apu0j7ndp42wqd": "iri-phase2-training-v2",
}


def write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(path)


def request(client, method, suffix):
    try:
        response = client.request(method, API + suffix)
    except httpx.HTTPError:
        raise RuntimeError("Runpod connection failed") from None
    if not response.is_success:
        raise RuntimeError(f"Runpod returned HTTP {response.status_code}")
    return response


def owned_pod(client, pod_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", pod_id):
        raise ValueError("Invalid Pod ID")
    pod = request(client, "GET", f"/pods/{pod_id}").json()
    expected_name = KNOWN_PODS.get(pod_id) or os.environ.get(
        "IRI_RUNPOD_EXPECTED_POD_NAME", POD_NAME
    )
    if pod.get("id") != pod_id or pod.get("name") != expected_name:
        raise ValueError("Pod identity does not match this project; no action taken")
    return pod


def stop(client, pod_id):
    pod = owned_pod(client, pod_id)
    if pod.get("desiredStatus") == "EXITED":
        return True
    request(client, "POST", f"/pods/{pod_id}/stop")
    # A successful POST alone is not reported as a confirmed stop.
    return owned_pod(client, pod_id).get("desiredStatus") == "EXITED"


def stop_reason(state, now, heartbeat):
    if now >= state["deadline"]:
        return "runtime_limit"
    if heartbeat is None or now - heartbeat >= 180:
        return "activity_lease_expired"
    return None


def watch(client, state_path):
    state = json.loads(state_path.read_text())
    heartbeat = state_path.with_suffix(".heartbeat")
    state.update(watchdog_pid=os.getpid(), watchdog_started_at=time.time())
    write_state(state_path, state)
    while True:
        now = time.time()
        reason = stop_reason(state, now, heartbeat.stat().st_mtime if heartbeat.exists() else None)
        try:
            pod = owned_pod(client, state["pod_id"])
            if pod.get("desiredStatus") == "EXITED":
                state.update(status="api_reports_exited", stopped_at=now)
                write_state(state_path, state)
                return
            if pod.get("lastStartedAt") != state["last_started_at"]:
                raise ValueError("Pod was restarted outside this watchdog session")
            if reason:
                state.update(stop_reason=reason, stop_requested_at=now)
                if stop(client, state["pod_id"]):
                    state.update(status="api_reports_exited", stopped_at=time.time())
                    write_state(state_path, state)
                    return
        except RuntimeError as error:
            # Keep retrying after transient failures, including an expired activity lease.
            state.update(
                status="stop_unconfirmed" if reason else "api_unreachable", error=str(error)
            )
        except ValueError as error:
            state.update(status="identity_changed_manual_check_required", error=str(error))
            write_state(state_path, state)
            raise
        state["last_poll_at"] = now
        write_state(state_path, state)
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "arm", "heartbeat", "stop", "watch"))
    parser.add_argument("--pod-id")
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.minutes <= 60:
        parser.error("Runtime must be 1 to 60 minutes")
    if args.action != "status" and not args.pod_id:
        parser.error("An explicit project Pod ID is required")
    if args.pod_id and not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", args.pod_id):
        parser.error("Invalid Pod ID")
    state_path = STATE_DIR / f"{args.pod_id}.json"
    if args.action == "heartbeat":
        state = json.loads(state_path.read_text())
        if state.get("status") == "api_reports_exited" or time.time() >= state["deadline"]:
            parser.error("This session ended; a heartbeat cannot extend the deadline")
        state_path.with_suffix(".heartbeat").touch()
        print("Activity lease renewed for at most 180 seconds; deadline unchanged")
        return
    key = os.environ.get("RUNPOD_API_KEY") or dotenv_values(ENV_FILE).get("RUNPOD_API_KEY")
    if not key:
        parser.error("Set RUNPOD_API_KEY locally in .keys/.env")
    with httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=15) as client:
        if args.action == "status":
            pods = request(client, "GET", "/pods").json()
            print(
                json.dumps(
                    [
                        {
                            k: pod.get(k)
                            for k in ("id", "name", "desiredStatus", "costPerHr", "volumeInGb")
                        }
                        for pod in pods
                    ],
                    indent=2,
                )
            )
        elif args.action == "stop":
            for _ in range(12):
                if stop(client, args.pod_id):
                    print("Runpod API reports EXITED; persistent storage can still be billed")
                    return
                time.sleep(5)
            raise RuntimeError("Stop was requested but EXITED was not confirmed; check console now")
        elif args.action == "watch":
            watch(client, state_path)
        else:
            pod = owned_pod(client, args.pod_id)
            if pod.get("desiredStatus") != "RUNNING":
                parser.error("Only arm immediately after starting this project's Pod")
            if state_path.exists():
                previous = json.loads(state_path.read_text())
                if (
                    previous.get("status") != "api_reports_exited"
                    or not pod.get("lastStartedAt")
                    or previous.get("last_started_at") == pod["lastStartedAt"]
                ):
                    parser.error(
                        "Previous session must be confirmed stopped before arming a restart"
                    )
                archive = STATE_DIR / "history" / f"{args.pod_id}-{time.time_ns()}.json"
                archive.parent.mkdir(parents=True, exist_ok=True)
                state_path.replace(archive)
            now = time.time()
            write_state(
                state_path,
                {
                    "pod_id": args.pod_id,
                    "last_started_at": pod.get("lastStartedAt"),
                    "armed_at": now,
                    "deadline": now + args.minutes * 60,
                    "cost_per_hr": pod.get("costPerHr"),
                    "volume_gb": pod.get("volumeInGb"),
                    "status": "arming",
                },
            )
            state_path.with_suffix(".heartbeat").touch()
            with state_path.with_suffix(".log").open("a") as log:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "runpod.operations.runpod_guard",
                        "watch",
                        "--pod-id",
                        args.pod_id,
                    ],
                    cwd=REPO_ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            for _ in range(30):
                if json.loads(state_path.read_text()).get("watchdog_started_at"):
                    print(
                        "Local watchdog armed. Renew activity during work; Pod-side deadline still required."
                    )
                    return
                time.sleep(0.1)
            stop(client, args.pod_id)
            raise RuntimeError("Watchdog startup unconfirmed; stop requested, verify status now")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
