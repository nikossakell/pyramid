# PYRAMID

**P**rivacy-preserving **Y**outh-oriented **R**eward-based **AI** **M**onitoring of **I**ntake and **D**iet

An AI-assisted, gamified dietary logging web application for children and adolescents (10–16) attending sports academies. Developed as part of an MSc thesis (University of Macedonia, in collaboration with the Aristotle University of Thessaloniki) and evaluated in a 12-week pilot randomised controlled trial.

> ⚠️ Research prototype under active development. Educational and research use only. It does not provide medical diagnosis, therapeutic diets or weight-loss advice.

## What it does

- **Meal logging** by photo, manual entry or free Greek text.
- **On-device food recognition and portion estimation.** Photos never leave the device and are deleted immediately; the child confirms or corrects the result.
- **Nutrition engine.** Deterministic matching against a food-composition database and nutrient arithmetic, with no AI involved.
- **Educational AI chat.** A Greek-capable language model answers only from expert-approved sources (Greek national dietary guidelines, EFSA, WHO), and its output is validated before display.
- **Card game against the computer** that rewards regular logging, with no leaderboards.
- **Safety layer.** Risk detection on input and output, pre-approved crisis messages and alerts to an on-call researcher.

## Design principles

- **The AI explains; it is never the source of truth.** Databases hold the facts, code does the maths, and validation has the final say.
- **On-premise only.** All processing runs on university infrastructure, with no third-party services.
- **Pseudonymised.** Servers know participants only by code.
- **Non-stigmatising.** Children receive food-group feedback, never calories, nutrient targets or BMI.

## Stack (subject to change)

PWA + ONNX Runtime Web · FastAPI · PostgreSQL + pgvector · Llama-Krikri-8B-Instruct · Nginx

## Status

🚧 Pre-alpha. Architecture v0.4.

## Repository layout

```
├── docs/            Architecture, API, deployment, GDPR/DPIA, ephemeral processing, content safety
├── data/            Reference data, version-controlled (EFSA, IOM, CDC, food composition)
├── backend/         FastAPI app, deterministic rule_engine, ai_pipeline, tests
├── frontend/        Vue 3 PWA, incl. the in-browser food gate (src/ml/)
├── game/            Unity card game (project + WebGL build)
├── nginx/           Reverse proxy; enforces the 1 MB photo limit
├── scripts/         Data loading, model download, RAG ingestion, Rule 7 verification
├── ml_data/         Training datasets (gitignored, non-personal only)
├── notebooks/       Research notebooks
├── pilot_study/     Protocol, ethics, consent, questionnaires, results
├── thesis/          LaTeX thesis
└── paper/           Journal manuscript
```

Three directories are deliberately absent from version control and are produced
on the machine that runs the system: `backend/models/` (weights, `make models`),
`backend/rag_db/` (vector store, `make rag`) and `ml_data/`.

## Setup

Requirements: Docker with the NVIDIA container toolkit, a GPU, Node 22 for
frontend work, and **swap disabled on the host** — the last one is a
precondition for the ephemeral-photo guarantee.

```bash
cp .env.example .env          # fill in every secret
make models                   # download model weights (see THIRD_PARTY_LICENSES.md)
make up && make migrate && make seed
make rag                      # after placing the EFSA PDFs in data/efsa_pdfs/
make dev
```

Frontend dev server: `make frontend` (proxies `/api` to the backend).

```bash
make test                     # backend suite
make check-ephemeral          # must pass before any participant is enrolled
make deploy                   # production stack (docker-compose.prod.yml)
```

`make help` lists every target.

## Licence

Our code is MIT (`LICENSE`). The models, datasets and libraries we build on
carry their own terms — see `THIRD_PARTY_LICENSES.md`, which also lists the
obligations we have to honour.
