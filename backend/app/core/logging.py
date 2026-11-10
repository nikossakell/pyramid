"""
app/core/logging.py — καταγραφή αιτημάτων (R6).

Μία γραμμή JSON ανά αίτημα: μέθοδος, path (ΧΩΡΙΣ query string), status, διάρκεια, pseudonym_id αν υπάρχει.
Ποτέ σώμα αιτήματος, query (π.χ. /foods/search?q=), headers (Authorization). Το access log του uvicorn πρέπει
να είναι κλειστό (--no-access-log), γιατί εκείνο γράφει το query string.
"""
import json
import logging
import time

from fastapi import FastAPI, Request

ACCESS_LOGGER = "pyramid.access"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname,
                "logger": record.name, "msg": record.getMessage()}
        data.update(getattr(record, "fields", {}))
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger("pyramid")
    if not any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.setLevel(level)


def install_access_log(app: FastAPI) -> None:
    logger = logging.getLogger(ACCESS_LOGGER)

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            fields = {"method": request.method, "path": request.url.path, "status": status,
                      "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                      "pseudonym_id": getattr(request.state, "pseudonym_id", None)}
            logger.info("request", extra={"fields": fields})
