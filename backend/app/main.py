"""
app/main.py — FastAPI: create_app() και το `app` για το uvicorn.

Το `app` δημιουργείται τεμπέλικα (PEP 562): `uvicorn app.main:app` το ζητά και τότε διαβάζονται οι ρυθμίσεις,
ενώ τα tests εισάγουν το create_app χωρίς να χρειάζονται μεταβλητές περιβάλλοντος.
Swagger UI (/docs) και /openapi.json μόνο εκτός production (API_DOCS· βλ. app/api/docs.py).

Ο πίνακας τροφίμων φορτώνεται εδώ, μία φορά. Σε ENVIRONMENT=production η εφαρμογή ΑΡΝΕΙΤΑΙ να ξεκινήσει αν έχει
demo γραμμές (οι τιμές του data/demo_foods.csv δεν είναι πραγματικές).
"""
from datetime import timedelta
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_pipeline.presentation.krikri_presenter import KrikriPresenter
from ai_pipeline.text.krikri_client import OpenAICompatibleClient
from rule_engine.data_loader import load_reference_values

from app.api import admin, ask, auth, cards, days, feedback, foods, health, me, meals
from app.api.docs import APP_VERSION, DESCRIPTION, SWAGGER_UI_PARAMETERS, TAGS, install_openapi
from app.config import Settings, get_settings
from app.core.clock import utcnow
from app.core.logging import install_access_log, setup_logging
from app.db.session import make_engine, make_sessionmaker
from app.services.auth_service import LoginLimiter
from app.services.food_catalog import load_catalog
from app.services.photo_pipeline import build_photo_pipeline
from app.services.suggestion_service import DeterministicTextExtractor

API_PREFIX = "/api/v1"


class StartupError(RuntimeError):
    pass


def build_presenter(settings: Settings) -> KrikriPresenter:
    """Krikri μόνο αν έχουν οριστεί LLM_BASE_URL και LLM_MODEL· αλλιώς μόνο σταθερά κείμενα (Απόφαση 2 του 4.2)."""
    client = None
    if settings.LLM_BASE_URL and settings.LLM_MODEL:
        client = OpenAICompatibleClient(settings.LLM_BASE_URL, settings.LLM_MODEL,
                                        timeout_s=settings.PRESENTER_TIMEOUT_SECONDS)
    return KrikriPresenter(client=client)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.LOG_LEVEL)
    catalog = load_catalog(settings.data_path(settings.FOODS_CSV), settings.data_path(settings.FOOD_ALIASES_CSV),
                           settings.DATA_DIR / "efsa_drv.csv", settings.DATA_DIR / "food_groups.csv")
    if settings.ENVIRONMENT == "production" and catalog.has_demo:
        raise StartupError("refusing to start in production: the food table contains demo rows (is_demo=true)")
    docs = settings.docs_enabled
    app = FastAPI(title="PYRAMID API", version=APP_VERSION, description=DESCRIPTION, openapi_tags=TAGS,
                  docs_url="/docs" if docs else None, redoc_url=None, openapi_url="/openapi.json" if docs else None,
                  swagger_ui_parameters=SWAGGER_UI_PARAMETERS)

    engine = make_engine(settings.DATABASE_URL.get_secret_value())
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.clock = utcnow
    app.state.catalog = catalog
    app.state.references = load_reference_values(settings.DATA_DIR / "efsa_drv.csv")
    app.state.presenter = build_presenter(settings)
    app.state.photo_pipeline = build_photo_pipeline(settings)
    app.state.text_extractor = DeterministicTextExtractor(catalog)
    app.state.login_limiter = LoginLimiter(settings.LOGIN_MAX_FAILURES, timedelta(minutes=settings.LOGIN_WINDOW_MINUTES))

    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                           allow_methods=["GET", "POST", "PATCH", "DELETE"],
                           allow_headers=["Authorization", "Content-Type"])
    install_access_log(app)

    for module in (health, auth, me, foods, meals, days, feedback, cards, ask, admin):
        app.include_router(module.router, prefix=API_PREFIX)
    if docs:
        install_openapi(app, settings)
    return app


def __getattr__(name: str):
    if name == "app":
        globals()["app"] = application = create_app()
        return application
    raise AttributeError(name)
