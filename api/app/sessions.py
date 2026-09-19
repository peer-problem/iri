"""Bounded, short-lived demo sessions. Never persist audio or conversation text."""

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

COOKIE = "iri_session"
TTL = 3600
DEV_ACCESS_CODE = "dev"
LOGIN_WINDOW_SECONDS = 300
LOGIN_LIMIT = 10
CALL_WINDOW_SECONDS = 600
SESSION_CALL_LIMIT = 90
IP_CALL_LIMIT = 120


@dataclass
class Session:
    expires: float
    age: str = ""
    history: list = field(default_factory=list)
    calls: deque = field(default_factory=deque)


class Sessions:
    def __init__(self, settings):
        self.settings = settings
        self.items: dict[str, Session] = {}
        self.attempts: dict[str, deque] = {}
        self.calls_by_ip: dict[str, deque] = {}

    @staticmethod
    def client_ip(request: Request) -> str:
        # Uvicorn trusts only the configured immediate proxy, so request.client is canonical.
        return request.client.host if request.client else "unknown"

    @staticmethod
    def trim(events: deque, cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    def origin(self, request: Request):
        origin = request.headers.get("origin")
        allowed = self.settings.allowed_origins.split(",")
        if origin and origin not in allowed:
            raise HTTPException(403, "Origin not allowed")
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Cross-site request not allowed")

    def lookup(self, request: Request):
        key = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
        session = self.items.get(key)
        if session and session.expires > time.time():
            return session
        self.items.pop(key, None)
        return None

    def prune(self):
        now = time.time()
        self.items = {key: session for key, session in self.items.items() if session.expires > now}
        self.attempts = {
            key: events
            for key, events in self.attempts.items()
            if events and events[-1] > now - LOGIN_WINDOW_SECONDS
        }
        self.calls_by_ip = {
            key: events
            for key, events in self.calls_by_ip.items()
            if events and events[-1] > now - CALL_WINDOW_SECONDS
        }

    def login(self, request: Request, code: str):
        self.origin(request)
        now = time.time()
        is_dev_code = self.settings.allow_dev_access_code and secrets.compare_digest(
            code.encode(), DEV_ACCESS_CODE.encode()
        )
        ip = self.client_ip(request)
        self.attempts = {
            key: value
            for key, value in self.attempts.items()
            if value and value[-1] > now - LOGIN_WINDOW_SECONDS
        }
        if ip not in self.attempts and len(self.attempts) >= 2000:
            raise HTTPException(429, "Try again later")
        attempts = self.attempts.setdefault(ip, deque())
        self.trim(attempts, now - LOGIN_WINDOW_SECONDS)
        if len(attempts) >= LOGIN_LIMIT:
            raise HTTPException(429, "Try again later", headers={"Retry-After": "300"})
        attempts.append(now)
        expected = self.settings.demo_access_code.get_secret_value()
        if not is_dev_code and (
            not expected or not secrets.compare_digest(code.encode(), expected.encode())
        ):
            raise HTTPException(401, "Invalid access code")
        self.items = {k: v for k, v in self.items.items() if v.expires > now}
        if len(self.items) >= 1000:
            raise HTTPException(429, "Demo is busy")
        token = secrets.token_urlsafe(32)
        self.items[hashlib.sha256(token.encode()).hexdigest()] = Session(now + TTL)
        return token

    def limit(self, session: Session, request: Request):
        now = time.time()
        self.trim(session.calls, now - CALL_WINDOW_SECONDS)
        if len(session.calls) >= SESSION_CALL_LIMIT:
            raise HTTPException(429, "Try again later", headers={"Retry-After": "60"})
        ip = self.client_ip(request)
        if ip not in self.calls_by_ip and len(self.calls_by_ip) >= 2000:
            raise HTTPException(429, "Try again later")
        calls = self.calls_by_ip.setdefault(ip, deque())
        self.trim(calls, now - CALL_WINDOW_SECONDS)
        if len(calls) >= IP_CALL_LIMIT:
            raise HTTPException(429, "Try again later", headers={"Retry-After": "60"})
        session.calls.append(now)
        calls.append(now)

    def logout(self, request):
        key = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
        self.items.pop(key, None)
