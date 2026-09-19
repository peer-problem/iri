"""Bounded, short-lived demo sessions. Never persist audio or conversation text."""

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

COOKIE = "iri_session"
TTL = 3600
SESSION_CREATE_WINDOW_SECONDS = 300
SESSION_CREATE_LIMIT = 30
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
        self.creations_by_ip: dict[str, deque] = {}
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
        self.creations_by_ip = {
            key: events
            for key, events in self.creations_by_ip.items()
            if events and events[-1] > now - SESSION_CREATE_WINDOW_SECONDS
        }
        self.calls_by_ip = {
            key: events
            for key, events in self.calls_by_ip.items()
            if events and events[-1] > now - CALL_WINDOW_SECONDS
        }

    def create(self, request: Request) -> tuple[Session, str]:
        """Create a bounded anonymous session on the first state-changing request."""
        now = time.time()
        ip = self.client_ip(request)
        self.creations_by_ip = {
            key: value
            for key, value in self.creations_by_ip.items()
            if value and value[-1] > now - SESSION_CREATE_WINDOW_SECONDS
        }
        if ip not in self.creations_by_ip and len(self.creations_by_ip) >= 2000:
            raise HTTPException(429, "Try again later")
        creations = self.creations_by_ip.setdefault(ip, deque())
        self.trim(creations, now - SESSION_CREATE_WINDOW_SECONDS)
        if len(creations) >= SESSION_CREATE_LIMIT:
            raise HTTPException(429, "Try again later", headers={"Retry-After": "300"})
        creations.append(now)
        self.items = {k: v for k, v in self.items.items() if v.expires > now}
        if len(self.items) >= 1000:
            raise HTTPException(429, "Demo is busy")
        token = secrets.token_urlsafe(32)
        session = Session(now + TTL)
        self.items[hashlib.sha256(token.encode()).hexdigest()] = session
        return session, token

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
