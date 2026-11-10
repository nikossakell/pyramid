"""Swagger UI / OpenAPI για demo: Authorize με JWT παιδιού και X-Admin-Token, upload raw image/jpeg, παραδείγματα με
τη σημερινή ημερομηνία. Ποτέ σε production."""
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.clock import local_today, utcnow
from app.main import create_app

from .conftest import build_app, make_settings


@pytest.fixture
def openapi(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    return r.json()


def test_swagger_ui_served_with_persistent_authorization(client):
    r = client.get("/docs")
    assert r.status_code == 200 and "swagger-ui" in r.text
    assert '"persistAuthorization": true' in r.text and '"tryItOutEnabled": true' in r.text


def test_security_schemes_for_child_and_admin(openapi):
    schemes = openapi["components"]["securitySchemes"]
    assert schemes["ChildJWT"] == {**schemes["ChildJWT"], "type": "http", "scheme": "bearer"}
    assert schemes["AdminToken"] == {**schemes["AdminToken"], "type": "apiKey", "in": "header", "name": "X-Admin-Token"}
    paths = openapi["paths"]
    child = {("/api/v1/me", "get"), ("/api/v1/meals/photo", "post"), ("/api/v1/feedback/today", "get"),
             ("/api/v1/cards", "get"), ("/api/v1/ask", "post")}
    for path, method in child:
        assert paths[path][method]["security"] == [{"ChildJWT": []}], path
    for path, ops in paths.items():
        if path.startswith("/api/v1/admin/"):
            assert all(op["security"] == [{"AdminToken": []}] for op in ops.values()), path
    assert "security" not in paths["/api/v1/auth/login"]["post"] and "security" not in paths["/api/v1/health"]["get"]


def test_photo_is_a_raw_jpeg_upload_not_multipart(openapi):
    body = openapi["paths"]["/api/v1/meals/photo"]["post"]["requestBody"]
    assert body["required"] is True and set(body["content"]) == {"image/jpeg"}
    assert body["content"]["image/jpeg"]["schema"] == {"type": "string", "format": "binary"}
    assert "multipart/form-data" not in str(openapi)
    responses = openapi["paths"]["/api/v1/meals/photo"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["example"] == {"rejected": True}


def test_examples_use_today_and_valid_foods(app, client, openapi, child):
    today = local_today(ZoneInfo("Europe/Athens"), utcnow()).isoformat()
    examples = openapi["paths"]["/api/v1/meals/confirm"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    _, _, headers = child
    for ex in examples.values():
        assert ex["value"]["eaten_on"] == today
        assert client.post("/api/v1/meals/confirm", json=ex["value"], headers=headers).status_code == 201   # δουλεύει όπως είναι


def test_every_endpoint_is_documented(openapi):
    expected = {"/api/v1/health", "/api/v1/auth/login", "/api/v1/me", "/api/v1/foods/search", "/api/v1/meals/photo",
                "/api/v1/meals/text", "/api/v1/meals/confirm", "/api/v1/meals", "/api/v1/meals/{meal_id}",
                "/api/v1/days/{day}/complete", "/api/v1/feedback/today", "/api/v1/cards", "/api/v1/cards/{card_id}/open",
                "/api/v1/ask", "/api/v1/admin/alerts", "/api/v1/admin/alerts/{alert_id}/status",
                "/api/v1/admin/participants/{participant_id}/deactivate", "/api/v1/admin/photo-suspensions"}
    assert set(openapi["paths"]) == expected
    assert all(op.get("summary") for ops in openapi["paths"].values() for op in ops.values())
    assert "Demo" in openapi["info"]["description"]


def test_no_docs_in_production(tmp_path):
    from .test_config import PROD
    foods = tmp_path / "foods.csv"
    src = (make_settings().DATA_DIR / "demo_foods.csv").read_text(encoding="utf-8").splitlines()
    foods.write_text("\n".join([src[0], src[1].replace("DEMO — ΟΧΙ πραγματικές τιμές", "TEST").replace(",true", ",false")])
                     + "\n", encoding="utf-8")
    (tmp_path / "aliases.csv").write_text("food_id,alias\n", encoding="utf-8")
    app = create_app(make_settings(**PROD, FOODS_CSV=foods, FOOD_ALIASES_CSV=tmp_path / "aliases.csv"))
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404
    with pytest.raises(ValidationError, match="API_DOCS must not be true"):
        make_settings(**PROD, API_DOCS=True)


def test_docs_can_be_switched_off_outside_production():
    app = build_app(API_DOCS=False)
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
