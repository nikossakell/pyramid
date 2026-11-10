"""
app/core/clock.py — χρόνος της εφαρμογής.

Ο server κρατά UTC (aware datetimes). Το «σήμερα» του παιδιού (γεύματα, ημέρες, κάρτες, πρόσβαση ομάδας ελέγχου)
είναι η ημερομηνία στη ζώνη APP_TIMEZONE. Το SQLite επιστρέφει naive datetimes· το aware() τα θεωρεί UTC.
"""
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def local_today(tz: ZoneInfo, now: datetime) -> date:
    return now.astimezone(tz).date()
