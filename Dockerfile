FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
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

# Ejecutar como usuario no-root (ver README.md "Estandar de calidad..." SS26).
# logs/ y .runtime/ se crean aqui porque el proceso los escribe en runtime
# (logging.configure_logging, StorageConfig.chunk_upload_temp_dir) y el
# usuario no-root necesita permiso de escritura sobre ellos de antemano.
RUN useradd --no-create-home --uid 1000 appuser \
    && mkdir -p logs .runtime/uploads \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "app.main"]
