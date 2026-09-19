import asyncio
import logging
import secrets
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import ClientDisconnect

from api.app.provider import ModelProvider, ModelUnavailable
from api.app.routing import RoutedChatService
from api.app.schemas import ChatRequest, ChatResponse, SpeechRequest
from api.app.service import FALLBACKS, QueueFull, RequestGate
from api.app.sessions import COOKIE, TTL, Sessions
from api.app.settings import Settings
from api.app.speech import SpeechUnavailable, Synthesizer
from api.app.transcription import (
    FORMATS,
    NoSpeechDetected,
    Transcriber,
    TranscriptionUnavailable,
)

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, transport=None) -> FastAPI:
    settings = settings or Settings()
    gate = RequestGate(settings.max_waiting)
    audio_gate = RequestGate(0)
    speech_gate = RequestGate(0)
    sessions = Sessions(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def prune_sessions():
            while True:
                sessions.prune()
                await asyncio.sleep(30)

        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            app.state.provider = ModelProvider(settings, client)
            app.state.service = RoutedChatService(app.state.provider)
            app.state.transcriber = Transcriber(settings, client)
            app.state.synthesizer = Synthesizer(settings, client)
            cleanup = asyncio.create_task(prune_sessions())
            try:
                yield
            finally:
                cleanup.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup
                sessions.items.clear()

    app = FastAPI(title="Kids Sandbox: internal Phase 1 API", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    async def access(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        expected = settings.sandbox_api_key.get_secret_value()
        request.state.demo_session = None
        request.state.session_token = None
        if credentials:
            if expected and secrets.compare_digest(
                credentials.credentials.encode(), expected.encode()
            ):
                return
            raise HTTPException(
                401,
                "Invalid API credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        session = sessions.lookup(request)
        if request.method in {"GET", "HEAD"}:
            request.state.demo_session = session
            return
        sessions.origin(request)
        if session is None:
            session, token = sessions.create(request)
            request.state.session_token = token
        sessions.limit(session, request)
        request.state.demo_session = session

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        token = getattr(request.state, "session_token", None)
        if token:
            response.set_cookie(
                COOKIE,
                token,
                max_age=TTL,
                httponly=True,
                secure=settings.secure_cookies,
                samesite="lax",
                path="/",
            )
        return response

    @app.delete("/conversation", dependencies=[Depends(access)])
    async def clear_conversation(request: Request):
        if request.state.demo_session:
            request.state.demo_session.history.clear()
        return {"cleared": True}

    @app.get("/conversation", dependencies=[Depends(access)])
    async def conversation(request: Request):
        session = request.state.demo_session
        return {
            "age_band": (session.age or "4-6") if session else "4-6",
            "messages": [
                {"id": str(uuid4()), **item} for item in (session.history if session else [])
            ],
        }

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _exc):
        # FastAPI's default validation error echoes the invalid input.
        return JSONResponse(status_code=422, content={"detail": "Invalid request"})

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "model_status": "configured" if settings.configured else "unconfigured",
            "generation_model": settings.generation_model if settings.configured else None,
            "adapter_sha256": settings.adapter_sha256 or None,
            "fallback_status": (
                "configured"
                if settings.openai_api_key.get_secret_value()
                else "unconfigured"
            ),
        }

    @app.get("/ready", dependencies=[Depends(access)])
    async def ready():
        if not await app.state.provider.ready():
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {
            "status": "ready",
            "guard_model": settings.served_model,
            "generation_model": settings.generation_model,
            "adapter_sha256": settings.adapter_sha256 or None,
        }

    @app.post("/transcribe", dependencies=[Depends(access)])
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
        except NoSpeechDetected:
            raise HTTPException(422, "No speech detected") from None
        except (ValueError, ClientDisconnect):
            raise HTTPException(400, "Invalid audio") from None

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(access)])
    async def chat(body: ChatRequest, request: Request):
        request_id = uuid4()
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                async with gate.enter():
                    session = request.state.demo_session
                    if session and session.age != body.age_band:
                        session.history.clear()
                        session.age = body.age_band
                    stored_history = list(session.history) if session else []
                    history = (
                        [
                            {"role": item["role"], "content": item["content"]}
                            for item in stored_history
                        ]
                        if session
                        else []
                    )
                    history.append({"role": "user", "content": body.message})
                    answer, action, provider = await app.state.service.respond(body.age_band, history)
                    if session:
                        session.history = [
                            *stored_history,
                            {"role": "user", "content": body.message},
                            {
                                "role": "assistant",
                                "content": answer,
                                "provider": provider,
                            },
                        ][-12:]
            return ChatResponse(answer=answer, action=action, request_id=request_id, provider=provider)
        except QueueFull as exc:
            status, headers = 429, {"Retry-After": "3"}
            failure = exc
        except TimeoutError as exc:
            status, headers = 504, {}
            failure = exc
        except ModelUnavailable as exc:
            status, headers = 503, {}
            failure = exc
        logger.warning(
            "chat_request_failed request_id=%s status=%s code=%s stage=%s",
            request_id,
            status,
            getattr(failure, "code", "queue_full" if status == 429 else "timeout"),
            getattr(failure, "stage", None),
        )
        return JSONResponse(
            status_code=status,
            headers=headers,
            content=ChatResponse(
                answer=FALLBACKS["unavailable"], action="unavailable", request_id=request_id,
                provider="unavailable",
            ).model_dump(mode="json"),
        )

    @app.post("/speech", dependencies=[Depends(access)])
    async def speech(body: SpeechRequest, request: Request):
        """Read an answer from POST /chat aloud. Returns MP3 bytes."""
        session = request.state.demo_session
        if session and not any(
            item["role"] == "assistant" and item["content"] == body.text for item in session.history
        ):
            raise HTTPException(403, "Only a checked conversation answer can be read aloud")
        if not settings.openai_api_key.get_secret_value():
            raise HTTPException(503, "Speech is not configured")
        if len(body.text) > settings.tts_max_chars:
            raise HTTPException(413, "Text is too long")
        try:
            async with asyncio.timeout(settings.tts_timeout_seconds):
                async with speech_gate.enter():
                    audio = await app.state.synthesizer.synthesize(body.text)
            return Response(
                content=audio,
                media_type="audio/mpeg",
                headers={"Cache-Control": "no-store", "X-Request-Id": str(uuid4())},
            )
        except QueueFull:
            raise HTTPException(429, "Speech is busy", headers={"Retry-After": "3"}) from None
        except TimeoutError:
            raise HTTPException(504, "Speech timed out") from None
        except SpeechUnavailable:
            raise HTTPException(503, "Speech is unavailable") from None
        except ValueError:
            raise HTTPException(413, "Text is too long") from None

    @app.post("/speech-stream", dependencies=[Depends(access)])
    async def speech_stream(body: SpeechRequest, request: Request):
        """Stream 24 kHz, mono, signed 16-bit little-endian PCM speech."""
        session = request.state.demo_session
        if session and not any(
            item["role"] == "assistant" and item["content"] == body.text for item in session.history
        ):
            raise HTTPException(403, "Only a checked conversation answer can be read aloud")
        if not settings.openai_api_key.get_secret_value():
            raise HTTPException(503, "Speech is not configured")
        if len(body.text) > settings.tts_max_chars:
            raise HTTPException(413, "Text is too long")

        stream = app.state.synthesizer.stream_pcm(body.text).__aiter__()
        gate_context = speech_gate.enter()
        entered = False
        deadline = asyncio.get_running_loop().time() + settings.tts_timeout_seconds
        try:
            await gate_context.__aenter__()
            entered = True
            first = await asyncio.wait_for(
                anext(stream), timeout=settings.tts_timeout_seconds
            )
        except QueueFull:
            raise HTTPException(
                429, "Speech is busy", headers={"Retry-After": "3"}
            ) from None
        except (TimeoutError, asyncio.TimeoutError):
            if entered:
                await gate_context.__aexit__(None, None, None)
            with suppress(Exception):
                await stream.aclose()
            raise HTTPException(504, "Speech timed out") from None
        except (SpeechUnavailable, StopAsyncIteration):
            if entered:
                await gate_context.__aexit__(None, None, None)
            with suppress(Exception):
                await stream.aclose()
            raise HTTPException(503, "Speech is unavailable") from None
        except ValueError:
            if entered:
                await gate_context.__aexit__(None, None, None)
            with suppress(Exception):
                await stream.aclose()
            raise HTTPException(413, "Text is too long") from None
        except BaseException:
            if entered:
                await gate_context.__aexit__(None, None, None)
            with suppress(Exception):
                await stream.aclose()
            raise

        async def chunks():
            try:
                yield first
                async with asyncio.timeout_at(deadline):
                    async for chunk in stream:
                        yield chunk
            finally:
                with suppress(Exception):
                    await stream.aclose()
                await gate_context.__aexit__(None, None, None)

        return StreamingResponse(
            chunks(),
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Request-Id": str(uuid4()),
                "X-Audio-Format": "pcm_s16le;rate=24000;channels=1",
            },
        )

    return app


app = create_app()
