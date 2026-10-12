# CUDA base: OliveGemma and the NSFW detector run on the GPU.
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3-pip python3.11-dev build-essential libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip3 install --no-cache-dir -e ".[dev]"

COPY . .

# Photos exist only in memory: nothing here writes to a volume.
RUN useradd --create-home --uid 10001 pyramid && chown -R pyramid:pyramid /app
USER pyramid

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
