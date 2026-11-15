"""
app/services/analysis_audit.py — έξοδος του μοντέλου για την αξιολόγησή του (Αποφάσεις 29 και 34–36 του 2026-11-12).

Δύο είδη εγγραφών στο audit:

1. Ανάλυση (`photo_processed`, `text_processed`): ΧΩΡΙΣ participant_id. Κάθε ανάλυση παίρνει νέο analysis_id (UUID)
   που επιστρέφεται στο παιδί μαζί με τις προτάσεις. Payload μόνο: analysis_id, model_id, model_labels (μόνο
   φωτογραφία), resolved_food_ids, pipeline, shown (ό,τι είδε το παιδί, μόνο food_id). Για τη φωτογραφία και
   stored_bytes: 0 (Κανόνας 9). Ποτέ bytes, διαστάσεις, EXIF ή hash εικόνας· ποτέ κείμενο του παιδιού ή τμήμα του.
2. Έκβαση (`suggestion_outcome`, ΜΕ participant_id): όταν το παιδί επιβεβαιώνει γεύμα με analysis_id. Payload:
   analysis_id, meal_id, analysis_found και ανά τρόφιμο {outcome, food_id[, instead_of]}, outcome ∈ OUTCOMES.

Η σύνδεση ανάλυσης ↔ παιδιού υπάρχει ΜΟΝΟ για αναλύσεις που κατέληξαν σε επιβεβαιωμένο γεύμα. Κανένα endpoint (ούτε
admin) δεν διαβάζει αυτές τις εγγραφές· πρόσβαση μόνο με εξαγωγή από τη βάση (Κύριος Ερευνητής, DPIA).
"""
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.db.models import AuditLog, Meal
from app.services.suggestion_service import Suggestion

ANALYSIS_EVENTS = ("photo_processed", "text_processed")
OUTCOME_EVENT = "suggestion_outcome"
ACCEPTED, PORTION_CHANGED, ALTERNATIVE_CHOSEN, REMOVED, ADDED = (
    "accepted", "portion_changed", "alternative_chosen", "removed", "added")
OUTCOMES = (ACCEPTED, PORTION_CHANGED, ALTERNATIVE_CHOSEN, REMOVED, ADDED)


def shown(items: list[Suggestion]) -> list[dict]:
    """Ό,τι είδε το παιδί, μόνο κωδικοί του πίνακα: food_id (null αν δεν βρέθηκε· το όνομα ΔΕΝ γράφεται, γιατί στο
    κείμενο είναι λέξεις του παιδιού), προτεινόμενη μερίδα (σήμερα πάντα null) και τα food_id των alternatives."""
    return [{"food_id": s.food_id, "portion": None, "alternatives": [fid for fid, _ in s.alternatives]} for s in items]


def record_analysis(db: Session, event: str, analysis_id: uuid.UUID, **payload: Any) -> AuditLog:
    if event not in ANALYSIS_EVENTS:
        raise ValueError(f"not an analysis event: {event}")
    return audit.record(db, event, None, analysis_id=str(analysis_id), **payload)   # participant_id: ΠΟΤΕ


def find_analysis(db: Session, analysis_id: uuid.UUID) -> Optional[dict]:
    row = db.scalar(select(AuditLog).where(
        AuditLog.event.in_(ANALYSIS_EVENTS), AuditLog.participant_id.is_(None),
        AuditLog.payload["analysis_id"].as_string() == str(analysis_id)).limit(1))
    return row.payload if row is not None else None


def outcomes(shown_items: list[dict], confirmed: list[dict]) -> list[dict]:
    """Σύγκριση προτάσεων ↔ επιβεβαιωμένου γεύματος, ανά τρόφιμο. Κάθε πρόταση χρησιμοποιείται μία φορά.
    accepted / portion_changed: το ίδιο food_id (portion_changed μόνο αν η πρόταση είχε μερίδα και άλλαξε)·
    alternative_chosen: food_id από τα alternatives μιας πρότασης που δεν χρησιμοποιήθηκε (instead_of = η πρόταση)·
    added: τρόφιμο που δεν προτάθηκε· removed: πρόταση που δεν χρησιμοποιήθηκε (food_id null αν δεν είχε βρεθεί)."""
    used = [False] * len(shown_items)
    out: list[dict] = []
    for item in confirmed:
        fid = item["food_id"]
        hit = next((n for n, s in enumerate(shown_items) if not used[n] and s.get("food_id") == fid), None)
        if hit is not None:
            used[hit] = True
            suggested = shown_items[hit].get("portion")
            changed = suggested is not None and suggested != item["portion"]
            out.append({"outcome": PORTION_CHANGED if changed else ACCEPTED, "food_id": fid})
            continue
        alt = next((n for n, s in enumerate(shown_items) if not used[n] and fid in (s.get("alternatives") or [])), None)
        if alt is not None:
            used[alt] = True
            out.append({"outcome": ALTERNATIVE_CHOSEN, "food_id": fid, "instead_of": shown_items[alt].get("food_id")})
            continue
        out.append({"outcome": ADDED, "food_id": fid})
    out += [{"outcome": REMOVED, "food_id": s.get("food_id")} for n, s in enumerate(shown_items) if not used[n]]
    return out


def record_outcome(db: Session, participant_id: uuid.UUID, analysis_id: uuid.UUID, meal: Meal,
                   confirmed: list[dict]) -> AuditLog:
    """Γράφεται μόνο για ΝΕΟ γεύμα (όχι σε επανάληψη του client_meal_id). Άγνωστο analysis_id δεν αποτυγχάνει το
    γεύμα: analysis_found=false, χωρίς items. Το commit το κάνει ο καλών."""
    analysis = find_analysis(db, analysis_id)
    found = analysis is not None
    items = outcomes(analysis.get("shown") or [], confirmed) if found else []
    return audit.record(db, OUTCOME_EVENT, participant_id, analysis_id=str(analysis_id), meal_id=str(meal.id),
                        analysis_found=found, items=items)
