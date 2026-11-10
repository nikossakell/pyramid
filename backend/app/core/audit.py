"""
app/core/audit.py — εγγραφή στο audit log (Κανόνας 5, R5).

record() προσθέτει μία γραμμή· το commit το κάνει ο καλών, στην ίδια συναλλαγή με την ενέργεια που καταγράφει.
Αρνείται (ValueError) payload με bytes οποιουδήποτε τύπου ή με κλειδιά που θα μπορούσαν να κρατούν κλειδί
πρόσβασης, token ή εικόνα, ώστε ένα λάθος στον κώδικα να σπάσει στα tests αντί να γράψει κάτι τέτοιο.
"""
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import AuditLog

FORBIDDEN_KEYS = frozenset({
    "key", "access_key", "key_hmac", "token", "access_token", "jwt", "authorization", "password", "secret",
    "image", "image_bytes", "photo", "photo_bytes", "body", "raw",
})


def _check(value: Any, path: str) -> None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError(f"audit payload must not contain bytes ({path})")
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"audit payload key not allowed: {path}.{k}")
            _check(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple, set, frozenset)):
        for i, v in enumerate(value):
            _check(v, f"{path}[{i}]")


def record(db: Session, event: str, participant_id: Optional[uuid.UUID] = None, **payload: Any) -> AuditLog:
    _check(payload, event)
    row = AuditLog(event=event, participant_id=participant_id, payload=payload)
    db.add(row)
    return row
