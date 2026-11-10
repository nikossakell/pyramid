"""
Δημιουργία alert (ΜΟΝΟ από εδώ· η εφαρμογή δεν δημιουργεί alerts αυτόματα — docs/backend_spec_v1.md, Τροποποίηση 4).

    python scripts/create_alert.py --participant <pseudonym_id> --kind safety --category disordered_eating
    python scripts/create_alert.py --participant <pseudonym_id> --kind operational --category device_lost --note "..."

kind=safety και status ≠ closed: καμία ανατροφοδότηση πρόσληψης στο παιδί μέχρι να κλείσει (POST
/api/v1/admin/alerts/{id}/status). ΜΟΝΟ κωδικός και κατηγορία· ποτέ κείμενο του παιδιού (η σημείωση είναι του ερευνητή).
"""
import argparse
import re
import sys
import uuid
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.core import audit  # noqa: E402
from app.db.models import Alert, Participant  # noqa: E402
from app.db.models.alert import MAX_NOTE_CHARS  # noqa: E402
from app.db.models.enums import AlertKind  # noqa: E402
from app.db.session import make_engine, make_sessionmaker  # noqa: E402

CATEGORY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Νέο alert για έναν κωδικό συμμετέχοντα.")
    p.add_argument("--participant", required=True, type=uuid.UUID)
    p.add_argument("--kind", required=True, choices=[k.value for k in AlertKind])
    p.add_argument("--category", required=True, help="π.χ. disordered_eating, self_harm, device_lost (a-z, 0-9, _)")
    p.add_argument("--note", default=None, help=f"σημείωση ερευνητή, έως {MAX_NOTE_CHARS} χαρακτήρες")
    args = p.parse_args(argv)
    if not CATEGORY.match(args.category):
        p.error("--category: a-z, 0-9 and _ only (no free text)")
    if args.note is not None and len(args.note) > MAX_NOTE_CHARS:
        p.error(f"--note longer than {MAX_NOTE_CHARS} characters")
    return args


def main(argv: Optional[list[str]] = None, settings: Optional[Settings] = None) -> int:
    args = parse_args(argv)
    settings = settings or Settings()
    engine = make_engine(settings.DATABASE_URL.get_secret_value())
    with make_sessionmaker(engine)() as db:
        if db.get(Participant, args.participant) is None:
            print("unknown participant", file=sys.stderr)
            return 1
        alert = Alert(participant_id=args.participant, kind=args.kind, category=args.category, note=args.note)
        db.add(alert)
        db.flush()
        audit.record(db, "alert_created", args.participant, alert_id=str(alert.id), kind=args.kind,
                     category=args.category)
        db.commit()
        alert_id = alert.id
    engine.dispose()
    print(f"alert_id: {alert_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
