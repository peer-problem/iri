"""Bounded, short-lived demo sessions. Never persist audio or conversation text."""

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

COOKIE = "iri_session"
TTL = 3600


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

    def login(self, request: Request, code: str):
        self.origin(request)
        now = time.time()
        # Trust only the immediate reverse proxy's real client address as configured in Uvicorn.
        ip = request.client.host if request.client else "unknown"
        self.attempts = {k: v for k, v in self.attempts.items() if v and v[-1] > now - 300}
        if ip not in self.attempts and len(self.attempts) >= 2000:
            raise HTTPException(429, "Try again later")
        attempts = self.attempts.setdefault(ip, deque())
        while attempts and attempts[0] <= now - 300:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Try again later", headers={"Retry-After": "300"})
        attempts.append(now)
        expected = self.settings.demo_access_code.get_secret_value()
        if not expected or not secrets.compare_digest(code.encode(), expected.encode()):
            raise HTTPException(401, "Invalid access code")
        self.items = {k: v for k, v in self.items.items() if v.expires > now}
        if len(self.items) >= 1000:
            raise HTTPException(429, "Demo is busy")
        token = secrets.token_urlsafe(32)
        self.items[hashlib.sha256(token.encode()).hexdigest()] = Session(now + TTL)
        return token

    def limit(self, session):
        now = time.time()
        while session.calls and session.calls[0] < now - 600:
            session.calls.popleft()
        if len(session.calls) >= 90:
            raise HTTPException(429, "Try again later", headers={"Retry-After": "60"})
        session.calls.append(now)

    def logout(self, request):
        key = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
        self.items.pop(key, None)
