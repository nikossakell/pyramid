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
