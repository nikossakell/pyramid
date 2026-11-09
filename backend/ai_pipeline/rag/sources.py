"""
ai_pipeline/rag/sources.py — ποια έγγραφα επιτρέπεται να μπουν στη βάση γνώσης.

Μόνο όσα είναι γραμμένα στο data/rag_sources.csv. Για καθένα:
- sha256: το αρχείο πρέπει να είναι ΑΚΡΙΒΩΣ αυτό που εγκρίθηκε (αλλιώς σφάλμα),
- status: "approved" (υπογεγραμμένο από διαιτολόγο/παιδίατρο), "draft" (μόνο για ανάπτυξη) ή "excluded"
  (δεν μπαίνει ποτέ, π.χ. όσο εκκρεμεί άδεια χρήσης),
- pages: ποιες σελίδες μπαίνουν (π.χ. χωρίς βιβλιογραφία και παραρτήματα),
- check_text (προαιρετικό): κείμενο που ΠΡΕΠΕΙ να υπάρχει στις 3 πρώτες σελίδες (π.χ. το DOI), ώστε να
  επιβεβαιώνεται αυτόματα ότι το αρχείο είναι πράγματι το έγγραφο της γραμμής. Εναλλακτικές με «|».

ΑΠΟΚΛΙΣΗ ΑΠΟ ΤΟ final_plan: εκεί το "approved_by": "research_team" είναι γραμμένο σταθερά στον κώδικα
για κάθε κομμάτι. Εδώ η έγκριση είναι δεδομένο ανά έγγραφο, και η Αρχιτεκτονική v0.4 ορίζει ότι τη βάση
γνώσης την εγκρίνουν διαιτολόγος και παιδίατρος.
"""
import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REQUIRED_COLUMNS = {"source_id", "file", "title", "organization", "year", "version", "language",
                    "url", "licence", "sha256", "pages", "status", "approved_by", "approved_date"}
# approved: εγκεκριμένο· draft: μόνο για ανάπτυξη (--allow-draft)· excluded: ΠΟΤΕ, ούτε στην ανάπτυξη
# (π.χ. εκκρεμεί άδεια χρήσης, όπως ο Εθνικός Διατροφικός Οδηγός)
STATUSES = {"approved", "draft", "excluded"}
_ID = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Source:
    source_id: str
    file: str
    title: str
    organization: str
    year: str
    version: str
    language: str
    url: str
    licence: str
    sha256: str
    pages: str            # "" = όλες, αλλιώς π.χ. "5-120" ή "3-10,12,15-20" (αρίθμηση από 1)
    status: str
    approved_by: str
    approved_date: str
    check_text: str = ""

    @property
    def approved(self) -> bool:
        return self.status == "approved"

    def page_numbers(self, n_pages: int) -> list[int]:
        """Σελίδες προς επεξεργασία, αρίθμηση από 1."""
        return parse_pages(self.pages, n_pages)


def parse_pages(spec: str, n_pages: int) -> list[int]:
    if not spec.strip():
        return list(range(1, n_pages + 1))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ValueError(f"bad page spec '{part}'")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if a < 1 or b < a or b > n_pages:
            raise ValueError(f"page range '{part}' outside 1-{n_pages}")
        out.update(range(a, b + 1))
    return sorted(out)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_sources(manifest: Path) -> list[Source]:
    with Path(manifest).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{Path(manifest).name}: missing columns {sorted(missing)}")
        sources, seen = [], set()
        for line, row in enumerate(reader, start=2):
            r = {k: (row.get(k) or "").strip() for k in REQUIRED_COLUMNS}
            where = f"{Path(manifest).name}, line {line}"
            for col in ("source_id", "file", "title", "version", "language", "status"):
                if not r[col]:
                    raise ValueError(f"{where}: empty '{col}'")
            if not _ID.match(r["source_id"]):
                raise ValueError(f"{where}: source_id must be [a-z0-9_]")
            if r["source_id"] in seen:
                raise ValueError(f"{where}: duplicate source_id '{r['source_id']}'")
            if r["status"] not in STATUSES:
                raise ValueError(f"{where}: status must be one of {sorted(STATUSES)}")
            if r["status"] == "approved" and not (r["approved_by"] and r["approved_date"] and r["sha256"]):
                raise ValueError(f"{where}: approved source needs approved_by, approved_date and sha256")
            seen.add(r["source_id"])
            sources.append(Source(**r, check_text=(row.get("check_text") or "").strip()))
        return sources


def select_sources(sources: list[Source], pdf_dir: Path, allow_draft: bool = False) -> list[tuple[Source, Path]]:
    """Επιστρέφει (πηγή, διαδρομή) για όσα θα μπουν. Σφάλμα αν λείπει αρχείο ή δεν ταιριάζει το hash.
    Τα draft μπαίνουν μόνο με allow_draft=True (και τότε το ευρετήριο σημειώνεται ως μη τελικό)."""
    chosen = []
    for s in sources:
        if s.status == "excluded" or (not s.approved and not allow_draft):
            continue
        path = resolve_file(Path(pdf_dir), s.file)
        if not s.sha256:
            raise ValueError(f"{s.source_id}: empty sha256 (run the ingest script with --update-hashes)")
        actual = sha256_file(path)
        if actual != s.sha256.lower():
            raise ValueError(f"{s.source_id}: sha256 mismatch: manifest {s.sha256[:12]}…, file {actual[:12]}…")
        chosen.append((s, path))
    return chosen


def _loose(name: str) -> str:
    return " ".join(name.lower().split())


def resolve_file(pdf_dir: Path, name: str) -> Path:
    """Ακριβές όνομα, αλλιώς ένα μοναδικό αρχείο με ίδιο όνομα αγνοώντας κεφαλαία και πολλαπλά κενά
    (π.χ. «2010 -  - Scientific»). Η ταυτότητα εξασφαλίζεται ούτως ή άλλως από το sha256."""
    exact = pdf_dir / name
    if exact.is_file():
        return exact
    matches = [p for p in pdf_dir.glob("*") if p.is_file() and _loose(p.name) == _loose(name)]
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"file not found in {pdf_dir}: '{name}'" + (" (ambiguous)" if matches else ""))


def fill_missing_hashes(manifest: Path, pdf_dir: Path) -> list[str]:
    """Συμπληρώνει ΜΟΝΟ κενά sha256 (ποτέ δεν αντικαθιστά υπάρχον). Επιστρέφει τα source_id που άλλαξαν."""
    manifest = Path(manifest)
    with manifest.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    changed = []
    for row in rows:
        if row["sha256"].strip():
            continue
        try:
            path = resolve_file(Path(pdf_dir), row["file"].strip())
        except FileNotFoundError:
            continue
        row["sha256"] = sha256_file(path)
        changed.append(row["source_id"])
    if changed:
        with manifest.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def find_source(sources: list[Source], source_id: str) -> Optional[Source]:
    return next((s for s in sources if s.source_id == source_id), None)
