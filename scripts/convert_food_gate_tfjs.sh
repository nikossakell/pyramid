#!/usr/bin/env bash
# Convert the trained Keras food gate to TF.js with 8-bit weight quantisation,
# into the directory the PWA serves it from.
set -euo pipefail

SRC="${1:-backend/models/food_gate.h5}"
DEST="${2:-frontend/public/models/food_gate}"

[[ -f "$SRC" ]] || { echo "missing $SRC -- run scripts/train_food_gate.py first" >&2; exit 1; }

mkdir -p "$DEST"
tensorflowjs_converter \
    --input_format=keras \
    --quantize_uint8 \
    "$SRC" "$DEST"

echo "converted -> $DEST"
ls -la "$DEST"
