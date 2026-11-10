"""
app/services/auth_service.py — login με κλειδί πρόσβασης, όριο αποτυχιών, πρόσβαση ομάδας ελέγχου.

Όριο αποτυχιών: LOGIN_MAX_FAILURES ανά IP σε LOGIN_WINDOW_MINUTES (ΠΡΟΣΧΕΔΙΟ: 30 / 15 λεπτά). In-memory: ισχύει
ΜΟΝΟ με έναν worker (docker-compose.prod.yml: --workers 1). Η IP είναι η request.client.host. Το uvicorn την
παίρνει από το X-Forwarded-For μόνο για αιτήματα από το FORWARDED_ALLOW_IPS (ο Nginx), και ο Nginx αντικαθιστά
το header με το $remote_addr, οπότε ένας client δεν μπορεί να «αλλάξει» IP με ψεύτικο header.
Η IP δεν γράφεται ποτέ σε audit ή log (R2). Πολλά παιδιά πίσω από μία IP (ακαδημίες, σχολεία) μοιράζονται το όριο.

Ομάδα ελέγχου: σύμφωνα με το πρωτόκολλο δεν χρησιμοποιεί την εφαρμογή κατά τη μελέτη -> 403 μέχρι το
CONTROL_ACCESS_FROM (docs/backend_spec_v1.md, Τροποποίηση 6).
"""
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core import audit
from app.core.clock import local_today
from app.core.security import create_access_token, key_hmac, normalize_access_key
from app.db.models import Participant
from app.db.models.enums import Arm

MAX_TRACKED_IPS = 10_000   # όριο μνήμης του limiter


class LoginError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


INVALID = LoginError(401, "invalid_credentials")          # ίδιο για κάθε λόγο αποτυχίας
RATE_LIMITED = LoginError(429, "too_many_attempts")
NOT_YET_AVAILABLE = LoginError(403, "not_yet_available")


class LoginLimiter:
    def __init__(self, max_failures: int, window: timedelta):
        self.max_failures, self.window = max_failures, window
        self._failures: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, ip: str, now: datetime) -> deque:
        q = self._failures[ip]
        while q and now - q[0] >= self.window:
            q.popleft()
        return q

    def blocked(self, ip: str, now: datetime) -> bool:
        with self._lock:
            blocked = len(self._prune(ip, now)) >= self.max_failures
            if not self._failures[ip]:
                del self._failures[ip]
            return blocked

    def fail(self, ip: str, now: datetime) -> None:
        with self._lock:
            if len(self._failures) >= MAX_TRACKED_IPS:
                for old in [k for k, q in self._failures.items() if not q or now - q[-1] >= self.window]:
                    del self._failures[old]
            self._prune(ip, now).append(now)


def control_access_open(settings: Settings, now: datetime) -> bool:
    start = settings.CONTROL_ACCESS_FROM
    return start is not None and local_today(settings.tz, now) >= start


def may_use_app(participant: Participant, settings: Settings, now: datetime) -> bool:
    return participant.arm != Arm.CONTROL.value or control_access_open(settings, now)


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_in: int


def login(db: Session, settings: Settings, limiter: LoginLimiter, client_ip: str, raw_key: str,
          now: datetime) -> LoginResult:
    if limiter.blocked(client_ip, now):
        raise RATE_LIMITED       # χωρίς audit: θα επέτρεπε απεριόριστες εγγραφές· φαίνεται στο access log (429)

    key = normalize_access_key(raw_key)
    participant = None
    if key is not None:
        digest = key_hmac(key, settings.ACCESS_KEY_PEPPER.get_secret_value())
        participant = db.scalar(select(Participant).where(Participant.key_hmac == digest))

    if participant is None or not participant.active:
        limiter.fail(client_ip, now)
        reason = "bad_format" if key is None else ("unknown_key" if participant is None else "inactive")
        audit.record(db, "login_failed", participant.id if participant else None, reason=reason)
        db.commit()
        raise INVALID

    if not may_use_app(participant, settings, now):
        audit.record(db, "login_denied_control", participant.id)
        db.commit()
        raise NOT_YET_AVAILABLE

    token, expires_in = create_access_token(participant.id, participant.token_version,
                                            settings.JWT_SECRET.get_secret_value(),
                                            settings.ACCESS_TOKEN_TTL_MINUTES, now)
    audit.record(db, "login_succeeded", participant.id)
    db.commit()
    return LoginResult(token, expires_in)
