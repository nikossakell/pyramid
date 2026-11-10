"""
Νυχτερινή κατανομή καρτών (π.χ. 03:00, από cron/systemd timer ή `docker compose exec backend ...`).

    python -m app.jobs.daily_card_drops                    # για χθες (στη ζώνη APP_TIMEZONE)
    python -m app.jobs.daily_card_drops --date 2026-11-09  # για συγκεκριμένη ημέρα

Μόνο ενεργοί συμμετέχοντες της ομάδας παρέμβασης. Idempotent: δεύτερη εκτέλεση για την ίδια ημέρα δεν δίνει διπλές
κάρτες. Βλ. app/services/card_service.py και rule_engine/card_rules.py.
"""
import argparse
import sys
from datetime import date, timedelta
from typing import Optional

from app.config import Settings
from app.core.clock import local_today, utcnow
from app.db.session import make_engine, make_sessionmaker
from app.services.card_service import run_card_drops
from app.services.food_catalog import load_catalog


def main(argv: Optional[list[str]] = None, settings: Optional[Settings] = None) -> int:
    settings = settings or Settings()
    p = argparse.ArgumentParser(description="Κάρτες της ημέρας (προεπιλογή: χθες).")
    p.add_argument("--date", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    args = p.parse_args(argv)
    day = args.date or local_today(settings.tz, utcnow()) - timedelta(days=1)
    catalog = load_catalog(settings.data_path(settings.FOODS_CSV), settings.data_path(settings.FOOD_ALIASES_CSV),
                           settings.DATA_DIR / "efsa_drv.csv", settings.DATA_DIR / "food_groups.csv")
    engine = make_engine(settings.DATABASE_URL.get_secret_value())
    with make_sessionmaker(engine)() as db:
        summary = run_card_drops(db, catalog, day)
    engine.dispose()
    print(f"day={summary['day']} participants={summary['participants']} new_cards={summary['new_cards']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
