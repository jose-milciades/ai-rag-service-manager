# AGENTS.md — Coding Rules (Non-Obvious Only)

This file provides guidance to agents when working with code in this repository.

- **Never instantiate `Settings()` directly** — always call `get_settings()` (it's `@lru_cache`; direct construction bypasses caching and will break Vault-sourced config).
- **New services go in `app/api/dependencies/services.py`** as `@lru_cache` functions, then used via `Annotated[..., Depends(...)]` type aliases in controllers.
- **All Pydantic schemas must use `get_camel_case_config()`** from `app/core/schema.py` — not a raw `ConfigDict`. This is the only way to apply the project-wide camelCase alias contract.
- **Loggers**: always `logging.getLogger(__name__)` at module level, never `get_logger()` (that's only for startup orchestration in `app/main.py`).
- **Milvus collection naming**: collection = sanitized project name only (never environment prefix); partition = sanitized `RAG_ENVIRONMENT`. See `_sanitize_collection_name()` in `app/services/rag/rag_service.py`.
- **`VectorStoreManager.delete_records()` requires a non-empty `filter_conditions`** — raises `ValueError` by design; do not call it without a filter.
- **`EmbeddingProvider` must remain a singleton** (shared via `get_embedding_provider()`). Never instantiate it per-request or per-collection.
- **Bandit `# nosec B104`** already annotated on `app_host = "0.0.0.0"` — do not remove it or add a second suppression.
- **Type annotations**: Python 3.11 syntax (`X | Y`, not `Optional[X]`; `list[X]`, not `List[X]`). mypy runs with `disallow_untyped_defs = true` — every function needs a return type.
- **Adding a new optional int `| None` to `Settings`**: add the `_blank_optional_int_as_none` validator pattern (Vault sends `""` for unset values, not `null`).
- **Middleware registration order**: add new middleware after CORS so it runs before CORS on requests. Starlette processes in reverse.
- **No `__init__.py` needed** in new `app/` subpackages — the project uses implicit namespace packages (`explicit_package_bases = true` in mypy config).
