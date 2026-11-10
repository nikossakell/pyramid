"""
app/core/security.py — κλειδιά πρόσβασης και JWT.

Κλειδί πρόσβασης: 12 τυχαίοι χαρακτήρες Crockford base32 (5 bit ο καθένας = 60 bit), σε μορφή XXXX-XXXX-XXXX.
Εμφανίζεται ΜΙΑ φορά, όταν δημιουργείται (scripts/create_participant.py). Στη βάση μόνο
HMAC-SHA256(ACCESS_KEY_PEPPER, κανονικοποιημένο κλειδί). Τα κλειδιά είναι τυχαία με υψηλή εντροπία, άρα δεν
χρειάζεται αργό hash (argon2): χωρίς το pepper, που δεν είναι στη βάση, το HMAC δεν αντιστρέφεται, και με
2^60 πιθανά κλειδιά η μαζική δοκιμή είναι ανέφικτη.

Κανονικοποίηση (Crockford): κεφαλαία, χωρίς παύλες/κενά, I/L -> 1, O -> 0, ώστε ένα παιδί που γράφει «o» αντί
για «0» να μπαίνει κανονικά.

JWT: HS256, sub = pseudonym_id, tv = token_version, iat, exp. Αύξηση του token_version ακυρώνει όλα τα tokens.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
KEY_GROUPS, KEY_GROUP_LEN = 3, 4
KEY_LEN = KEY_GROUPS * KEY_GROUP_LEN          # 12 χαρακτήρες x 5 bit = 60 bit
KEY_BITS = KEY_LEN * 5
_CONFUSABLE = str.maketrans({"I": "1", "L": "1", "O": "0"})
JWT_ALGORITHM = "HS256"


class InvalidToken(Exception):
    pass


def generate_access_key() -> str:
    raw = "".join(secrets.choice(CROCKFORD) for _ in range(KEY_LEN))
    return "-".join(raw[i:i + KEY_GROUP_LEN] for i in range(0, KEY_LEN, KEY_GROUP_LEN))


def normalize_access_key(raw: str) -> Optional[str]:
    """Κανονική μορφή (12 χαρακτήρες, χωρίς παύλες) ή None αν δεν είναι έγκυρο κλειδί."""
    if not isinstance(raw, str) or len(raw) > 64:
        return None
    s = "".join(raw.split()).replace("-", "").upper().translate(_CONFUSABLE)
    if len(s) != KEY_LEN or any(c not in CROCKFORD for c in s):
        return None
    return s


def key_hmac(normalized_key: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), normalized_key.encode("ascii"), hashlib.sha256).hexdigest()


def create_access_token(participant_id: uuid.UUID, token_version: int, secret: str, ttl_minutes: int,
                        now: datetime) -> tuple[str, int]:
    exp = now + timedelta(minutes=ttl_minutes)
    payload = {"sub": str(participant_id), "tv": token_version, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM), ttl_minutes * 60


def decode_access_token(token: str, secret: str) -> tuple[uuid.UUID, int]:
    try:
        claims = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "tv", "exp"]})
        tv = claims["tv"]
        if not isinstance(tv, int) or isinstance(tv, bool):
            raise InvalidToken("bad tv")
        return uuid.UUID(claims["sub"]), tv
    except (jwt.PyJWTError, ValueError, TypeError) as e:
        raise InvalidToken(type(e).__name__) from e
