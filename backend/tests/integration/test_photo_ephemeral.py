"""
Κανόνας 7 (docs/ephemeral-processing.md): 1000 uploads δεν αφήνουν κανένα νέο αρχείο, ούτε στο tempfile.gettempdir()
ούτε στον φάκελο της εφαρμογής, και κανένα byte εικόνας στη βάση (audit: stored_bytes 0).

Το tempfile.gettempdir() δείχνει εδώ σε άδειο, δικό μας φάκελο: ό,τι θα έγραφε σε προσωρινό αρχείο (π.χ. ένα
UploadFile / SpooledTemporaryFile) θα εμφανιζόταν εκεί. Τους φακέλους του συστήματος (Nginx, tmpfs, swap) τους ελέγχει
το scripts/check_ephemeral.sh στο deployment.
"""
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models import AuditLog, Meal
from tests.api.conftest import add_participant, build_app, login
from tests.api.photos import dark_jpeg, jpeg

UPLOADS = 1000
BACKEND = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def snapshot(root: Path) -> set[tuple[str, int]]:
    out = set()
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            p = Path(d) / f
            out.add((str(p.relative_to(root)), p.stat().st_size))
    return out


def test_1000_uploads_leave_no_file(tmp_path, monkeypatch):
    private_tmp = tmp_path / "tmp"
    private_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(private_tmp))
    monkeypatch.setenv("TMPDIR", str(private_tmp))
    assert tempfile.gettempdir() == str(private_tmp)

    app = build_app(DEMO_MODE=True)
    before = snapshot(BACKEND)
    images = [jpeg(400, 300, (30 + i % 200, 90, 60)) for i in range(10)]
    with TestClient(app) as client:
        participants = [login(client, add_participant(app)[1]) for _ in range(4)]
        accepted = rejected = 0
        for n in range(UPLOADS):
            headers = {**participants[n % 4], "Content-Type": "image/jpeg"}
            if n % 250 == 0:                                         # λίγες απορρίψεις, κάτω από το όριο αναστολής
                assert client.post("/api/v1/meals/photo", content=dark_jpeg(), headers=headers).status_code == 422
                rejected += 1
            else:
                assert client.post("/api/v1/meals/photo", content=images[n % 10], headers=headers).status_code == 200
                accepted += 1

    assert list(private_tmp.iterdir()) == []                        # τίποτα στο tempfile.gettempdir()
    assert snapshot(BACKEND) == before                               # τίποτα στον φάκελο της εφαρμογής
    with app.state.sessionmaker() as s:
        assert s.query(Meal).count() == 0                            # R3: οι προτάσεις δεν αποθηκεύονται
        rows = s.query(AuditLog).filter(AuditLog.event.in_(["photo_processed", "photo_rejected"])).all()
        assert len(rows) == UPLOADS and accepted + rejected == UPLOADS
        assert all(r.payload["stored_bytes"] == 0 for r in rows)
    app.state.engine.dispose()
