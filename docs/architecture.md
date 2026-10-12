# System architecture

> Status: outline. Fill in alongside `docs/diagrams/system_architecture.png`.

## 1. Overview

## 2. Components

| Component | Responsibility |
|---|---|
| Frontend (Vue 3 PWA) | Capture, in-browser food gate, image preparation, confirmation UI |
| Nginx | TLS termination, 1 MB cap on `/api/meals/photo`, static and game hosting |
| Backend (FastAPI) | API, content safety, orchestration, persistence |
| Rule engine | Deterministic assessment, evaluation and rules -- the source of truth |
| AI pipeline | OliveGemma (vision), Krikri (text), e5 + ChromaDB (RAG) |
| LLM service | llama.cpp serving Krikri 8B Q4_K_M |
| PostgreSQL | Pseudonymised participant, meal, recommendation, game and audit data |

## 3. The photo path

See `docs/diagrams/photo_pipeline.png` and `docs/ephemeral-processing.md`.

## 4. Where the numbers come from

The rule engine computes every number. The LLM only rewords, and
`ai_pipeline/presentation/safety_validator.py` rejects any output whose numbers
differ from the engine's.

## 5. Data sources

Primary food composition: Hellenic Health Foundation (`data/greek_foods.csv`).
USDA FoodData Central (`data/usda_foods.csv`) is a fallback for foods missing
from the Greek table only.
