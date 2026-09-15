import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from runpod.settings import ENV_FILE, ROOT, Settings


def build_command(settings: Settings, executable: str) -> list[str]:
    command = [
        executable,
        "serve",
        settings.profile["model_id"],
        "--revision",
        settings.model_revision,
        "--tokenizer-revision",
        settings.model_revision,
        "--served-model-name",
        settings.served_model,
        "--host",
        "127.0.0.1",
        "--port",
        str(settings.model_serve_port),
        "--max-model-len",
        "4096",
        "--max-num-seqs",
        "1",
        "--gpu-memory-utilization",
        "0.80",
        "--dtype",
        "bfloat16",
        "--generation-config",
        "vllm",
        "--enforce-eager",
        "--no-enable-log-requests",
    ]
    return command


def main():
    load_dotenv(ENV_FILE)
    settings = Settings()
    if not settings.configured:
        raise SystemExit("Set .keys/.env keys and the model revision first. See README.md")
    if sys.platform != "linux" or not shutil.which("nvidia-smi"):
        raise SystemExit("Run this launcher inside the Linux NVIDIA GPU Pod")
    executable = shutil.which("vllm") or str(Path(sys.executable).parent / "vllm")
    if not Path(executable).exists():
        raise SystemExit("Install runpod/requirements-gpu.txt in the GPU environment first")
    version = importlib.metadata.version("vllm")
    if version != "0.29.0":
        raise SystemExit("This launcher targets vLLM 0.29.0; use runpod/requirements-gpu.txt")
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    )
    run_dir = (ROOT / "runs") / f"gpu-{settings.model_profile}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    run_dir.mkdir(parents=True, exist_ok=False)
    command = build_command(settings, executable)
    (run_dir / "gpu-environment.json").write_text(
        json.dumps(
            {
                "gpu": gpu.stdout.strip(),
                "vllm": version,
                "model_id": settings.profile["model_id"],
                "revision": settings.model_revision,
                "command": command,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    packages = sorted(
        f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()
    )
    (run_dir / "gpu-packages.txt").write_text("\n".join(packages) + "\n")
    os.environ["VLLM_API_KEY"] = settings.model_api_key.get_secret_value()
    # Absolute Python invocation does not activate its virtual environment.
    # vLLM's JIT build subprocesses still need that environment's ninja binary.
    os.environ["PATH"] = str(Path(executable).parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("HF_HOME", "/workspace/hf-cache")
    os.environ.setdefault("VLLM_LOGGING_LEVEL", "WARNING")
    print(f"Starting {settings.served_model}. Environment record: {run_dir}", flush=True)
    os.execv(executable, command)


if __name__ == "__main__":
    main()
