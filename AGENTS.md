# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Stack
Python 3.11, FastAPI, `uv` as package manager and task runner. No `Makefile` — all commands via `uv run`.

## Commands
```bash
uv sync --extra dev          # install all deps including dev
uv run ruff check .          # lint
uv run ruff format --check . # format check (ruff also formats, not just lint)
uv run mypy                  # type check (config in pyproject.toml, targets app/ only)
uv run bandit -r app/        # security scan
uv run pytest --cov=app --cov-report=term-missing  # all tests
uv run pytest tests/path/to/test_file.py::test_name  # single test
uv run python -m app.main    # run locally (also: bash run-local.sh)
```
> Note: There are currently no tests written (P-07 in pendientes.md). `pytest` exits cleanly on "no tests collected".

## Key Non-Obvious Facts

**Config / Settings**
- `get_settings()` is `@lru_cache` — never construct `Settings()` directly; use `get_settings()`.
- Config source is decided by a single explicit flag: `USE_VAULT_CONFIG=true` → reads from HashiCorp Vault KV v2 (paths: `common,ai-rag-service-manager,storage,llm_apis`). Otherwise falls back to env vars + `.env` file.
- `RAG_ENVIRONMENT` is strictly validated: only `edi-local | edi-dev | edi-stage | edi-prod` accepted — an invalid value hard-fails at startup.
- `RAG_EMBEDDING_PROVIDER` is always `openai` (only supported value); the local `sentence-transformers` backend was completely removed.

**Milvus / Vector Store**
- Milvus collection name = project name only (e.g. `project_127`), **not** prefixed with environment.
- Milvus partition name = `RAG_ENVIRONMENT` value (e.g. `edi_dev`), used to isolate environments within the same collection.
- Collection names are sanitized: any non-ASCII-word char (`\W`) → `_`; names starting with a digit get a `_` prefix. This matters — `project-42` is valid in-memory but invalid in Milvus.
- `VECTOR_DB_TYPE=memory` (default) uses `InMemoryVectorStore` (data lost on restart). Set to `milvus` for the real backend.
- `VectorStoreManager.delete_records()` requires a non-empty `filter_conditions` — passing an empty dict raises `ValueError` by design.

**Dependency Injection**
- All service singletons live in [`app/api/dependencies/services.py`](app/api/dependencies/services.py) as `@lru_cache` functions. Services are never instantiated directly in controllers.
- `EmbeddingProvider` must be a singleton (loading the model/client is expensive). It is shared across all `RAGService` instances.
- `RAGService` instances are keyed by `index_name` inside `DocumentEmbeddingService._rag_services` dict, not by FastAPI's DI.

**Pydantic Schemas**
- All request/response schemas use `get_camel_case_config()` from [`app/core/schema.py`](app/core/schema.py), which applies `alias_generator=to_camel` and `populate_by_name=True`. JSON in/out is camelCase; Python attributes are snake_case.
- `rag_openai_embedding_dimensions` has a custom validator that coerces `""` → `None` (Vault sends empty string for unset optional ints).

**Logging**
- Always obtain loggers via `logging.getLogger(__name__)` — never `get_logger()` directly in module bodies (that function is for startup code in `main.py`/`logging.py`).
- HTTP client loggers (`httpx`, `httpcore`, `urllib3`, `openai`, `google.auth`) are **always DEBUG** regardless of `APP_LOG_LEVEL`, to capture full request/response details without enabling global debug mode.
- Logs go to both console (colorized) and rotating file `logs/app.log` (5 MB × 5 backups).

**Middleware order matters**
- Starlette executes middlewares in **reverse registration order**. `CorrelationIdMiddleware` is registered after CORS so it runs first on requests (sets correlation ID before any log) and last on responses (adds the header back).

**Testing**
- `asyncio_mode = "auto"` in `pyproject.toml` — all async tests run without explicit `@pytest.mark.asyncio`.
- Test files must be placed under `tests/` (the only configured `testpath`).
- `numpy` is pinned below `2.5.0` for Python 3.11 mypy compatibility (PEP 695 type stubs issue); do not upgrade until Python is upgraded to 3.12 (pendientes.md P-18).

**Ruff**
- `line-length = 100`, `target-version = "py311"`.
- FastAPI `File(...)`, `Form(...)`, `Query(...)`, `Body(...)`, `Header(...)`, `Cookie(...)`, `Path(...)`, `Depends(...)` are declared `extend-immutable-calls` — Ruff rule B008 does not flag them.
- `.md` files are excluded from format checks.

**mypy**
- `explicit_package_bases = true` — needed because most `app/` subpackages have no `__init__.py` (namespace packages).
- Runs only over `app/` (not `tests/`). `check_untyped_defs` and `disallow_untyped_defs` are both enabled.
- `hvac`, `py_eureka_client`, `google.cloud`, `google.oauth2`, `pymilvus` have `ignore_missing_imports = true` (no type stubs).

**Infrastructure integrations (all optional by default)**
- Eureka: `EUREKA_ENABLED=false` by default. Registration is retried up to `EUREKA_REGISTER_MAX_RETRIES` times.
- Spring Config Server: `USE_SPRING_CLOUD_CONFIG=false` by default. Queried once at startup only; failures are logged as warnings and do not block startup.
- Readiness probe (`GET /api/v1/health/ready`) returns 503 only for integrations listed in `READINESS_CRITICAL_DEPENDENCIES` that are **both enabled and failed**. Disabled integrations never count as failures.

**Storage**
- `StorageClient` includes SSRF protection: download URLs must resolve to a public IP (non-private, non-loopback, non-link-local). Any private-IP hostname is rejected.
- Chunked uploads use `.runtime/uploads/` as temp dir (created at Docker build time with correct permissions).
- `GOOGLE_CREDS_JSON` must contain the full service account JSON on a single line.
