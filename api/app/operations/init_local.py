import os
import secrets

from app.settings import ENV_FILE


def main():
    target = ENV_FILE
    content = (
        f"SANDBOX_API_KEY={secrets.token_urlsafe(32)}\n"
        f"MODEL_API_KEY={secrets.token_urlsafe(32)}\n"
        "MODEL_BASE_URL=http://127.0.0.1:8002/v1\n"
        "MODEL_PROFILE=kanana\n"
        "MODEL_REVISION=\n"
        "HF_TOKEN=\n"
        "RUNPOD_API_KEY=\n"
        "OPENAI_API_KEY=\n"
    )
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit(".env already exists; preserved without changes") from None
    with os.fdopen(descriptor, "w") as file:
        file.write(content)
    print("Created private .env with separate API keys. No secrets printed.")


if __name__ == "__main__":
    main()
