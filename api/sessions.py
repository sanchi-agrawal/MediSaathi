"""Bounded single-process demo sessions; no authentication or persistence."""
from dataclasses import dataclass, field
from threading import RLock
import secrets
import time

from .dependencies import AIIntegration

TTL_SECONDS = 1800
COOKIE = "medisaathi_demo"


@dataclass
class DemoSession:
    ai: AIIntegration
    created: float = field(default_factory=time.monotonic)
    lock: RLock = field(default_factory=RLock)
    revision: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    reviewed: bool = False
    confirmed_revision: str | None = None
    explanation: dict | None = None
    performance: dict = field(default_factory=dict)
    section_states: dict = field(default_factory=dict)
    prescription_active: bool = False
    strip_active: bool = False
    strip_state: dict = field(default_factory=dict)
    scheduling_revision: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    scheduling_state: dict = field(default_factory=dict)
    prescription_image: bytes | None = None
    prescription_mime: str | None = None

    def invalidate_scheduling(self):
        self.ai.clear_associations()
        self.scheduling_revision = secrets.token_urlsafe(24)
        self.scheduling_state = {}

    def invalidate(self):
        self.invalidate_scheduling()
        self.revision = secrets.token_urlsafe(24)
        self.reviewed = False
        self.confirmed_revision = None
        self.explanation = None


class SessionStore:
    def __init__(self, factory=AIIntegration, *, limit=64):
        self.factory = factory
        self.limit = limit
        self.sessions = {}
        self.lock = RLock()

    def prune(self):
        now = time.monotonic()
        for token, session in list(self.sessions.items()):
            if now - session.created >= TTL_SECONDS:
                del self.sessions[token]

    def get(self, token):
        with self.lock:
            self.prune()
            return self.sessions.get(token)

    def create(self):
        with self.lock:
            self.prune()
            if len(self.sessions) >= self.limit:
                return None
            token = secrets.token_urlsafe(32)
            session = DemoSession(self.factory())
            self.sessions[token] = session
            return token, session
