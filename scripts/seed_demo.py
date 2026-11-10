"""
Δεδομένα ΕΠΙΔΕΙΞΗΣ για το backend (Swagger demo). ΜΟΝΟ με DEMO_MODE=true και ποτέ σε production.

    python scripts/seed_demo.py --photos /tmp/pyramid_demo/photos

Δημιουργεί (στη βάση του DATABASE_URL, μετά από `alembic upgrade head`):
  Α  παρέμβαση, 3 πλήρεις ημέρες γευμάτων  -> /feedback/today με μηνύματα, κάρτες (και streak 3 ημερών)
  Β  παρέμβαση, χωρίς ιστορικό               -> για ζωντανή καταγραφή: φωτογραφία, κείμενο, επιβεβαίωση
  Γ  ομάδα ελέγχου                           -> login 403 μέχρι το CONTROL_ACCESS_FROM
  Δ  παρέμβαση, ίδιο ιστορικό με το Α, ανοιχτό alert kind=safety -> /feedback/today χωρίς μηνύματα (ασφάλεια)
Τυπώνει τα κλειδιά πρόσβασης ΜΙΑ φορά. Με --photos γράφει συνθετικές εικόνες (όχι φωτογραφίες παιδιών):
meal.jpg (γίνεται δεκτή), dark.jpg (το demo φίλτρο την απορρίπτει), too_big.jpg (> 448 px), not_jpeg.png.
"""
import argparse
import sys
from datetime import timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core import audit  # noqa: E402
from app.core.clock import local_today, utcnow  # noqa: E402
from app.core.security import generate_access_key, key_hmac, normalize_access_key  # noqa: E402
from app.db.models import Alert, DayStatus, Meal, MealItem, Participant  # noqa: E402
from app.db.session import make_engine, make_sessionmaker  # noqa: E402
from app.services.card_service import run_card_drops  # noqa: E402
from app.services.food_catalog import load_catalog  # noqa: E402

DEMO_DAY = [("breakfast", [("milk", "medium"), ("wholegrain_bread", "small")]),
            ("lunch", [("chicken", "medium"), ("apple", "medium"), ("crisps", "small")])]
HISTORY_DAYS = 3


def write_photos(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    meal = Image.new("RGB", (400, 300), (196, 140, 70))
    for x in range(0, 400, 50):
        meal.paste((70, 150, 60), (x, 150, x + 25, 300))
        meal.paste((230, 210, 160), (x + 25, 0, x + 50, 120))
    files = {"meal.jpg": (meal, "JPEG"), "dark.jpg": (Image.new("RGB", (400, 300), (0, 0, 0)), "JPEG"),
             "too_big.jpg": (meal.resize((800, 600)), "JPEG"), "not_jpeg.png": (meal, "PNG")}
    out = []
    for name, (img, fmt) in files.items():
        img.save(directory / name, format=fmt)
        out.append(directory / name)
    return out


def main(argv: Optional[list[str]] = None, settings: Optional[Settings] = None) -> int:
    p = argparse.ArgumentParser(description="Δεδομένα επίδειξης (μόνο DEMO_MODE).")
    p.add_argument("--photos", type=Path, default=None, help="φάκελος για τις δοκιμαστικές εικόνες")
    args = p.parse_args(argv)
    settings = settings or Settings()
    if settings.ENVIRONMENT == "production" or not settings.DEMO_MODE:
        print("seed_demo: μόνο με DEMO_MODE=true και εκτός production", file=sys.stderr)
        return 2
    catalog = load_catalog(settings.data_path(settings.FOODS_CSV), settings.data_path(settings.FOOD_ALIASES_CSV),
                           settings.DATA_DIR / "efsa_drv.csv", settings.DATA_DIR / "food_groups.csv")
    engine = make_engine(settings.DATABASE_URL.get_secret_value())
    if "participants" not in inspect(engine).get_table_names():
        print("seed_demo: δεν υπάρχουν πίνακες — τρέξτε πρώτα `alembic upgrade head`", file=sys.stderr)
        return 2
    pepper = settings.ACCESS_KEY_PEPPER.get_secret_value()
    today = local_today(settings.tz, utcnow())
    rows = []
    with make_sessionmaker(engine)() as db:
        def participant(label, sex, age, arm, enrolled_days_ago):
            key = generate_access_key()
            p_ = Participant(key_hmac=key_hmac(normalize_access_key(key), pepper), sex=sex, age_years_at_enrollment=age,
                             arm=arm, enrollment_date=today - timedelta(days=enrolled_days_ago))
            db.add(p_)
            db.flush()
            audit.record(db, "participant_created", p_.id, arm=arm, demo=True)
            rows.append((label, arm, p_.id, key))
            return p_

        def history(p_):
            for k in range(1, HISTORY_DAYS + 1):
                day = today - timedelta(days=k)
                for slot, items in DEMO_DAY:
                    meal = Meal(participant_id=p_.id, eaten_on=day, meal_slot=slot, source="manual")
                    meal.items = [MealItem(position=n, food_id=f, portion=por, grams=catalog.grams(f, por),
                                           ai_suggested=False) for n, (f, por) in enumerate(items)]
                    db.add(meal)
                db.add(DayStatus(participant_id=p_.id, day=day, completed=True, completed_at=utcnow()))

        a = participant("Α (παρέμβαση, με ιστορικό)", "F", 12, "intervention", 7)
        history(a)
        participant("Β (παρέμβαση, χωρίς ιστορικό)", "M", 14, "intervention", 0)
        participant("Γ (ομάδα ελέγχου)", "F", 11, "control", 7)
        d = participant("Δ (παρέμβαση, ανοιχτό safety alert)", "M", 13, "intervention", 7)
        history(d)
        db.add(Alert(participant_id=d.id, kind="safety", category="demo_safety", note="DEMO"))
        db.commit()
        for k in range(HISTORY_DAYS, 0, -1):                          # η νυχτερινή εργασία για τις 3 ημέρες
            run_card_drops(db, catalog, today - timedelta(days=k))
    engine.dispose()

    print("\nDEMO συμμετέχοντες (τα κλειδιά εμφανίζονται μόνο τώρα):")
    for label, arm, pid, key in rows:
        print(f"  {label:38s} {key}   pseudonym_id={pid}")
    if args.photos:
        print("\nΔοκιμαστικές εικόνες (συνθετικές):")
        for f in write_photos(args.photos):
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
