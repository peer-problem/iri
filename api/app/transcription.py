import httpx

from api.app.settings import Settings

FORMATS = {
    "audio/wav": ("wav", lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE"),
    "audio/x-wav": ("wav", lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE"),
    "audio/webm": ("webm", lambda b: b.startswith(b"\x1a\x45\xdf\xa3")),
    "audio/mpeg": (
        "mp3",
        lambda b: b.startswith(b"ID3") or (len(b) > 1 and b[0] == 255 and b[1] & 224 == 224),
    ),
    "audio/mp4": ("m4a", lambda b: b[4:8] == b"ftyp"),
}


class TranscriptionUnavailable(Exception):
    pass


class Transcriber:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    async def transcribe(self, audio: bytes, mime: str) -> str:
        if not self.settings.openai_api_key.get_secret_value():
            raise TranscriptionUnavailable
        extension, valid_header = FORMATS[mime]
        if not valid_header(audio):
            raise ValueError("Invalid audio container")
        # Container signatures are a quick rejection check. OpenAI decodes the audio.
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key.get_secret_value()}"
                },
                data={"model": self.settings.stt_model, "languages[]": "ko"},
                files={"file": (f"recording.{extension}", audio, mime)},
                timeout=self.settings.stt_timeout_seconds,
            )
            response.raise_for_status()
            text = response.json()["text"]
            if not isinstance(text, str) or not text.strip() or len(text.strip()) > 1000:
                raise TranscriptionUnavailable
            return text.strip()
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise TranscriptionUnavailable from exc
