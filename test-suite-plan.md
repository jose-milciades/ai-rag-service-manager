# Test Suite Plan — ai-rag-service-manager

## Overview

Create a complete unit test suite for `ai-rag-service-manager` from scratch, covering all
executable Python modules under `app/`. The user requested the test folder be named `test`
(not `tests`), so we will use `test/` and update `pyproject.toml` accordingly.

All tests must pass Ruff lint and mypy checks without modifications to production code.
No new test-only packages will be added — only `pytest`, `pytest-asyncio`, `pytest-cov`,
and stdlib `unittest.mock` (already declared as dev dependencies).

### Critical constraints discovered during analysis

- `get_settings()` is `@lru_cache` — MUST be cleared between tests via
  `get_settings.cache_clear()` or test isolation.
- Same for all `@lru_cache` functions in `app/api/dependencies/services.py`.
- The `lifespan` context manager (`app/main.py`) contacts ConfigServer and Eureka on startup —
  TestClient must mock these or disable them via settings flags.
- `RAG_ENVIRONMENT` is strictly validated (only 4 allowed values); test settings must use
  a valid value.
- `RAG_EMBEDDING_PROVIDER` must be `"openai"` always.
- `VectorStoreManager.delete_records()` raises `ValueError` on empty `filter_conditions` —
  this is intentional and must be tested.
- mypy targets only `app/` (`files = ["app"]`) — test files are NOT type-checked by default.
  We should still write typed code but do not need to configure mypy overrides for tests.
- `asyncio_mode = "auto"` means no `@pytest.mark.asyncio` needed (but it is harmless if added).
- `GOOGLE_CREDS_JSON` must be valid JSON or `None/""` — empty string is treated as "no creds".
- Milvus collection names: any non-ASCII-word char is replaced by `_`; digit-leading names get
  a `_` prefix.
- Storage blob name for download in expand_context is `unique_code`, NOT `file_name`.

---

## Folder structure

