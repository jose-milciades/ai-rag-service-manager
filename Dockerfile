FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    UV_CACHE_DIR=/app/.cache/uv \
    HOME=/app

# Aplica parches de seguridad del SO disponibles en el momento del build
# (ver README.md "Estandar de calidad..." SS27, pendientes.md P-18/Trivy).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/app/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY README.md ./README.md
COPY app ./app

# Pre-descarga el modelo de embeddings (EmbeddingProvider) en tiempo de
# build para que el arranque del contenedor no dependa de red y no pague el
# costo de descarga en el primer request. Si RAG_EMBEDDING_MODEL se
# sobreescribe en runtime con un modelo distinto al default, el arranque
# hara la descarga real en ese momento (requiere salida a internet).
RUN uv run python -c "\
from pymilvus.model.dense import SentenceTransformerEmbeddingFunction; \
SentenceTransformerEmbeddingFunction(model_name='sentence-transformers/all-MiniLM-L6-v2', device='cpu')"

# A partir de aqui el modelo ya esta en HF_HOME: se fuerza modo offline para
# que el arranque no intente verificar archivos contra Hugging Face Hub (sin
# esto, cada arranque hace varios HEAD request con reintentos/backoff antes
# de caer al cache local, incluso si el cache ya tiene todo lo necesario).
# Si se cambia RAG_EMBEDDING_MODEL a un modelo no horneado en la imagen, hay
# que quitar esta variable (o reconstruir la imagen) para permitir la
# descarga real en runtime.
ENV HF_HUB_OFFLINE=1

# Ejecutar como usuario no-root (ver README.md "Estandar de calidad..." SS26).
# logs/ y .runtime/ se crean aqui porque el proceso los escribe en runtime
# (logging.configure_logging, StorageConfig.chunk_upload_temp_dir) y el
# usuario no-root necesita permiso de escritura sobre ellos de antemano.
# El cache de HF_HOME queda dentro de /app, asi que el chown lo cubre.
RUN useradd --no-create-home --uid 1000 appuser \
    && mkdir -p logs .runtime/uploads \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "app.main"]
