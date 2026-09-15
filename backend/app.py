import asyncio
import secrets
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import ClientDisconnect

from backend.provider import ModelProvider, ModelUnavailable
from backend.schemas import ChatRequest, ChatResponse
from backend.service import FALLBACKS, ChatService, QueueFull, RequestGate
from backend.settings import Settings
from backend.transcription import FORMATS, Transcriber, TranscriptionUnavailable


def create_app(settings: Settings | None = None, transport=None) -> FastAPI:
    settings = settings or Settings()
    gate = RequestGate(settings.max_waiting)
    audio_gate = RequestGate(0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            app.state.provider = ModelProvider(settings, client)
            app.state.service = ChatService(app.state.provider)
            app.state.transcriber = Transcriber(settings, client)
            yield

    app = FastAPI(title="Kids Sandbox: internal Phase 1 API", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    async def authenticate(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        expected = settings.sandbox_api_key.get_secret_value()
        if (
            not expected
            or credentials is None
            or not secrets.compare_digest(credentials.credentials.encode(), expected.encode())
        ):
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _exc):
        # FastAPI's default validation error echoes the invalid input.
        return JSONResponse(status_code=422, content={"detail": "Invalid request"})

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "model_status": "configured" if settings.configured else "unconfigured",
        }

    @app.get("/ready", dependencies=[Depends(authenticate)])
    async def ready():
        if not await app.state.provider.ready():
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready", "model": settings.served_model}

    @app.post("/transcribe", dependencies=[Depends(authenticate)])
    async def transcribe(request: Request):
        """Upload raw audio bytes; explicitly confirm the transcript before POST /chat."""
        if request.headers.get("x-audio-consent") != "true":
            raise HTTPException(400, "Confirm external audio processing before upload")
        mime = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if mime not in FORMATS:
            raise HTTPException(415, "Unsupported audio type")
        if not settings.openai_api_key.get_secret_value():
            raise HTTPException(503, "Transcription is not configured")
        try:
            async with asyncio.timeout(settings.stt_timeout_seconds):
                async with audio_gate.enter():
                    audio = bytearray()
                    async for chunk in request.stream():
                        if len(audio) + len(chunk) > settings.stt_max_bytes:
                            raise HTTPException(413, "Audio is too large")
                        audio.extend(chunk)
                    if not audio:
                        raise HTTPException(400, "Audio is empty")
                    text = await app.state.transcriber.transcribe(bytes(audio), mime)
            return {"text": text, "requires_confirmation": True, "request_id": str(uuid4())}
        except QueueFull:
            raise HTTPException(
                429, "Transcription is busy", headers={"Retry-After": "3"}
            ) from None
        except TimeoutError:
            raise HTTPException(504, "Transcription timed out") from None
        except TranscriptionUnavailable:
            raise HTTPException(503, "Transcription is unavailable") from None
        except (ValueError, ClientDisconnect):
            raise HTTPException(400, "Invalid audio") from None

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(authenticate)])
    async def chat(body: ChatRequest):
        request_id = uuid4()
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                async with gate.enter():
                    answer, action = await app.state.service.respond(
                        body.age_band, [{"role": "user", "content": body.message}]
                    )
            return ChatResponse(answer=answer, action=action, request_id=request_id)
        except QueueFull:
            status, headers = 429, {"Retry-After": "3"}
        except TimeoutError:
            status, headers = 504, {}
        except ModelUnavailable:
            status, headers = 503, {}
        return JSONResponse(
            status_code=status,
            headers=headers,
            content=ChatResponse(
                answer=FALLBACKS["unavailable"], action="unavailable", request_id=request_id
            ).model_dump(mode="json"),
        )

    return app


app = create_app()
