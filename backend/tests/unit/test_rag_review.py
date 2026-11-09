"""Απόφαση 10: αξιολόγηση σε επίπεδο αποσπάσματος (CSV για άνθρωπο, scripts/score_review.py)."""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

from ai_pipeline.rag.chunking import Chunk
from ai_pipeline.rag.index import Hit
from ai_pipeline.rag.review import (ANSWER_COL, COMMENT_COL, REVIEW_COLUMNS, ReviewError, read_review,
                                    review_rows, score_review, write_review_csv)

ROOT = Path(__file__).resolve().parents[3]


def hit(cid, text="κείμενο", score=0.5):
    c = Chunk(chunk_id=cid, source_id=cid.split(":")[0], title="T", organization="O", version="v1", language="en",
              section="S", page_start=3, page_end=4, text=text, text_sha256="x", approved=True)
    return Hit(c, score, 1, None)


def write(path, answers):
    """answers: {(ερώτηση, expected_sources): [απάντηση θέσης 1, 2, 3]}"""
    rows = []
    for (q, exp), vals in answers.items():
        for r in review_rows(q, exp, [hit(f"s:{i:04d}") for i in range(1, 4)]):
            r[ANSWER_COL] = vals[r["rank"] - 1]
            rows.append(r)
    write_review_csv(path, rows)


def test_review_rows_and_csv_format(tmp_path):
    rows = review_rows("Ερώτηση;", "a;b", [hit("a:0001", "x" * 1000), hit("a:0002"), hit("b:0001"), hit("b:0002")])
    assert [r["rank"] for r in rows] == [1, 2, 3] and rows[0]["pages"] == "3-4"
    assert len(rows[0]["text"]) == 600 and rows[0][ANSWER_COL] == "" and rows[0][COMMENT_COL] == ""
    write_review_csv(tmp_path / "r.csv", rows)
    raw = (tmp_path / "r.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                       # utf-8-sig: σωστά ελληνικά στο Excel
    with (tmp_path / "r.csv").open(encoding="utf-8-sig", newline="") as f:
        assert next(csv.reader(f)) == REVIEW_COLUMNS


def test_score(tmp_path):
    write(tmp_path / "r.csv", {
        ("Q1", "efsa_iron_2015"): ["ναι", "όχι", "όχι"],
        ("Q2", "efsa_calcium_2015"): ["μερικώς", "ναι", "όχι"],
        ("Q3", "gr_guide_children"): ["όχι", "μερικώς", "όχι"],
        ("Q4", "efsa_fibre_2010"): ["Όχι ", " ΝΑΙ", "όχι"],      # πεζά/κεφαλαία και κενά επιτρέπονται
        ("OFF1", ""): ["όχι", "όχι", "όχι"],
        ("OFF2", ""): ["όχι", "ναι", "όχι"],
    })
    s = score_review(read_review(tmp_path / "r.csv"))
    assert s["on_topic_n"] == 4 and s["precision_at_1"] == pytest.approx((1 + 0.5 + 0 + 0) / 4)
    assert s["answerable_at_3"] == pytest.approx(3 / 4) and s["no_yes"] == ["Q3"]
    assert s["off_topic_n"] == 2 and s["off_topic_yes_share"] == pytest.approx(0.5)
    assert s["off_topic_with_yes"] == ["OFF2"]


def test_invalid_values_reported_with_line_numbers(tmp_path):
    rows = review_rows("Q1", "x", [hit("s:0001", "γραμμή 1\nγραμμή 2"), hit("s:0002"), hit("s:0003")])
    for r, v in zip(rows, ["ναι", "ίσως", ""]):
        r[ANSWER_COL] = v
    write_review_csv(tmp_path / "r.csv", rows)
    with pytest.raises(ReviewError) as e:
        read_review(tmp_path / "r.csv")
    msg = str(e.value)
    # γραμμή 1: επικεφαλίδα· η 1η εγγραφή πιάνει τις γραμμές 2-3 (κείμενο με αλλαγή γραμμής)
    assert "line 4: 'ίσως'" in msg and "line 5: ''" in msg and "line 2" not in msg


def test_script_exit_codes(tmp_path):
    write(tmp_path / "ok.csv", {("Q1", "a"): ["ναι", "όχι", "όχι"], ("OFF", ""): ["όχι", "όχι", "όχι"]})
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "score_review.py"), str(tmp_path / "ok.csv")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "precision@1=1.00" in r.stdout and "answerable@3=100%" in r.stdout
    write(tmp_path / "bad.csv", {("Q1", "a"): ["ναι", "yes", "όχι"]})
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "score_review.py"), str(tmp_path / "bad.csv")],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "line 3" in r.stderr
