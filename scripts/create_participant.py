"""
Δημιουργία συμμετέχοντα (ΜΟΝΟ από εδώ· δεν υπάρχει endpoint εγγραφής).

    python scripts/create_participant.py --sex F --age-years 12 --arm intervention
    python scripts/create_participant.py --sex M --age-years 14 --arm control --enrollment-date 2026-11-16

Τυπώνει το pseudonym_id και το κλειδί πρόσβασης ΜΙΑ φορά. Το κλειδί δεν αποθηκεύεται πουθενά (στη βάση μόνο
HMAC με το ACCESS_KEY_PEPPER) και δεν μπορεί να ανακτηθεί: αν χαθεί, δημιουργείται νέος συμμετέχων ή νέο κλειδί.
Ο server δεν γνωρίζει ποιο παιδί αντιστοιχεί στον κωδικό (R2)· η αντιστοίχιση κρατιέται εκτός server, στο χαρτί.

Χρειάζεται τις μεταβλητές της εφαρμογής (.env) και πίνακες στη βάση (`alembic upgrade head`).
"""
import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core import audit  # noqa: E402
from app.core.clock import local_today, utcnow  # noqa: E402
from app.core.security import generate_access_key, key_hmac, normalize_access_key  # noqa: E402
from app.db.models import Participant  # noqa: E402
from app.db.models.enums import Arm, Sex  # noqa: E402
from app.db.models.participant import MAX_AGE_YEARS, MIN_AGE_YEARS  # noqa: E402
from app.db.session import make_engine, make_sessionmaker  # noqa: E402


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Νέος συμμετέχων: τυπώνει pseudonym_id και κλειδί πρόσβασης μία φορά.")
    p.add_argument("--sex", required=True, choices=[s.value for s in Sex])
    p.add_argument("--age-years", required=True, type=int,
                   help=f"συμπληρωμένα έτη κατά την εγγραφή ({MIN_AGE_YEARS}-{MAX_AGE_YEARS}, πρωτόκολλο)")
    p.add_argument("--arm", required=True, choices=[a.value for a in Arm])
    p.add_argument("--enrollment-date", type=date.fromisoformat, default=None,
                   help="YYYY-MM-DD (προεπιλογή: σήμερα στη ζώνη APP_TIMEZONE)")
    args = p.parse_args(argv)
    if not MIN_AGE_YEARS <= args.age_years <= MAX_AGE_YEARS:
        p.error(f"--age-years must be {MIN_AGE_YEARS}-{MAX_AGE_YEARS}")
    return args


def main(argv: Optional[list[str]] = None, settings: Optional[Settings] = None) -> int:
    args = parse_args(argv)
    settings = settings or Settings()
    engine = make_engine(settings.DATABASE_URL.get_secret_value())
    pepper = settings.ACCESS_KEY_PEPPER.get_secret_value()
    with make_sessionmaker(engine)() as db:
        while True:   # σύγκρουση HMAC: πρακτικά αδύνατη με 2^60 κλειδιά, αλλά ελέγχεται
            key = generate_access_key()
            digest = key_hmac(normalize_access_key(key), pepper)
            if db.scalar(select(Participant.id).where(Participant.key_hmac == digest)) is None:
                break
        participant = Participant(
            key_hmac=digest, sex=args.sex, age_years_at_enrollment=args.age_years, arm=args.arm,
            enrollment_date=args.enrollment_date or local_today(settings.tz, utcnow()),
        )
        db.add(participant)
        db.flush()
        audit.record(db, "participant_created", participant.id, arm=args.arm)
        db.commit()
        pid = participant.id
    engine.dispose()
    print(f"pseudonym_id: {pid}")
    print(f"access_key:   {key}")
    print("Το κλειδί εμφανίζεται μόνο τώρα και δεν αποθηκεύεται πουθενά. Δώστε το στο παιδί σε χαρτί.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
