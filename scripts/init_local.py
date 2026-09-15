import os
import secrets
from pathlib import Path


def main():
    target = Path(".env")
    content = Path(".env.example").read_text()
    content = content.replace(
        "SANDBOX_API_KEY=\n", f"SANDBOX_API_KEY={secrets.token_urlsafe(32)}\n"
    )
    content = content.replace("MODEL_API_KEY=\n", f"MODEL_API_KEY={secrets.token_urlsafe(32)}\n")
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit(".env already exists; preserved without changes") from None
    with os.fdopen(descriptor, "w") as file:
        file.write(content)
    print("Created private .env with separate API keys. No secrets printed.")


if __name__ == "__main__":
    main()
