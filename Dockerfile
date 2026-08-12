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

# Pre-descarga el modelo local de embeddings (backend "local" de
# EmbeddingProvider, ver pendientes.md P-27) en tiempo de build, por si se
# usa RAG_EMBEDDING_PROVIDER=local, para que ese arranque no dependa de red
# ni pague el costo de descarga en el primer request. El default de runtime
# hoy es RAG_EMBEDDING_PROVIDER=openai (API remota, sin descarga ni modelo
# local involucrado) -- este paso no afecta ese camino.
RUN uv run python -c "\
from pymilvus.model.dense import SentenceTransformerEmbeddingFunction; \
SentenceTransformerEmbeddingFunction(model_name='sentence-transformers/all-MiniLM-L6-v2', device='cpu')"

# A partir de aqui el modelo local ya esta en HF_HOME: se fuerza modo offline
# para que, si se usa el backend "local", el arranque no intente verificar
# archivos contra Hugging Face Hub (sin esto, cada arranque hace varios HEAD
# request con reintentos/backoff antes de caer al cache local, incluso si el
# cache ya tiene todo lo necesario). Sin efecto sobre el backend "openai".
# Si se cambia RAG_EMBEDDING_MODEL (con provider=local) a un modelo no
# horneado en la imagen, hay que quitar esta variable (o reconstruir la
# imagen) para permitir la descarga real en runtime.
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
