# AGENTS.md — Architecture Constraints (Non-Obvious Only)

This file provides guidance to agents when working with code in this repository.

- **Config source is exclusive**: Vault XOR env vars/`.env`. They do not merge — if `USE_VAULT_CONFIG=true`, `Settings()` is built entirely from Vault KV data; the `.env` file is not read at all.
- **Milvus scoping model**: collection = project (e.g. `project_127`), partition = RAG environment (`edi-local`, `edi-dev`, `edi-stage`, `edi-prod`). `clear_collection()` deletes only the current partition, not the whole collection. Changing `RAG_ENVIRONMENT` without migrating vectors leaves orphaned data in other partitions.
- **`InMemoryVectorStore` is stateless per-process**: all vectors are lost on restart. It is the default (`VECTOR_DB_TYPE=memory`). Any test that relies on persisted state across restarts must use a real Milvus.
- **`DocumentEmbeddingService._rag_services` is a process-level in-memory cache** of `RAGService` instances keyed by `index_name`. It is not thread-safe; FastAPI's async single-threaded model keeps it safe but adding true threading would break this.
- **No test suite currently exists** (pendientes.md P-07). The CI pipeline runs `pytest` with `continue-on-error: true`. Before writing tests, note that `asyncio_mode = "auto"` is set and test files must live under `tests/`.
- **Only OpenAI embeddings are supported** (local `sentence-transformers`/`torch` backend was intentionally removed to reduce Docker image size — pendientes.md P-19). Any embedding provider abstraction added must still funnel through OpenAI.
- **Health readiness is NOT binary**: `GET /health/ready` returns 503 only for integrations that are *both* enabled *and* failed. An integration disabled by default (Eureka, Config Server) never triggers a 503, even if it's listed in `READINESS_CRITICAL_DEPENDENCIES`.
- **Dependency chain**: `StorageService` → `DocumentEmbeddingService` → `RAGService` → `EmbeddingProvider` + `VectorStoreManager`. New services that need embedding/storage must go through `DocumentEmbeddingService`, not instantiate their own `RAGService`.
- **`numpy < 2.5.0` pin is a blocker** until Python is upgraded to 3.12 (P-18). Do not bump numpy without the Python upgrade — mypy will break due to PEP 695 type stubs incompatibility.
- **Docker runs non-root** (uid 1000 `appuser`). Directories `logs/` and `.runtime/uploads/` are pre-created and chowned in the Dockerfile. New runtime-writable paths must follow the same pattern.
- **CI pipeline**: Ruff lint → Ruff format → mypy → Bandit → pip-audit → pytest → Docker build + Trivy scan. SonarQube job is disabled (`if: false`) pending internal network connectivity.
