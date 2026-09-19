"""Wire format for verified speech streamed from the API to browsers."""

import json
from typing import Any


def speech_event(name: str, payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n".encode()
