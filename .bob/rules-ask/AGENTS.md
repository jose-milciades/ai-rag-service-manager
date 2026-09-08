# AGENTS.md — Documentation Context (Non-Obvious Only)

This file provides guidance to agents when working with code in this repository.

- **`pendientes.md`** (repo root) is the authoritative backlog — all `P-NN` references throughout the code trace here. Read it to understand known limitations, deferred decisions, and intentional design constraints before proposing changes.
- **`app/domain/`** contains empty folders (entities, repositories); domain layer exists architecturally but is not yet populated with actual code. The `__pycache__` stubs are from pre-refactor artifacts.
- **`app/infrastructure/external_clients/`** contains only stale `__pycache__` — the live implementations are in `app/infrastructure/clients/` (note: different directory name).
- **`api.md`** in the repo root is the hand-maintained public API contract (endpoint signatures for the Java micro that calls this service), not auto-generated from OpenAPI.
- **Milvus "partition = environment"** is a non-standard use of Milvus partitions: this project maps business environments (local/dev/stage/prod) to Milvus partitions, not to separate collections or databases.
- **`run-local-vault.sh`** is in `.gitignore` — it contains a real `VAULT_TOKEN`. The example in the repo is a placeholder token only.
- **Spring Cloud Config integration** is startup-only: it queries once and stores metadata in `app.state.remote_config`. It does not inject config into `Settings` — the config source hierarchy is Vault (if `USE_VAULT_CONFIG=true`) or env vars / `.env` file.
- **`integracion-*.md` files** in the repo root document integration contracts with other microservices in the same ecosystem (Java backend, operator service, chat backend).
