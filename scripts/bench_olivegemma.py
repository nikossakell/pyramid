#!/usr/bin/env python3
"""
scripts/bench_olivegemma.py — τρέχει το τοπικό OliveGemma-3B σε έναν φάκελο εικόνων και γράφει CSV:
    image, top1, top2, top3, food_id, confidence, seconds, max_rss_mb[, colab_top1, same_top1]

Σκοπός: ΜΟΝΟ λειτουργική ενσωμάτωση και ταύτιση CPU ↔ Colab (ίδιο top-1 με τη δοκιμή της 19/10 σε T4 GPU), όχι
μέτρηση ακρίβειας. Οι εικόνες διαβάζονται από όπου είναι (π.χ. ~/Desktop/msc/thesis/Phase3/demo_photos/) και ΔΕΝ
αντιγράφονται· κάθε εικόνα περνά από το ίδιο prepare() του pipeline (≤ 448 px, νέο JPEG χωρίς EXIF) και μένει στη RAM.
Οι παράμετροι beam είναι από την κάρτα του μοντέλου (num_beams = num_return_sequences = top-k, greedy, 64 tokens).

Πριν τη φόρτωση τυπώνει τη διαθέσιμη μνήμη (MemAvailable) και σταματά αν είναι κάτω από --min-available-gib (7).

    ./venv/bin/python scripts/bench_olivegemma.py --images ~/Desktop/msc/thesis/Phase3/demo_photos \
        --results ~/Desktop/msc/thesis/Phase3/demo_photos/olivegemma_results.csv --out /tmp/bench.csv
"""
import argparse
import csv
import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from ai_pipeline.vision.olivegemma import (OliveGemmaRecognizer, TorchBackend, load_label_map,  # noqa: E402
                                           normalize_label, rss_mb)
from app.services.food_catalog import load_catalog  # noqa: E402
from app.services.photo_pipeline import PhotoPipeline  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def mem_available_gib() -> float:
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / (1024 ** 2)
    return float("nan")


def to_jpeg(path: Path, max_edge: int) -> bytes:
    """Όπως ο browser: σμίκρυνση ώστε η μεγαλύτερη πλευρά ≤ max_edge, JPEG χωρίς μεταδεδομένα, στη RAM."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90)
        return out.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, required=True, help="φάκελος με jpg/jpeg/png (διαβάζονται επί τόπου)")
    ap.add_argument("--out", type=Path, required=True, help="CSV αποτελεσμάτων")
    ap.add_argument("--results", type=Path, help="olivegemma_results.csv της δοκιμής 19/10 (στήλες filename, pred_top1)")
    ap.add_argument("--model-dir", type=Path, default=ROOT / "models" / "olivegemma-3b")
    ap.add_argument("--dtype", choices=["bfloat16", "float32"], default="bfloat16")
    ap.add_argument("--threads", type=int)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, help="μόνο οι πρώτες N εικόνες (αλφαβητικά)")
    ap.add_argument("--min-available-gib", type=float, default=7.0)
    ap.add_argument("--force", action="store_true", help="συνέχισε και με λιγότερη διαθέσιμη μνήμη")
    args = ap.parse_args()

    avail = mem_available_gib()
    print(f"MemAvailable: {avail:.1f} GiB (όριο {args.min_available_gib} GiB)")
    if avail < args.min_available_gib and not args.force:
        print("ΣΤΟΠ: λίγη διαθέσιμη μνήμη. Κλείσε εφαρμογές ή δώσε --force.", file=sys.stderr)
        return 2

    images = sorted(p for p in args.images.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)[: args.limit or None]
    if not images:
        print(f"καμία εικόνα στο {args.images}", file=sys.stderr)
        return 2

    colab: dict[str, str] = {}
    if args.results:
        with args.results.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                colab[Path(row["filename"]).stem.lower()] = normalize_label(row.get("pred_top1") or "")

    catalog = load_catalog(ROOT / "data/demo_foods.csv", ROOT / "data/demo_food_aliases.csv",
                           ROOT / "data/efsa_drv.csv", ROOT / "data/food_groups.csv",
                           ROOT / "data/display_food_groups.csv")
    label_map = load_label_map(ROOT / "data/olivegemma_label_map.csv", catalog.foods)
    rec = OliveGemmaRecognizer(args.model_dir, label_map, catalog.foods, dtype=args.dtype, threads=args.threads,
                               topk=args.topk, timeout_s=1e9,
                               backend_factory=lambda: TorchBackend(args.model_dir, args.dtype, args.threads))
    pipeline = PhotoPipeline(None, None, rec, 1_048_576, 448)

    t0 = time.monotonic()
    rec.load()
    print(f"φόρτωση: {time.monotonic() - t0:.0f} s, max RSS {rss_mb()} MB, dtype {args.dtype}, "
          f"threads {args.threads or 'default'}, top-k {args.topk}")

    rows, same, compared = [], 0, 0
    for path in images:
        jpeg = pipeline.prepare(to_jpeg(path, 448))
        t0 = time.monotonic()
        labels = rec._backend.answer(Image.open(io.BytesIO(jpeg)).convert("RGB"), "What is the name of this dish?",
                                     args.topk)
        seconds = time.monotonic() - t0
        found = rec.assemble(labels)
        resolved = catalog.resolver.resolve(found.name_el) if found.name_el else None
        row = {"image": path.name, **{f"top{i + 1}": normalize_label(labels[i]) if i < len(labels) else ""
                                     for i in range(args.topk)},
               "food_id": resolved.food_id if resolved else "", "confidence": "sure" if found.confidence else "maybe",
               "seconds": f"{seconds:.1f}", "max_rss_mb": rss_mb()}
        if colab:
            c = colab.get(path.stem.lower(), "")
            row["colab_top1"] = c
            row["same_top1"] = "" if not c else ("yes" if c == row["top1"] else "no")
            if c:
                compared += 1
                same += row["same_top1"] == "yes"
        rows.append(row)
        print(f"{path.name}: {row['top1']!r} | {row['top2']!r} | {row['top3']!r} -> food_id={row['food_id'] or '-'} "
              f"({row['confidence']}) {seconds:.1f} s, RSS {row['max_rss_mb']} MB"
              + (f", Colab {c!r} same={row['same_top1']}" if colab else ""))
        del jpeg

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    secs = [float(r["seconds"]) for r in rows]
    print(f"\n{len(rows)} εικόνες · μέσος χρόνος {sum(secs) / len(secs):.1f} s · max RSS {rss_mb()} MB · CSV: {args.out}")
    if compared:
        print(f"ίδιο top-1 με Colab: {same}/{compared}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
