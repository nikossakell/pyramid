"""
app/services/auth_service.py — login με κλειδί πρόσβασης, όριο αποτυχιών, πρόσβαση ομάδας ελέγχου.

Όριο αποτυχιών: LOGIN_MAX_FAILURES ανά IP σε LOGIN_WINDOW_MINUTES (ΠΡΟΣΧΕΔΙΟ: 30 / 15 λεπτά). In-memory: ισχύει
ΜΟΝΟ με έναν worker (docker-compose.prod.yml: --workers 1). Η IP είναι η request.client.host. Το uvicorn την
παίρνει από το X-Forwarded-For μόνο για αιτήματα από το FORWARDED_ALLOW_IPS (ο Nginx), και ο Nginx αντικαθιστά
το header με το $remote_addr, οπότε ένας client δεν μπορεί να «αλλάξει» IP με ψεύτικο header.
Η IP δεν γράφεται ποτέ σε audit ή log (R2). Πολλά παιδιά πίσω από μία IP (ακαδημίες, σχολεία) μοιράζονται το όριο.

Το 429 λέει στον client πότε να ξαναδοκιμάσει (Retry-After, δευτερόλεπτα): πότε λήγει η παλαιότερη αποτυχία που
κρατά το παράθυρο γεμάτο.

Ομάδα ελέγχου: σύμφωνα με το πρωτόκολλο δεν χρησιμοποιεί την εφαρμογή κατά τη μελέτη -> 403 μέχρι το
CONTROL_ACCESS_FROM (docs/backend_spec_v1.md, Τροποποίηση 6).

Τέλος μελέτης (S19): ημέρες μελέτης ενός συμμετέχοντα = enrollment_date .. enrollment_date + STUDY_DURATION_DAYS - 1
(στη ζώνη APP_TIMEZONE). Ομάδα παρέμβασης μετά την τελευταία ημέρα: StudyEnded -> 403 {"study_ended": true} στο login
και σε κάθε αίτημα με token, εκτός αν POST_STUDY_ACCESS=true. Η ομάδα ελέγχου μένει μόνο με τον κανόνα
CONTROL_ACCESS_FROM. Η νυχτερινή εργασία κοιτά την ΗΜΕΡΑ-ΣΤΟΧΟ (in_study_on), ώστε να γράφονται και οι κάρτες της
τελευταίας ημέρας, αν και τρέχει την επομένη.
"""
import math
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core import audit
from app.core.clock import local_today
from app.core.exceptions import StudyEnded
from app.core.security import create_access_token, key_hmac, normalize_access_key
from app.db.models import Participant
from app.db.models.enums import Arm

MAX_TRACKED_IPS = 10_000   # όριο μνήμης του limiter


class LoginError(Exception):
    def __init__(self, status_code: int, detail: str, retry_after: Optional[int] = None):
        super().__init__(detail)
        self.status_code, self.detail, self.retry_after = status_code, detail, retry_after

    @property
    def headers(self) -> Optional[dict[str, str]]:
        return {"Retry-After": str(self.retry_after)} if self.retry_after is not None else None


INVALID = LoginError(401, "invalid_credentials")          # ίδιο για κάθε λόγο αποτυχίας
NOT_YET_AVAILABLE = LoginError(403, "not_yet_available")


def rate_limited(retry_after: int) -> LoginError:
    return LoginError(429, "too_many_attempts", retry_after=retry_after)


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

    def retry_after(self, ip: str, now: datetime) -> Optional[int]:
        """None αν η IP δεν είναι κλειδωμένη· αλλιώς ολόκληρα δευτερόλεπτα (≥ 1) μέχρι να ελευθερωθεί μία θέση στο
        παράθυρο, δηλαδή μέχρι να λήξει η παλαιότερη από τις τελευταίες max_failures αποτυχίες."""
        with self._lock:
            q = self._prune(ip, now)
            if not q:
                del self._failures[ip]
                return None
            if len(q) < self.max_failures:
                return None
            frees_at = q[len(q) - self.max_failures] + self.window
            return max(1, math.ceil((frees_at - now).total_seconds()))

    def blocked(self, ip: str, now: datetime) -> bool:
        return self.retry_after(ip, now) is not None

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


def study_last_day(participant: Participant, settings: Settings) -> date:
    return participant.enrollment_date + timedelta(days=settings.STUDY_DURATION_DAYS - 1)


def in_study_on(participant: Participant, settings: Settings, day: date) -> bool:
    """Μετρά η ημέρα `day` για τον συμμετέχοντα; (πάντα, αν POST_STUDY_ACCESS=true)"""
    return settings.POST_STUDY_ACCESS or day <= study_last_day(participant, settings)


def study_ended(participant: Participant, settings: Settings, now: datetime) -> bool:
    """Μόνο για την ομάδα παρέμβασης· η ομάδα ελέγχου ακολουθεί το CONTROL_ACCESS_FROM."""
    return participant.arm == Arm.INTERVENTION.value and \
        not in_study_on(participant, settings, local_today(settings.tz, now))


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_in: int


def login(db: Session, settings: Settings, limiter: LoginLimiter, client_ip: str, raw_key: str,
          now: datetime) -> LoginResult:
    wait = limiter.retry_after(client_ip, now)
    if wait is not None:
        raise rate_limited(wait)  # χωρίς audit: θα επέτρεπε απεριόριστες εγγραφές· φαίνεται στο access log (429)

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

    if study_ended(participant, settings, now):          # δεν μετρά ως αποτυχία login
        audit.record(db, "login_denied_study_ended", participant.id)
        db.commit()
        raise StudyEnded()

    token, expires_in = create_access_token(participant.id, participant.token_version,
                                            settings.JWT_SECRET.get_secret_value(),
                                            settings.ACCESS_TOKEN_TTL_MINUTES, now)
    audit.record(db, "login_succeeded", participant.id)
    db.commit()
    return LoginResult(token, expires_in)
