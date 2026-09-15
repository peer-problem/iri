import argparse
import json
import re
from pathlib import Path

import httpx

from app.settings import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["kanana", "gemma"])
    args = parser.parse_args()
    model_id = json.loads((ROOT / "configs/models.json").read_text())[args.profile]["model_id"]
    response = httpx.get(f"https://huggingface.co/api/models/{model_id}", timeout=20)
    response.raise_for_status()
    revision = response.json()["sha"]
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise SystemExit("Invalid revision returned by Hugging Face")
    Path("runs").mkdir(exist_ok=True)
    target = Path("runs") / f"{args.profile}-model.env"
    target.write_text(f"MODEL_PROFILE={args.profile}\nMODEL_REVISION={revision}\n")
    print(f"{model_id}: {revision}\nSaved to {target}. No model weights downloaded.")


if __name__ == "__main__":
    main()