```
test/                                # All tests here (user requirement: "test" not "tests")
├── conftest.py                      # Shared fixtures, mock settings, app clients
├── unit/
│   ├── core/
│   │   ├── test_config.py           # Settings, validators, get_settings(), vault flags
│   │   ├── test_vault.py            # VaultClient, is_vault_configured, _is_truthy
│   │   ├── test_logging.py          # CorrelationIdFilter, configure_logging, get_logger
│   │   ├── test_middleware.py       # CorrelationIdMiddleware.dispatch
│   │   ├── test_schema.py           # to_camel, get_camel_case_config
│   │   └── test_utils.py            # generate_unique_code, serialize_for_json, now_mx
│   ├── api/
│   │   ├── test_health_controller.py    # GET /health/live, /health/ready branches
│   │   ├── test_embedding_controller.py # All 7 POST /embedding/* endpoints
│   │   └── test_storage_controller.py   # upload, chunk, get, getFileByte, public-upload
│   ├── services/
│   │   ├── test_rag_service.py              # RAGService: chunking, search, sanitize, etc.
│   │   ├── test_document_embedding_service.py # DocumentEmbeddingService: all methods
│   │   └── test_storage_service.py          # StorageService: upload, chunk, get, vectorize
│   └── infrastructure/
│       ├── test_vector_store_manager.py  # InMemoryVectorStore + VectorStoreManager
│       ├── test_milvus_vector_store.py   # MilvusVectorStore with mocked pymilvus
│       ├── test_embedding_provider.py    # EmbeddingProvider with mocked openai
│       ├── test_storage_client.py        # StorageClient + _ensure_public_http_url
│       ├── test_storage_config.py        # StorageConfig parsing and validation
│       ├── test_config_server.py         # ConfigServerClient.fetch_config async branches
│       └── test_eureka.py               # EurekaRegistrar.register/stop async
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project scaffolding and conftest.py

**Status**: `[ ] pending`

**Intent**

Set up the `test/` directory, create `conftest.py` with all shared fixtures, and update
`pyproject.toml` so pytest discovers tests under `test/` instead of `tests/`. This subtask
is the foundation — all other subtasks depend on it.

**Expected Outcomes**

- `test/` directory exists with `conftest.py` and `test/unit/` hierarchy (empty `__init__.py`
  files where needed).
- `pyproject.toml` `testpaths` changed from `["tests"]` to `["test"]`.
- `pytest --collect-only` runs without errors (0 items collected, no import failures).
- Fixtures defined in `conftest.py`: `mock_settings`, `test_app`, `test_client`,
  `mock_embedding_provider`, `mock_vector_store_manager`, `mock_storage_client`,
  `mock_storage_service`, `mock_document_embedding_service`.

**Todo List**

1. Update `pyproject.toml`: change `testpaths = ["tests"]` → `testpaths = ["test"]`.
   Also add `[tool.coverage.run] source = ["app"] omit = ["test/*"]` section to ensure
   coverage only measures `app/` code.
2. Create `test/__init__.py` (empty).
3. Create all `test/unit/**/__init__.py` files (empty) for proper Python package structure.
4. Create `test/conftest.py` with:
   - `mock_settings` fixture: a real `Settings()` instance constructed with safe test values
     (rag_environment="edi-local", openai_api_key="sk-test", vector_db_type="memory", all
     external integrations disabled: eureka_enabled=False, use_spring_cloud_config=False,
     use_vault_config not set). **Use `monkeypatch.setenv` + `Settings()` construction** to
     avoid lru_cache contamination, then call `get_settings.cache_clear()` in teardown.
   - `test_app(mock_settings)` fixture: use `unittest.mock.patch` to replace
     `get_settings` return value and mock both `ConfigServerClient.fetch_config` (AsyncMock
     returning `{"enabled": False, "loaded": False}`) and `EurekaRegistrar.register`
     (AsyncMock returning `{"enabled": False, "registered": False}`) and
     `StorageClient.startup_event` (Mock, no-op). Then call `create_app()`.
     Use `app.dependency_overrides` to inject all lru_cache-wrapped singletons.
   - `test_client(test_app)` fixture: `TestClient(test_app)`.
   - `mock_embedding_provider` fixture: `Mock()` with `dim=1536`,
     `model_name="text-embedding-3-small"`, `embed_documents.return_value=[[0.1]*1536]`,
     `embed_query.return_value=[0.1]*1536`.
   - `mock_vector_store_manager` fixture: `Mock(spec=VectorStoreManager)`.
   - `mock_storage_client` fixture: `Mock(spec=StorageClient)`.
   - `mock_storage_service(test_app)` fixture: override `get_storage_service` dependency.
   - `mock_document_embedding_service(test_app)` fixture: override `get_document_embedding_service`.
5. Run `uv run pytest --collect-only` to verify zero errors.

**Relevant Context**

- `app/main.py`: `create_app()`, `lifespan`, `app.dependency_overrides`
- `app/api/dependencies/services.py`: all `@lru_cache` dependency functions
- `app/core/config.py`: `get_settings()` is `@lru_cache`
- `pyproject.toml`: `[tool.pytest.ini_options]`

---

### Sub-Task 2 — Core utilities tests

**Status**: `[ ] pending`

**Intent**

Test all modules in `app/core/` that contain pure logic: config validators, vault helpers,
logging filter, middleware, schema utilities, and utils. These are mostly sync, unit-testable
without FastAPI.

**Expected Outcomes**

- 6 test files created under `test/unit/core/`.
- All branches in each module covered.
- `ruff check test/unit/core/` passes.
- Tests pass with `uv run pytest test/unit/core/ -v`.

**Todo List**

For `test_config.py`:
1. Test `Settings._blank_optional_int_as_none`: value="" → None; value="256" → 256.
2. Test `Settings._validate_rag_environment`: valid values pass; invalid raises ValueError.
3. Test `Settings._validate_rag_embedding_provider`: "openai" passes; "local" raises.
4. Test `_vault_config_paths()`: default CSV parsing; custom VAULT_CONFIG_PATHS env var.
5. Test `get_settings()` lru_cache: same instance returned on multiple calls.
6. Test `get_settings()` without Vault: reads from env/defaults.
7. Test `Settings` field aliases: AliasChoices (e.g. EUREKA_SERVER_URL vs EUREKA_SERVER).

For `test_vault.py`:
1. Test `_is_truthy()` with: "1", "true", "TRUE", "yes", "on", "off", "false", None, "".
2. Test `is_vault_configured()` with/without `USE_VAULT_CONFIG` env var (monkeypatch).
3. Test `VaultClient.__init__()`: missing VAULT_ADDR → ValueError listing it.
4. Test `VaultClient.__init__()`: missing VAULT_TOKEN → ValueError listing it.
5. Test `VaultClient.__init__()`: both missing → ValueError listing both.
6. Test `VaultClient.__init__()`: hvac connection failure → ValueError with hint.
7. Test `VaultClient.__init__()`: not authenticated → ValueError with token hint.
8. Test `VaultClient.get_secret()`: correct extraction from hvac response dict structure.
9. Test `VaultClient.load_configs()`: multiple paths merged (later overrides earlier).
10. Test VAULT_SKIP_VERIFY=true calls `urllib3.disable_warnings`.

For `test_logging.py`:
1. Test `CorrelationIdFilter.filter()`: sets `record.correlation_id` from ContextVar.
2. Test `CorrelationIdFilter.filter()`: default "-" when no correlation_id in context.
3. Test `configure_logging()`: creates `logs/` directory.
4. Test `configure_logging()`: does not raise on repeated calls.
5. Test `get_logger()`: returns Logger with correct name.

For `test_middleware.py`:
1. Test dispatch: `X-Correlation-ID` from request → same value in response header.
2. Test dispatch: no header → generates UUID, adds to response.
3. Test dispatch: ContextVar set during request, reset after.
4. Test dispatch: `request.state.correlation_id` set correctly.
5. Test dispatch: token reset even if `call_next` raises (use mock raising exception).

For `test_schema.py`:
1. Test `to_camel()`: "file_name" → "fileName"; "id" → "id"; "text_preview" → "textPreview".
2. Test `get_camel_case_config()`: returns ConfigDict with alias_generator, populate_by_name.
3. Test that a Pydantic model using the config serializes with camelCase aliases.

For `test_utils.py`:
1. Test `generate_unique_code()`: returns a non-empty string; two calls return different values.
2. Test `generate_unique_code()`: format check (hex chars, length ≥ some minimum).
3. Test `serialize_for_json()` with datetime → isoformat string.
4. Test `serialize_for_json()` with nested dict containing datetime.
5. Test `serialize_for_json()` with list of datetimes.
6. Test `serialize_for_json()` with plain str/int → unchanged.
7. Test `now_mx()`: returns timezone-aware datetime; default "America/Mexico_City".
8. Test `now_mx()` with TIMEZONE env var override (use monkeypatch).

**Relevant Context**

- `app/core/config.py`, `app/core/vault.py`, `app/core/logging.py`
- `app/core/middleware.py`, `app/core/schema.py`, `app/core/utils.py`

---

### Sub-Task 3 — Infrastructure layer tests

**Status**: `[ ] pending`

**Intent**

Test all infrastructure adapters (vector stores, embedding provider, storage client,
config server, eureka) using mocks for external systems (pymilvus, openai, GCS, httpx).

**Expected Outcomes**

- 7 test files created under `test/unit/infrastructure/`.
- All adapters tested with mocked external dependencies.
- SSRF validation fully covered.
- `ruff check test/unit/infrastructure/` passes.

**Todo List**

For `test_vector_store_manager.py` — InMemoryVectorStore (no mocking needed):
1. Test `create_collection`: creates entry in `_collections`.
2. Test `create_collection`: idempotent (called twice → no error).
3. Test `insert_vectors`: records stored with id, vector, payload, _partition.
4. Test `insert_vectors`: auto-generates UUID ids when `ids=None`.
5. Test `search`: returns top_k results sorted by cosine similarity descending.
6. Test `search`: returns empty list when collection is empty.
7. Test `search`: cosine similarity with zero-norm vector → score 0.0 (no ZeroDivisionError).
8. Test `list_records`: partition filter applied correctly.
9. Test `list_records`: metadata filter (equality) applied correctly.
10. Test `list_records`: returns all partitions when partition_name=None.
11. Test `delete_collection`: removes collection and partitions.
12. Test `delete_partition`: removes only that partition's records; others unaffected.
13. Test `delete_records`: returns count; filter applied.
14. Test `collection_exists`: True/False.
15. Test `VectorStoreManager.__init__`: VECTOR_DB_TYPE="memory" → InMemoryVectorStore.
16. Test `VectorStoreManager.__init__`: VECTOR_DB_TYPE="unknown" → InMemoryVectorStore.
17. Test `VectorStoreManager.delete_records`: empty filter → ValueError.
18. Test `VectorStoreManager.delete_records`: non-empty filter → delegates to store.

For `test_milvus_vector_store.py` — mock `pymilvus.MilvusClient`:
1. Test `_build_filter_expression()`: empty dict → ""; single key → correct Milvus expression.
2. Test `_build_filter_expression()`: multiple keys → "and"-joined expressions.
3. Test `_build_filter_expression()`: unsafe key (contains non-alphanumeric) → ValueError.
4. Test `_get_client()`: URI construction, no auth if user/password absent.
5. Test `_get_client()`: auth passed when both user and password present.
6. Test `create_collection()`: skipped if `has_collection()` returns True (idempotent).
7. Test `create_collection()`: creates schema with id, vector, payload fields.
8. Test `create_partition()`: skipped if `has_partition()` returns True.
9. Test `insert_vectors()`: empty list → returns without calling insert.
10. Test `search()`: correct output mapping from MilvusClient.search() response.
11. Test `delete_collection()`: skipped if collection doesn't exist.
12. Test `delete_records()`: returns 0 if collection doesn't exist.
13. Test `collection_exists()`: delegates to `has_collection()`.

For `test_embedding_provider.py` — mock `openai.OpenAI`:
1. Test `__init__`: missing OPENAI_API_KEY → ValueError.
2. Test `__init__`: known model → correct dimension from `_OPENAI_MODEL_DIMENSIONS`.
3. Test `__init__`: unknown model without RAG_OPENAI_EMBEDDING_DIMENSIONS → ValueError.
4. Test `__init__`: unknown model WITH explicit dimensions → uses explicit value.
5. Test `embed_documents()`: empty list → [].
6. Test `embed_documents()`: non-empty list → calls OpenAI API; extracts `.embedding`.
7. Test `embed_documents()`: `dimensions` param added only when `_requested_dimensions` set.
8. Test `embed_query()`: calls API with single-item list; returns first embedding.

For `test_storage_client.py`:
1. Test `_ensure_public_http_url()`: non-http scheme (ftp://) → ValueError.
2. Test `_ensure_public_http_url()`: no hostname → ValueError.
3. Test `_ensure_public_http_url()`: private IP (192.168.x.x) → ValueError.
4. Test `_ensure_public_http_url()`: loopback (127.0.0.1) → ValueError.
5. Test `_ensure_public_http_url()`: valid public URL → no exception.
6. Test `_ensure_public_http_url()`: hostname that resolves to private IP → ValueError.
7. Test `download_from_bucket()`: blob exists → returns bytes.
8. Test `download_from_bucket()`: blob does not exist → FileNotFoundError.
9. Test `download_with_metadata()`: returns (bytes, content_type).
10. Test `upload_bytes()`: success → True; exception → logs and returns False.
11. Test `upload_public_bytes()`: no public_bucket → returns (False, None).
12. Test `upload_public_bytes()`: success → (True, url).
13. Test `download_from_url()`: valid URL → returns content bytes (mock httpx.get).
14. Test `download_from_url()`: SSRF-blocked URL → ValueError.
15. Test `_resolve_content_type()`: explicit type used; fallback to mimetypes.guess_type.
16. Test `startup_event()`: exception is caught and logged; does not raise.
17. Test `startup_event()`: no default_bucket → skips GCS check without error.

For `test_storage_config.py`:
1. Test `__init__`: no credentials → credentials_info=None, no error.
2. Test `__init__`: valid JSON credentials → credentials_info set.
3. Test `__init__`: invalid JSON → ValueError.
4. Test `__init__`: JSON not a dict → TypeError.
5. Test `__init__`: credentials with no project_id and no STORAGE_PROJECT_ID → ValueError.
6. Test `__init__`: STORAGE_PROJECT_ID set → project_id resolved.
7. Test `_get_project_id_from_credentials_info()`: project_id in JSON → returned.
8. Test `has_credentials_info()`: True/False based on credentials_info.

For `test_config_server.py` — mock `httpx.AsyncClient`:
1. Test `fetch_config()`: use_spring_cloud_config=False → {"enabled": False, "loaded": False}.
2. Test `fetch_config()`: no spring_cloud_config_uri → {"enabled": False, "loaded": False}.
3. Test `fetch_config()`: HTTP GET success → parses propertySources; "enabled":True, "loaded":True.
4. Test `fetch_config()`: propertySources in reverse order (last source overrides first).
5. Test `fetch_config()`: HTTP error (e.g. 404 raise_for_status) → "loaded": False, "error" set.
6. Test `fetch_config()`: timeout exception → "loaded": False, "error" set.
7. Test `fetch_config()`: URL construction: {uri}/{app_name}/{spring_profiles_active}.

For `test_eureka.py` — mock `py_eureka_client.eureka_client`:
1. Test `register()`: eureka_enabled=False → {"enabled": False, "registered": False}.
2. Test `register()`: eureka_client None (import failed) → error dict.
3. Test `register()`: success on first attempt → {"enabled": True, "registered": True}.
4. Test `register()`: success on second attempt (first raises) → registered.
5. Test `register()`: all retries exhausted → {"registered": False, "error": "retries exhausted"}.
6. Test `register()`: sets `_registered = True` on success.
7. Test `stop()`: `_registered=False` → does not call `stop_async()`.
8. Test `stop()`: `_registered=True` → calls `stop_async()`.
9. Test `stop()`: `stop_async()` raises → logs warning, does not propagate.

**Relevant Context**

- `app/infrastructure/vector_store/vector_store_manager.py`
- `app/infrastructure/vector_store/milvus_vector_store.py`
- `app/infrastructure/embeddings/embedding_provider.py`
- `app/infrastructure/clients/storage_client.py`
- `app/infrastructure/clients/storage_config.py`
- `app/infrastructure/clients/config_server.py`
- `app/infrastructure/clients/eureka.py`

---

### Sub-Task 4 — Service layer tests

**Status**: `[ ] pending`

**Intent**

Test all three service classes (`RAGService`, `DocumentEmbeddingService`, `StorageService`)
with mocked infrastructure. These are the most complex units and carry the core business logic.

**Expected Outcomes**

- 3 test files created under `test/unit/services/`.
- All public methods covered with success and failure paths.
- Branch coverage includes: chunking logic, text extraction paths (PDF/txt/json/plain),
  expansion strategies (reslice vs adjacent-chunk-index), vectorization trigger conditions.
- `ruff check test/unit/services/` passes.

**Todo List**

For `test_rag_service.py`:
1. Test `_sanitize_collection_name()`: unicode/hyphen chars → `_`; digit-leading → `_` prefix.
2. Test `_sanitize_collection_name()`: empty string → `"_"`.
3. Test `_sanitize_collection_name()`: already-clean name unchanged.
4. Test `RAGService.__init__()`: creates collection if not exists.
5. Test `RAGService.__init__()`: skips creation if collection exists.
6. Test `RAGService.__init__()`: always calls `create_partition`.
7. Test `index_documents()`: no chunking (chunk=False) → single record indexed.
8. Test `index_documents()`: with chunking → multiple records with start_index/end_index.
9. Test `index_documents()`: chunk_size/chunk_overlap override over defaults.
10. Test `index_documents()`: metadata enriched with chunk_index, start_index, end_index, text.
11. Test `_split_text()`: normal case with overlap.
12. Test `_split_text()`: chunk_size=1 → many tiny chunks.
13. Test `_split_text()`: chunk_size > len(text) → single chunk.
14. Test `_split_text()`: overlap >= chunk_size → clamped to chunk_size-1.
15. Test `_split_text()`: negative chunk_size → clamped to 1.
16. Test `_split_text()`: empty text → list with one tuple ("", 0, 0).
17. Test `search()`: calls embed_query + vector_store.search with correct partition.
18. Test `search()`: top_k=None → uses settings.rag_default_top_k.
19. Test `clear_collection()`: calls `delete_partition` with correct collection + partition.
20. Test `delete_records()`: delegates to `delete_records` with partition_name.

For `test_document_embedding_service.py`:
1. Test `_get_rag_service()`: same index_name → returns cached instance.
2. Test `_get_rag_service()`: different index_name → creates new instance.
3. Test `save_document_to_vecstore()`: base64 path → decodes and indexes.
4. Test `save_document_to_vecstore()`: URL path → calls download_from_url.
5. Test `save_document_to_vecstore()`: bucket path → calls download_from_bucket.
6. Test `save_document_to_vecstore()`: no text extracted → raises ValueError.
7. Test `save_document_to_vecstore()`: list_parameters normalization (key/code aliases).
8. Test `save_document_to_vecstore()`: VECTOR_CHUNK_SIZE from parameters → uses as chunk_size.
9. Test `save_document_to_vecstore()`: invalid VECTOR_CHUNK_SIZE string → falls back to None.
10. Test `delete_index()`: calls clear_collection; removes from _rag_services cache.
11. Test `delete_document()`: filters by id_document; returns deleted_count.
12. Test `list_unique_code_documents()`: deduplicates by unique_code; respects limit.
13. Test `list_unique_code_documents()`: payload missing unique_code → falls back to id_document.
14. Test `list_documents_by_index()`: deduplicates by document key; respects limit.
15. Test `list_documents_by_index()`: text excluded from metadata dict.
16. Test `get_embeddings_by_unique_code()`: records sorted by chunk_index.
17. Test `search_similar_documents()`: expand_context=False → no expanded_text field.
18. Test `search_similar_documents()`: expand_context=True → calls _expand_context.
19. Test `_load_file_content()`: has_document_base64=True + base64 present → decodes.
20. Test `_load_file_content()`: has_document_base64=True + base64 None → falls to URL.
21. Test `_load_file_content()`: URL present → calls download_from_url.
22. Test `_load_file_content()`: no base64, no URL → calls download_from_bucket.
23. Test `_extract_text_from_file()`: .txt bytes → decoded text.
24. Test `_extract_text_from_file()`: .pdf bytes → calls pdfplumber (mock).
25. Test `_extract_text_from_file()`: .json bytes → JSON text.
26. Test `_extract_text_from_file()`: unknown extension → UTF-8 decode.
27. Test `_normalize_parameters()`: "key"/"value" form; "code"/"value" form; fallback.
28. Test `_parse_int_parameter()`: valid int string → int; invalid → None; None → None.
29. Test `_expand_context()`: exception on one result → logged, others unaffected.
30. Test `_expand_single_result()`: payload has start_index/end_index → reslice strategy.
31. Test `_expand_single_result()`: no start_index → adjacent chunk index strategy.
32. Test `_expand_via_source_reslice()`: uses file_cache; downloads by unique_code, not file_name.
33. Test `_expand_via_source_reslice()`: window clamped at 0 and len(text).
34. Test `_expand_via_adjacent_chunk_index()`: collects N+1 consecutive chunks.
35. Test `_expand_via_adjacent_chunk_index()`: no matching chunks → None.

For `test_storage_service.py`:
1. Test `upload_file()`: file read success + storage upload success → UploadFileResponse(success=True).
2. Test `upload_file()`: file.read() raises → UploadFileResponse(success=False).
3. Test `upload_file()`: success + vectorization trigger with all conditions → add_task called.
4. Test `upload_file()`: success + trigger missing unique_code → add_task NOT called.
5. Test `upload_file()`: success + trigger missing background_tasks → add_task NOT called.
6. Test `upload_file()`: upload_content_bucket=False → add_task NOT called.
7. Test `store_chunk()`: intermediate chunk (not last) → consolidated=False.
8. Test `store_chunk()`: final chunk → consolidated=True, calls _consolidate_chunks.
9. Test `store_chunk()`: final chunk + vectorization trigger → add_task called.
10. Test `store_chunk()`: creates directories with 0o700 permissions.
11. Test `store_chunk()`: writes chunk part file with correct name.
12. Test `store_chunk()`: writes metadata.properties file.
13. Test `get_file()`: download succeeds → returns (bytes, content_type).
14. Test `get_file()`: FileNotFoundError → HTTPException 404.
15. Test `get_file()`: generic Exception → HTTPException 500.
16. Test `get_file_byte()`: returns FileResponse with base64 field.
17. Test `upload_public_file()`: success → UploadPublicFileResponse(success=True, url=...).
18. Test `upload_public_file()`: file.read() raises → success=False, url=None.
19. Test `_resolve_vectorization_index()`: project_id → "project_<id>".
20. Test `_resolve_vectorization_index()`: no project_id + code_type_document → code used.
21. Test `_resolve_vectorization_index()`: neither → default collection name.
22. Test `_vectorize_uploaded_file()`: encodes to base64; calls save_document_to_vecstore.
23. Test `_vectorize_uploaded_file()`: exception → logged, not re-raised.
24. Test `_collect_ordered_parts()`: returns .part files sorted by numeric stem.
25. Test `_consolidate_chunks()`: concatenates parts in order; calls upload_bytes.

**Relevant Context**

- `app/services/rag/rag_service.py`
- `app/services/embedding/document_embedding_service.py`
- `app/services/storage_service.py`

---

### Sub-Task 5 — API endpoint tests

**Status**: `[ ] pending`

**Intent**

Test all HTTP endpoints via `TestClient` (sync wrapper) with dependency overrides.
Covers status codes, response schemas, validation errors (422), error propagation (500),
and correlation-ID header propagation.

**Expected Outcomes**

- 3 test files created under `test/unit/api/`.
- All endpoints covered: happy path, validation error (422), service exception → 500.
- Correlation ID behavior tested.
- `ruff check test/unit/api/` passes.

**Todo List**

For `test_health_controller.py`:
1. Test `GET /api/v1/health/live`: status 200, body `{"status": "alive"}`.
2. Test `GET /api/v1/health/ready`: all deps disabled → 200, status="ready".
3. Test `GET /api/v1/health/ready`: config_server enabled + loaded → 200.
4. Test `GET /api/v1/health/ready`: config_server enabled + not loaded + critical → 503.
5. Test `GET /api/v1/health/ready`: eureka enabled + not registered + critical → 503.
6. Test `GET /api/v1/health/ready`: non-critical dep fails → 200 but in failed_dependencies.
7. Test `GET /api/v1/health/ready`: response includes "integrations", "service", "environment".
8. Test correlation ID: header passed in request → same value in response header.
9. Test correlation ID: no header in request → UUID generated and returned.
10. Test `GET /`: root endpoint returns service name, environment, api_prefix, docs.

For `test_embedding_controller.py`:
1. Test POST `/api/v1/embedding/save_document_vecstore`: service returns dict → 200 with schema.
2. Test POST `/api/v1/embedding/save_document_vecstore`: service raises → 500 HTTPException.
3. Test POST `/api/v1/embedding/save_document_vecstore`: missing required field → 422.
4. Test POST `/api/v1/embedding/delete_index_vecstore`: 200 + OperationStatusResponse.
5. Test POST `/api/v1/embedding/delete_index_vecstore`: service raises → 500.
6. Test POST `/api/v1/embedding/delete_document`: 200 + DeleteDocumentVecstoreResponse.
7. Test POST `/api/v1/embedding/delete_document`: service raises → 500.
8. Test POST `/api/v1/embedding/list_unique_code_documents`: 200 + list response.
9. Test POST `/api/v1/embedding/list_unique_code_documents`: service raises → 500.
10. Test POST `/api/v1/embedding/list_documents`: 200 + ListDocumentsResponse.
11. Test POST `/api/v1/embedding/list_documents`: service raises → 500.
12. Test POST `/api/v1/embedding/get_embeddings_by_unique_code`: 200 + response schema.
13. Test POST `/api/v1/embedding/get_embeddings_by_unique_code`: service raises → 500.
14. Test POST `/api/v1/embedding/search_similar_documents`: 200 + SearchSimilarDocumentsResponse.
15. Test POST `/api/v1/embedding/search_similar_documents`: service raises → 500.
16. Test camelCase request body accepted (indexVecstore vs index_vecstore).
17. Test `delete_index_vecstore`: verifies background task is added (not executed synchronously).

For `test_storage_controller.py`:
1. Test POST `/api/v1/storage/upload`: form + file → 200 UploadFileResponse.
2. Test POST `/api/v1/storage/upload`: missing required `name` form field → 422.
3. Test POST `/api/v1/storage/upload`: missing `file` → 422.
4. Test POST `/api/v1/storage/chunk`: intermediate chunk → 200 consolidated=False.
5. Test POST `/api/v1/storage/chunk`: missing required form fields → 422.
6. Test GET `/api/v1/storage/get`: name query param → StreamingResponse.
7. Test GET `/api/v1/storage/get`: missing `name` → 422.
8. Test GET `/api/v1/storage/getFileByte`: name query param → 200 FileResponse.
9. Test POST `/api/v1/storage/public-upload`: file + name → 200 UploadPublicFileResponse.
10. Test vectorization trigger form dependency: codeTypeDocument, uniqueCode aliases work.

**Relevant Context**

- `app/api/routes/health_controller.py`
- `app/api/routes/embedding_controller.py`
- `app/api/routes/storage_controller.py`
- `app/core/middleware.py` (correlation ID tested through TestClient)

---

### Sub-Task 6 — Validation, schemas, and main app tests

**Status**: `[ ] pending`

**Intent**

Test Pydantic schemas for serialization correctness and any schema with validation logic.
Also test `app/main.py`: `create_app()` configuration and the root endpoint. This fills
remaining coverage gaps.

**Expected Outcomes**

- Schema tests confirm camelCase alias round-trip and field constraints.
- `create_app()` tested for CORS configuration (wildcard vs explicit origins).
- `ruff check test/unit/` passes on all files.
- `mypy` produces no new errors related to test files (since tests are outside `files=["app"]`).

**Todo List**

1. Create `test/unit/test_main.py`:
   - Test `create_app()`: CORS with `*` → `allow_credentials=False`.
   - Test `create_app()`: explicit origins → `allow_credentials=True`.
   - Test `create_app()`: app title equals `settings.app_name`.
   - Test `GET /` root endpoint via TestClient.

2. Create `test/unit/test_schemas.py`:
   - Test `SaveDocumentVecstoreRequest`: camelCase deserialization (indexVecstore → index_vecstore).
   - Test `ListDocumentsRequest`: `limit` default from settings, ge/le bounds.
   - Test `SearchSimilarDocumentsRequest`: top_k bounds.
   - Test `OperationStatusResponse`: `mensaje`/`codigo` fields (Spanish names; no camelCase change).
   - Test `UploadFileResponse`, `ChunkUploadResponse`, `FileResponse` round-trips.
   - Test `DocumentSummaryResponse`: expanded_text is optional (None by default).

3. Verify `test/unit/api/test_router_controller.py` (simple):
   - Test that `api_router` has routes for `/embedding`, `/health`, `/storage` prefixes.

**Relevant Context**

- `app/main.py`
- `app/schemas/embedding.py`
- `app/schemas/storage.py`
- `app/api/router_controller.py`

---

### Sub-Task 7 — Run, fix, verify, and report

**Status**: `[ ] pending`

**Intent**

Execute the full test suite, fix any failures, run coverage, run Ruff, and produce the
final report as required by the task.

**Expected Outcomes**

- `uv run pytest test/ -v` exits with 0 failures.
- `uv run pytest test/ --cov=app --cov-report=term-missing` generates coverage report.
- `uv run ruff check .` passes (no errors on test files or app files).
- `uv run mypy` passes (mypy only covers `app/`).
- `uv run bandit -r app/` passes (no changes to production code).
- Final summary report delivered.

**Todo List**

1. Run `uv run pytest test/ -v` — fix any import errors, fixture issues, or assertion failures.
2. Run `uv run pytest test/ --cov=app --cov-report=term-missing` — record results.
3. Run `uv run ruff check .` — fix any lint errors in test files.
4. Run `uv run ruff format --check .` — fix any format issues.
5. Run `uv run mypy` — verify no new errors.
6. Review coverage report:
   - Identify files below 70% with explanation.
   - Note any lines that cannot reasonably be covered (e.g. Milvus real auth, Docker-specific paths).
7. Update `pyproject.toml` `[tool.pytest.ini_options]` to add
   `addopts = "--tb=short"` for better CI output (optional but helpful).
8. Deliver final summary report with: test counts, pass/fail, coverage %, Ruff/mypy status,
   and notes on uncoverable lines.

**Relevant Context**

- `.github/workflows/ci.yml`: once tests pass, note that `continue-on-error: true` on the
  pytest step should be removed (but this is NOT done automatically — only flagged in report).

---

## Notes on testability

### Potential coverage gaps (justified)

| Module / Line | Reason | Mitigation |
|---|---|---|
| `app/core/config.py: get_settings()` Vault path | Requires real Vault + hvac auth | Mocked via `patch("app.core.config.is_vault_configured", return_value=True)` + mock VaultClient |
| `app/infrastructure/vector_store/milvus_vector_store.py` full integration | Requires running Milvus | All methods tested via mocked `MilvusClient` |
| `app/infrastructure/clients/storage_client.py: _get_client()` real GCS | Requires service account JSON | Mocked via patch on `google.cloud.storage.Client` |
| `app/main.py: run()` | Calls `uvicorn.run()` — would start a real server | Trivially tested: mock uvicorn.run and verify call args |
| `app/infrastructure/clients/eureka.py` real py_eureka_client | py_eureka_client.init_async is a real network call | Mocked at module level |
| `app/services/storage_service.py: _consolidate_chunks` real filesystem | Requires temp dir | Use `tmp_path` pytest fixture for real filesystem calls |
