"""scripts/create_participant.py και Alembic: `alembic upgrade head` σε καινούργια SQLite, χωρίς διαφορά από τα μοντέλα."""
import re
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.models import AuditLog, Participant
from app.main import create_app

from .conftest import make_settings

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


def test_alembic_upgrade_head_matches_models_and_audit_triggers(tmp_path):
    db_file = tmp_path / "fresh.db"
    cfg = alembic_config(f"sqlite:///{db_file}")
    command.upgrade(cfg, "head")
    command.check(cfg)                                   # κανένα drift μεταξύ μετάβασης και μοντέλων
    con = sqlite3.connect(db_file)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(Base.metadata.tables) <= tables
    columns = {c[1] for t in Base.metadata.tables for c in con.execute(f"PRAGMA table_info({t})")}
    assert not {c for c in columns if re.search(r"image|photo_bytes|picture|blob", c)}   # Κανόνας 7
    con.execute("INSERT INTO audit_log (ts, event, payload) VALUES ('2026-11-09', 'x', '{}')")
    con.commit()
    for sql in ("UPDATE audit_log SET event='y'", "DELETE FROM audit_log"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            con.execute(sql)
    con.close()
    command.downgrade(cfg, "base")


def _load_cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location("create_participant", ROOT / "scripts" / "create_participant.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_participant_cli_prints_key_once_and_stores_only_hmac(tmp_path, capsys):
    db_file = tmp_path / "cli.db"
    settings = make_settings(DATABASE_URL=f"sqlite:///{db_file}")
    command.upgrade(alembic_config(f"sqlite:///{db_file}"), "head")
    assert _load_cli().main(["--sex", "F", "--age-years", "13", "--arm", "intervention"], settings=settings) == 0
    out = capsys.readouterr().out
    pid = re.search(r"pseudonym_id: (\S+)", out).group(1)
    key = re.search(r"access_key:\s+([0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4})", out).group(1)
    assert out.count(key) == 1
    raw = db_file.read_bytes()
    assert key.encode() not in raw and key.replace("-", "").encode() not in raw   # το κλειδί πουθενά στη βάση

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post("/api/v1/auth/login", json={"access_key": key})
        assert r.status_code == 200
        assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()["arm"] == "intervention"
    with app.state.sessionmaker() as s:
        p = s.query(Participant).one()
        assert str(p.id) == pid and p.age_years_at_enrollment == 13 and p.sex == "F"
        created = s.query(AuditLog).filter_by(event="participant_created").one()
        assert created.payload == {"arm": "intervention"} and str(created.participant_id) == pid
    app.state.engine.dispose()


@pytest.mark.parametrize("args", [
    ["--sex", "F", "--age-years", "9", "--arm", "control"],
    ["--sex", "F", "--age-years", "17", "--arm", "control"],
    ["--sex", "X", "--age-years", "12", "--arm", "control"],
    ["--sex", "F", "--age-years", "12", "--arm", "placebo"],
])
def test_create_participant_cli_validates(args):
    with pytest.raises(SystemExit):
        _load_cli().parse_args(args)
