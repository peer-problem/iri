"""Independent in-Pod time limit using the preconfigured Pod-scoped runpodctl key."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--training-output", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--deadline", type=float)
    args = parser.parse_args()
    pod_id = os.environ.get("RUNPOD_POD_ID")
    cli = shutil.which("runpodctl")
    if not pod_id or not cli or not Path("/workspace").is_dir():
        parser.error("Run this inside a Runpod Pod with its preconfigured runpodctl")
    if not 1 <= args.minutes <= 60:
        parser.error("Runtime must be 1 to 60 minutes")
    if args.training_output and not args.training_output.resolve().is_relative_to(
        Path("/workspace")
    ):
        parser.error("Training output must be on persistent /workspace storage")
    path = Path("/workspace/pod-deadline.json")
    commands = [[cli, "pod", "stop", pod_id], [cli, "stop", "pod", pod_id]]
    if not args.worker:
        deadline = time.time() + args.minutes * 60
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--deadline",
            str(deadline),
        ]
        if args.training_output:
            command.extend(["--training-output", str(args.training_output.resolve())])
        # The account-wide API key is deliberately removed from the child's environment.
        environment = {k: v for k, v in os.environ.items() if k != "RUNPOD_API_KEY"}
        with Path("/workspace/pod-deadline.log").open("a") as log:
            child = subprocess.Popen(
                command,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        for _ in range(30):
            if path.exists():
                state = json.loads(path.read_text())
                if state.get("pid") == child.pid:
                    print(json.dumps(state))
                    return
            time.sleep(0.1)
        parser.error("Deadline worker startup not confirmed; stop Pod from local guard now")
    if args.deadline is None:
        parser.error("Worker requires deadline")
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps({"pid": os.getpid(), "pod_id": pod_id, "deadline": args.deadline})
    )
    temporary.replace(path)
    remaining = max(0, args.deadline - time.time())
    end = time.monotonic() + remaining
    while time.monotonic() < end:
        if args.training_output and end - time.monotonic() <= 300:
            args.training_output.mkdir(parents=True, exist_ok=True)
            (args.training_output / "STOP_REQUESTED").touch()
        time.sleep(min(5, max(0, end - time.monotonic())))
    os.sync()
    # Current and legacy CLI syntax. Retry if the control plane is temporarily unavailable.
    while True:
        for command in commands:
            try:
                subprocess.run(
                    command,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                pass
        time.sleep(5)


if __name__ == "__main__":
    main()
