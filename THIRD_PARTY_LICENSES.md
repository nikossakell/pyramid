# Third-party licences and terms

The MIT licence in `LICENSE` covers only the code written in this repository.
Everything listed below is redistributed or used under its own terms. Model
weights and datasets are **not** committed here; `make models` downloads them
and acceptance of the terms below is a precondition for running the system.

| Component | Role in PYRAMID | Licence / terms | Notes |
|---|---|---|---|
| OliveGemma-3B | Dish recognition from photos | Gemma Terms of Use + Gemma Prohibited Use Policy | Derived from Gemma; use and any redistribution stay bound by the Gemma Terms. Output is treated as a suggestion the child confirms. |
| Llama-Krikri-8B-Instruct (GGUF Q4) | Greek text extraction and presentation | Llama 3.1 Community License | Attribution ("Built with Llama") required; acceptable-use policy applies. |
| multilingual-e5-large | RAG embeddings | MIT | |
| Falconsai/nsfw_image_detection | Server-side content safety | Apache-2.0 | |
| MobileNetV2 (food gate backbone) | In-browser food/non-food gate | Apache-2.0 | Keras/TensorFlow pretrained weights. |
| Food-5K (EPFL) | Food-gate training data | Research use only | Not redistributed; not used commercially. See `ml_data/food5k/`. |
| TensorFlow / TensorFlow.js | Food-gate training and inference | Apache-2.0 | |
| llama.cpp | Krikri inference server | MIT | |
| ChromaDB | RAG vector store | Apache-2.0 | |
| FastAPI, SQLAlchemy, Alembic, Pydantic | Backend | MIT / BSD | |
| Vue 3, Vite, Pinia, Axios | Frontend | MIT | |
| Nginx | Reverse proxy | BSD-2-Clause | |
| PostgreSQL | Database | PostgreSQL Licence | |

## Reference data

| Source | Use | Terms |
|---|---|---|
| EFSA Dietary Reference Values and scientific opinions | `data/efsa_drv.csv`, RAG corpus | EFSA reuse policy; attribution required |
| IOM / NASEM EER equations | `data/iom_eer.csv` | Published equations, cited in the thesis |
| CDC BMI-for-age LMS parameters | `data/cdc_bmi_lms.csv` | US public domain |
| Hellenic Health Foundation food-composition tables | `data/greek_foods.csv` (primary) | Used with attribution; see `docs/architecture.md` |
| USDA FoodData Central | `data/usda_foods.csv` (fallback only) | US public domain |

## Obligations we carry

- Keep the "Built with Llama" notice in any user-facing about page.
- Pass the Gemma Terms and the Gemma Prohibited Use Policy on to anyone we give
  the model files or a derivative to.
- Do not use Food-5K outside research.
- Cite EFSA, IOM, CDC and the Hellenic Health Foundation wherever their values
  are displayed or published.
