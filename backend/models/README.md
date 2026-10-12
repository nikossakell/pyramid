# Model weights

Everything in this directory is **gitignored**. Populate it with:

```bash
make models      # -> scripts/download_models.py
```

Expected layout:

```
models/
├── olivegemma-3b/                    # dish recognition (Gemma Terms)
├── krikri-8b-instruct-q4_k_m.gguf    # Greek LLM, served by llama.cpp
├── multilingual-e5-large/            # RAG embeddings
├── nsfw_image_detection/             # Falconsai, server-side content safety
└── food_gate.h5                      # MobileNetV2 food/non-food (server re-check)
```

The TF.js conversion of `food_gate.h5` used by the browser lives in
`frontend/public/models/food_gate/` and is produced by
`scripts/convert_food_gate_tfjs.sh`.

Terms of use for each of these: `THIRD_PARTY_LICENSES.md`.
