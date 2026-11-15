"""
app/services/system_status.py — κατάσταση συστήματος για την κονσόλα του ερευνητή (A03). ΚΑΝΕΝΑ δεδομένο συμμετέχοντα.

demo_mode: η ρύθμιση DEMO_MODE (demo φίλτρα / αναγνώριση). Μόνο εδώ και στο log εκκίνησης· τίποτα προς το παιδί.
versions: sha256 των CSV (data_versions του engine), sha256 του rag_sources.csv (μόνο ανάγνωση), εκδόσεις presenter /
          prompt, αν ο πίνακας τροφίμων έχει demo γραμμές, ονόματα μοντέλων από τις ρυθμίσεις (ή null).
services: db (SELECT 1), llm (GET {LLM_BASE_URL}/models με LLM_PROBE_TIMEOUT_SECONDS· "not_configured" αν λείπουν οι
          ρυθμίσεις), photo_pipeline (available | demo | unavailable), last_card_job (από τον πίνακα job_runs).
Δεν επιστρέφει ποτέ URL, κλειδιά ή μηνύματα σφαλμάτων (μπορεί να περιέχουν διευθύνσεις): μόνο κλειστές τιμές.
"""
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_pipeline.presentation.krikri_presenter import PRESENTER_VERSION
from ai_pipeline.presentation.prompts import PROMPT_VERSION

from app.config import Settings
from app.core.clock import aware
from app.services.card_service import last_card_job
from app.services.food_catalog import FoodCatalog, sha256_file
from app.services.photo_pipeline import PhotoPipeline

LLM_PROBE_TIMEOUT_SECONDS = 2.0     # ΠΡΟΣΧΕΔΙΟ: η κονσόλα δεν περιμένει το μοντέλο
RAG_SOURCES_CSV = "rag_sources.csv"

LlmProbe = Callable[[str, float], bool]


def http_llm_probe(base_url: str, timeout_s: float) -> bool:
    """True αν το GET {base_url}/models απαντά 2xx μέσα στο timeout. Τοπικός server: ποτέ μέσω proxy."""
    url = base_url.rstrip("/") + "/models"
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        return False
    host = urllib.parse.urlparse(url).hostname or ""
    opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
              if host in {"localhost", "127.0.0.1", "::1"} else urllib.request.build_opener())
    try:
        with opener.open(urllib.request.Request(url, method="GET"), timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _db_status(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "unavailable"
    return "ok"


def _llm_status(settings: Settings, probe: LlmProbe) -> str:
    if not (settings.LLM_BASE_URL and settings.LLM_MODEL):
        return "not_configured"
    try:
        return "ok" if probe(settings.LLM_BASE_URL, LLM_PROBE_TIMEOUT_SECONDS) else "unavailable"
    except Exception:
        return "unavailable"


def _photo_status(settings: Settings, pipeline: PhotoPipeline) -> str:
    if not pipeline.available:
        return "unavailable"
    return "demo" if settings.DEMO_MODE else "available"


def _sha256_or_none(path: Path) -> Optional[str]:
    try:
        return sha256_file(path)
    except OSError:
        return None


def system_status(db: Session, settings: Settings, catalog: FoodCatalog, pipeline: PhotoPipeline,
                  probe: LlmProbe = http_llm_probe, app_version: Optional[str] = None) -> dict:
    services = {"db": _db_status(db), "llm": _llm_status(settings, probe),
                "photo_pipeline": _photo_status(settings, pipeline), "last_card_job": None}
    if services["db"] == "ok":
        run = last_card_job(db)
        if run is not None:
            services["last_card_job"] = {"day": run.day, "run_at": aware(run.started_at),
                                         "finished_at": aware(run.finished_at), "status": run.status,
                                         "drops": run.count}
    return {
        "demo_mode": settings.DEMO_MODE,
        "versions": {
            "app": app_version,
            "data_versions": dict(catalog.versions),
            "rag_sources_sha256": _sha256_or_none(settings.DATA_DIR / RAG_SOURCES_CSV),
            "prompt_version": PROMPT_VERSION,
            "presenter_version": PRESENTER_VERSION,
            "foods_is_demo": catalog.has_demo,
            "models": {"llm": settings.LLM_MODEL, **pipeline.versions},
        },
        "services": services,
    }
