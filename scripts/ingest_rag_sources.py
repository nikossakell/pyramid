"""
Βήμα 5.1: χτίσιμο της βάσης γνώσης RAG από τα PDF του data/rag_sources.csv.
(Αντικαθιστά το scripts/ingest_efsa_pdfs.py της Δομής: οι πηγές δεν είναι μόνο EFSA.)

Τρέξτε από τον φάκελο nutriscan/. Τα PDF είναι στο data/efsa_pdfs/ (gitignored). Μπαίνουν ΜΟΝΟ όσα
είναι γραμμένα στο data/rag_sources.csv· τα υπόλοιπα αρχεία του φακέλου αγνοούνται.

    # 1. συμπλήρωση των κενών sha256 στο manifest (μία φορά, μετά ελέγξτε το diff)
    python scripts/ingest_rag_sources.py --update-hashes

    # 2. έλεγχος εξαγωγής κειμένου ΧΩΡΙΣ μοντέλο: σελίδες, ενότητες, δείγματα κομματιών
    python scripts/ingest_rag_sources.py --inspect --allow-draft

    # 3. χτίσιμο σε ChromaDB (κατεβάζει το multilingual-e5-large, ~2,2 GB, μία φορά)
    python scripts/ingest_rag_sources.py --build --allow-draft          # ανάπτυξη
    python scripts/ingest_rag_sources.py --build                        # τελικό: μόνο approved
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.rag.chunking import MAX_WORDS, OVERLAP_WORDS     # noqa: E402
from ai_pipeline.rag.ingest import build_index, prepare           # noqa: E402
from ai_pipeline.rag.sources import fill_missing_hashes           # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--manifest", default=ROOT / "data" / "rag_sources.csv", type=Path)
p.add_argument("--pdf-dir", default=ROOT / "data" / "efsa_pdfs", type=Path)
p.add_argument("--out", default=ROOT / "backend" / "rag_db", type=Path)
p.add_argument("--allow-draft", action="store_true", help="περιλαμβάνει και μη εγκεκριμένες πηγές (μόνο ανάπτυξη)")
p.add_argument("--max-words", type=int, default=MAX_WORDS)
p.add_argument("--overlap-words", type=int, default=OVERLAP_WORDS)
p.add_argument("--device", default=None, help="cpu | cuda | mps (προεπιλογή: αυτόματα)")
p.add_argument("--revision", default=None, help="commit του μοντέλου στο Hugging Face, για πάγωμα")
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--update-hashes", action="store_true")
g.add_argument("--inspect", action="store_true")
g.add_argument("--build", action="store_true")
p.add_argument("--samples", type=int, default=2, help="δείγματα κομματιών ανά πηγή στο --inspect")
args = p.parse_args()

if args.update_hashes:
    changed = fill_missing_hashes(args.manifest, args.pdf_dir)
    print("Συμπληρώθηκαν:", changed or "τίποτα (όλα είχαν sha256 ή λείπουν αρχεία)")
    sys.exit(0)


def ranges(pages):
    out, start, prev = [], None, None
    for p in sorted(pages):
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start)); start = prev = p
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(out)


def print_reports(reports):
    for r in reports:
        n_dropped = sum(len(v) for v in r.dropped.values())
        print(f"\n[{r.source_id}] status={r.status} σελίδες={r.pages} κομμάτια={r.chunks} (κόπηκαν {n_dropped}) "
              f"μέσες λέξεις={r.mean_words} ενότητες={r.sections}")
        for reason, ids in r.dropped.items():
            print(f"  φίλτρο {reason}: {len(ids)} π.χ. {ids[0]} «{r.dropped_samples[reason]}»")
        if r.flagged_pages:
            low = [p for p, f in r.flagged_pages.items() if "low_text" in f]
            bad = [p for p, f in r.flagged_pages.items() if "bad_chars" in f]
            if low:
                print(f"  ! σελίδες με ελάχιστο κείμενο (εικόνα; OCR δεν γίνεται): {low[:20]}{' …' if len(low) > 20 else ''}")
            if bad:
                print(f"  ! σελίδες με αλλοιωμένους χαρακτήρες (γραμματοσειρά PDF): {bad[:20]}")
        if r.auto_excluded:
            print(f"  εξαιρέθηκαν αυτόματα (βιβλιογραφία/παραρτήματα): σελίδες {ranges(r.auto_excluded)}")
        if r.removed_lines:
            print(f"  αφαιρέθηκαν ως κεφαλίδα/υποσέλιδο ({len(r.removed_lines)}): {r.removed_lines[:8]}")
        if r.truncated:
            print(f"  ! {len(r.truncated)} κομμάτια > 512 tokens (θα κοπούν): {r.truncated[:5]} — μειώστε --max-words")


if args.inspect:
    prepared, reports = prepare(args.manifest, args.pdf_dir, args.allow_draft, args.max_words, args.overlap_words)
    print_reports(reports)
    for src, chunks in prepared:
        print(f"\n--- δείγματα {src.source_id} ---")
        step = max(1, len(chunks) // (args.samples + 1))
        for c in chunks[step::step][:args.samples]:
            print(f"{c.chunk_id} | σελ. {c.page_start}-{c.page_end} | ενότητα: {c.section or '-'}\n  {c.text[:400]}…\n")
    sys.exit(0)

from ai_pipeline.rag.embedder import E5Embedder   # noqa: E402  (βαριά εισαγωγή μόνο στο build)

t0 = time.time()
embedder = E5Embedder(revision=args.revision, device=args.device)
index, reports = build_index(args.manifest, args.pdf_dir, embedder, args.out, args.allow_draft,
                             args.max_words, args.overlap_words)
manifest = index.manifest
print_reports(reports)
print(f"\nΑποθηκεύτηκε: {args.out}  ({manifest['n_chunks']} κομμάτια, dim={manifest['dim']}, "
      f"release={manifest['release']}, έκδοση={index.version}, {time.time() - t0:.0f} s)")
(args.out / "ingest_report.json").write_text(
    json.dumps([{k: v for k, v in r.__dict__.items() if k != "dropped_records"} for r in reports],
               ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(f"Κομμάτια που κόπηκαν (audit): {args.out / 'dropped_chunks.jsonl'} ({manifest['n_dropped']})")
