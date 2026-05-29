FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY README.md ./README.md
COPY app ./app

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "app.main"]
