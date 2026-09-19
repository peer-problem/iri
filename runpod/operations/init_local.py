import os
import secrets

from runpod.settings import ENV_FILE


def main():
    target = ENV_FILE
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    content = (
        f"SANDBOX_API_KEY={secrets.token_urlsafe(32)}\n"
        f"MODEL_API_KEY={secrets.token_urlsafe(32)}\n"
        "MODEL_BASE_URL=http://127.0.0.1:8002/v1\n"
        "MODEL_PROFILE=kanana\n"
        "MODEL_REVISION=\n"
        "ADAPTER_NAME=iri-kanana3b-v5-0ecacdb7d7f7\n"
        "ADAPTER_REVISION=0880ce0372cedf22aec91b190f8a7b9499ccc176\n"
        "ADAPTER_SHA256=0ecacdb7d7f743652a24ff7b7e7c59d0e2ae238e63476e64b2d6d95e8fbe2e02\n"
        "BEHAVIOR_PROFILE=kanana_v5\n"
        "HF_TOKEN=\n"
        "RUNPOD_API_KEY=\n"
        "OPENAI_API_KEY=\n"
    )
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit(".keys/.env already exists; preserved without changes") from None
    with os.fdopen(descriptor, "w") as file:
        file.write(content)
    print("Created private .keys/.env with separate API keys. No secrets printed.")


if __name__ == "__main__":
    main()
