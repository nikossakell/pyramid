"""
app/db/models/append_only.py — πίνακες στους οποίους η εφαρμογή ΜΟΝΟ προσθέτει (audit_log, alert_events).

Πρώτο δίχτυ (ORM): before_update / before_delete στο μοντέλο και κάθε UPDATE/DELETE statement του ORM στον πίνακα ->
AppendOnlyError. Το δεύτερο δίχτυ είναι οι triggers της βάσης (μεταβάσεις 001 και 004)· το τρίτο, η μία συνάρτηση
εγγραφής κάθε πίνακα (app.core.audit.record, alert_service.record_event), που ελέγχει τι επιτρέπεται να γραφτεί.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session

_APPEND_ONLY: list[type] = []


class AppendOnlyError(RuntimeError):
    pass


def append_only(model: type) -> type:
    """Καταχωρεί το μοντέλο ως append-only (χρήση: append_only(Model) μετά τον ορισμό του)."""
    message = f"{model.__tablename__} is append-only"

    def _refuse(*_):
        raise AppendOnlyError(message)

    event.listen(model, "before_update", _refuse)
    event.listen(model, "before_delete", _refuse)
    _APPEND_ONLY.append(model)
    return model


@event.listens_for(Session, "do_orm_execute")
def _no_bulk_changes(state):
    if not (state.is_update or state.is_delete):
        return
    for m in state.all_mappers:
        for model in _APPEND_ONLY:
            if getattr(m, "entity", None) is model or getattr(m, "local_table", None) is model.__table__:
                raise AppendOnlyError(f"{model.__tablename__} is append-only")
