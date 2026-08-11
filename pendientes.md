# Pendientes — ai-rag-service-manager

Registro de trazabilidad de hallazgos detectados durante la revisión del microservicio. No reemplaza al README: aquí se documentan brechas, riesgos y deuda técnica, con su estado de resolución.

Cómo usarlo:

- Cada hallazgo tiene un ID estable (`P-XX`). No reutilizar IDs.
- Al resolver un pendiente, cambiar `Estado` a `Resuelto`, agregar `Resuelto el` y una línea `Solución aplicada`.
- Agregar hallazgos nuevos al final de su sección de prioridad, no reordenar los existentes.

Última actualización: 2026-08-11.

## Resumen de estado

| ID | Título | Prioridad | Estado |
|----|--------|-----------|--------|
| P-01 | SSRF sin validar en `url_download_file` | Alta | Resuelto |
| P-02 | `/storage/public-upload` roto (falta `storage_public_bucket_name`) | Alta | Resuelto |
| P-03 | README no documenta `storage_controller` | Alta | Resuelto |
| P-04 | Embeddings no son reales (hash determinístico) | Media | Resuelto |
| P-05 | No hay integración LLM real en `rag_query` | Media | Pendiente |
| P-06 | `.env.example` ausente (contradice al README) | Media | Resuelto |
| P-07 | Cero tests pese a estar configurado en `pyproject.toml` | Media | Pendiente |
| P-08 | Vector store real (Milvus) no implementado | Baja | Resuelto |
| P-09 | `InMemoryRagServiceRepository` sin persistencia real | Baja | Pendiente |
| P-10 | `storage-upload-vectorization` sin integrar (marcado en código) | Baja | Pendiente |
| P-11 | `storage-chunk-consolidation` sin integrar (marcado en código) | Baja | Pendiente |
| P-12 | Acoplamiento import-time con Vault en `app/schemas/embedding.py` | Baja | Pendiente |
| P-13 | CORS abierto (`*`) + `allow_credentials` sin autenticación | Baja | Resuelto (parcial) |
| P-14 | `/health/ready` nunca refleja fallas reales de dependencias | Baja | Resuelto |
| P-15 | Inconsistencia camelCase/snake_case entre `rag-services` y `embedding`/`storage` | Baja | Resuelto |
| P-16 | `/storage/chunk` no declara sus campos como `Form()`, no aparece bien en OpenAPI | Baja | Resuelto |
| P-17 | `Settings` no carga `.env` automáticamente pese a lo que dice el README | Baja | Resuelto |
| P-18 | Adopción del estándar corporativo de calidad/seguridad (CI/CD, mypy, Bandit, pip-audit, Gitleaks, Trivy, coverage) | Media | Resuelto (parcial) |
| P-19 | Imagen Docker creció ~1.6GB por embeddings locales (torch + sentence-transformers + pymilvus) | Baja | Pendiente |

---

## Alta prioridad

### P-01 — SSRF sin validar en `url_download_file`

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-10
- **Ubicación:** `app/infrastructure/clients/storage_client.py` (`download_from_url`), invocado desde `app/services/embedding/document_embedding_service.py` (`_load_file_content`).
- **Descripción:** `POST /api/v1/embedding/save_document_vecstore` acepta un campo `urlDownloadFile` que el servicio descarga con `httpx.get(url)` sin ninguna validación de esquema, host o rango de IP. El endpoint no requiere autenticación.
- **Impacto:** Cualquier llamador podía usar el microservicio como proxy para alcanzar red interna (metadata de nube, servicios internos sin exponer, `localhost` del propio contenedor) — Server-Side Request Forgery clásico.
- **Solución aplicada:** se agregó `_ensure_public_http_url` en `storage_client.py`, que exige esquema `http`/`https`, resuelve el hostname y rechaza IPs privadas, loopback, link-local, reservadas, multicast o no especificadas antes de descargar. Se fijó `follow_redirects=False` explícito para evitar bypass vía redirección.

### P-02 — `/storage/public-upload` roto (falta `storage_public_bucket_name`)

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-10
- **Ubicación:** `app/infrastructure/clients/storage_config.py:21`, `app/core/config.py`.
- **Descripción:** `StorageConfig` leía `getattr(settings, "storage_public_bucket_name", None)`, pero ese campo no existía en `Settings`. El valor siempre era `None`.
- **Impacto:** `POST /api/v1/storage/public-upload` fallaba siempre con `success=False, url=None`, sin importar la configuración real del entorno — funcionalidad inutilizable.
- **Solución aplicada:** se agregó el campo `storage_public_bucket_name` a `Settings` (`app/core/config.py`), con alias `STORAGE_PUBLIC_BUCKET_NAME`, y `StorageConfig` ahora lo lee directamente en vez de usar `getattr` con fallback.

### P-03 — README no documenta `storage_controller`

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-10
- **Ubicación:** `README.md` (sección "Endpoints principales"), `app/api/routes/storage_controller.py`.
- **Descripción:** El router de storage está incluido en `app/api/router_controller.py` y expone 5 endpoints reales (`/storage/upload`, `/chunk`, `/get`, `/getFileByte`, `/public-upload`), pero el README solo listaba `health`, `rag-services` y `embedding`.
- **Impacto:** Documentación incompleta; alguien leyendo solo el README no sabía que el servicio expone operaciones de storage.
- **Solución aplicada:** se agregaron los endpoints de storage a la sección "Endpoints principales" del README y se agregó una referencia a `api.md` como fuente completa de contratos de request/response.

---

## Media prioridad

### P-04 — Embeddings no son reales

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/services/rag/rag_service.py` (`_embed_text`, eliminado); nuevo `app/infrastructure/embeddings/embedding_provider.py`.
- **Descripción:** Pese a que `Settings.rag_embedding_model` sugería `sentence-transformers/all-MiniLM-L6-v2`, el vector real se generaba con hashing SHA-256 determinístico por token — no había ningún modelo de embeddings cargado.
- **Solución aplicada:** se agregó `EmbeddingProvider` (usa `pymilvus.model.dense.SentenceTransformerEmbeddingFunction`, que envuelve `sentence-transformers`) cargando el modelo indicado en `RAG_EMBEDDING_MODEL`/`RAG_EMBEDDING_DEVICE`/`RAG_NORMALIZE_EMBEDDINGS`. Es una instancia única (`@lru_cache` en `app/api/dependencies/services.py`, `get_embedding_provider()`) compartida entre todas las colecciones/instancias de `RAGService` — cargar el modelo es costoso, no se puede repetir por request. `RAGService` ya no calcula `_vector_size` fijo (era `128` hardcodeado); ahora usa `embedding_provider.dim` (384 para el modelo default).
- **Verificación real:** se corrió un test end-to-end (embeddings reales + Milvus real, ver P-08) indexando 3 documentos de temas distintos (gatos, finanzas, Python) y consultando `"lenguajes de programacion"` — el resultado top-1 fue correctamente el documento de Python (score 0.589) muy por encima del de gatos (score 0.256), algo que el hashing anterior no podía lograr al no capturar significado semántico.
- **Pendiente relacionado no resuelto aquí:** el modelo (`sentence-transformers/all-MiniLM-L6-v2`) es un default genérico, no validado contra datos/dominio propios de negocio — antes de confiar en la calidad de retrieval para un caso de uso real, evaluar el modelo con datos reales del dominio y comparar contra alternativas (BGE, modelos en español, etc.) si el default no rinde bien.
- **Impacto en imagen Docker:** agrega `torch`+`sentence-transformers`+`pymilvus` como dependencias core — ver P-19.

### P-05 — No hay integración LLM real en `rag_query`

- **Estado:** Pendiente
- **Detectado:** 2026-08-10
- **Ubicación:** `app/services/rag/rag_agent.py` (`answer_with_context`).
- **Descripción:** `POST /api/v1/embedding/rag_query` siempre responde `answer: "LLM integration pending. Retrieved context returned."`. Los campos `llm_provider`/`chat_model` de `rag-services` no se usan en ningún punto del flujo de embedding/retrieval.
- **Impacto:** El endpoint no genera respuestas basadas en LLM, solo retorna contexto recuperado y fuentes.
- **Acción sugerida:** conectar `RAGAgent` con un cliente LLM real, idealmente resolviendo el proveedor/modelo desde la definición de `rag-services` correspondiente (hoy desconectada del flujo, ver relación con P-04).

### P-06 — `.env.example` ausente (contradice al README)

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-10
- **Ubicación:** raíz del repositorio; referenciado en `README.md` ("se documentan en `.env.example`") y en `.gitignore` (`!.env.example`).
- **Descripción:** El archivo no existía en el working tree ni en el historial de git, pese a estar referenciado en dos lugares distintos del repo.
- **Impacto:** Onboarding más lento; no había una lista canónica de variables de entorno esperadas fuera de leer `config.py` línea por línea.
- **Solución aplicada:** se creó `.env.example` en la raíz del repo con todas las variables de `Settings` (incluyendo `STORAGE_PUBLIC_BUCKET_NAME` y `CORS_ALLOWED_ORIGINS`, agregadas en P-02 y P-13), agrupadas igual que en el README, con valores de ejemplo no sensibles. Se documentó explícitamente en el propio archivo que `Settings` no auto-carga `.env` hoy (ver P-17), para no generar una falsa expectativa.

### P-07 — Cero tests pese a estar configurado

- **Estado:** Pendiente
- **Detectado:** 2026-08-10
- **Ubicación:** `pyproject.toml` (`[tool.pytest.ini_options]`, dependencias `dev`); no existe carpeta `tests/`.
- **Descripción:** `pytest`, `pytest-asyncio` están declarados como dependencias de desarrollo y `testpaths = ["tests"]` apunta a una carpeta inexistente.
- **Impacto:** Cobertura real 0%. Cualquier cambio (incluyendo los de este documento) no tiene red de seguridad automatizada.
- **Acción sugerida:** crear `tests/` con al menos smoke tests de cada controller usando `TestClient`/`httpx.AsyncClient`, priorizando `rag_services_controller` (lógica de negocio real) y los casos nuevos de validación SSRF (P-01).

---

## Baja prioridad

### P-08 — Vector store real (Milvus) no implementado

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/infrastructure/vector_store/vector_store_manager.py`; nuevo `app/infrastructure/vector_store/milvus_vector_store.py` y `vector_store_interface.py` (extraído para evitar import circular con `milvus_vector_store.py`).
- **Descripción:** `Settings` traía todos los parámetros de Milvus (host, puerto, alias, métrica, tipo de índice, nlist, nprobe), pero `VectorStoreManager` solo tenía `InMemoryVectorStore`; pedir `milvus` caía silenciosamente a memoria con un warning en logs.
- **Solución aplicada:** `MilvusVectorStore` implementa `VectorStoreInterface` completo usando `pymilvus.MilvusClient` (API moderna, no la de `connections.connect()` + `Collection`). Esquema de colección: `id` (VARCHAR, primary key), `vector` (FLOAT_VECTOR, dimensión del `EmbeddingProvider` activo) y `payload` (**JSON**) — este último preserva el contrato de dict libre que ya usa el resto de la app (`record["payload"].get(...)`) sin declarar una columna por cada clave de metadata posible. `filter_conditions` se traduce a expresiones de filtro de Milvus sobre ese campo JSON (`payload["clave"] == valor`). `VectorStoreManager` ahora instancia `MilvusVectorStore` de verdad cuando `VECTOR_DB_TYPE=milvus`.
- **Seguridad — inyección de filtro:** las claves de `filter_conditions` (parcialmente controladas por el cliente vía `metadata_filter` en la API) se interpolan directo en la expresión de filtro Milvus (`payload["<key>"] == ...`); se agregó una validación (`_SAFE_KEY_PATTERN`, solo `[A-Za-z0-9_]+`) que rechaza claves con comillas u otros caracteres que podrían escapar la expresión — mismo principio aplicado en P-01 (SSRF) de validar entrada no confiable en la frontera.
- **Verificación real contra Milvus real** (no solo tests unitarios): usando el Milvus del usuario (`localhost:19530`, `milvus-standalone:v2.6.21`, sin auth) se probó — creación de colección con prefijo de nombre resuelto correctamente, indexación de 3 documentos con chunking, búsqueda semántica (top-1 correcto), búsqueda con filtro por `department` (devolvió exactamente 1 resultado del department correcto), `retrieve_context`, `list_records`, y `delete_collection` (confirmado con `collection_exists` antes/después). Ver detalle de la prueba de búsqueda semántica en P-04.
- **`MILVUS_ALIAS` sin uso real:** `MilvusClient` (API moderna) no tiene concepto de alias de conexión global (eso era de la API legacy `connections.connect(alias=...)`); el setting se deja en `Settings`/`.env.example` documentado como no usado por este adapter, por si se vuelve a necesitar con la API clásica.
- **Impacto en imagen Docker:** ver P-19 — `pymilvus[model]` + `sentence-transformers` + `torch` (CPU-only, fijado vía índice de `uv`) agregan ~1.6GB al `.venv`.

### P-09 — `InMemoryRagServiceRepository` sin persistencia real

- **Estado:** Pendiente
- **Ubicación:** `app/infrastructure/repositories/in_memory_rag_service_repository.py`.
- **Descripción:** Las definiciones de `rag-services` viven solo en memoria del proceso.
- **Impacto:** Se pierden en cada restart/deploy y no se comparten entre réplicas si el servicio escala horizontalmente.
- **Acción sugerida:** backlog de producto (requiere elegir motor de persistencia). **No relacionado con la integración de Milvus (P-08)**: este pendiente es sobre el almacén de las *definiciones* de `rag-services` (nombre, proveedor LLM, etc.), un dominio distinto al de los vectores/documentos que sí ahora persisten en Milvus.

### P-10 — `storage-upload-vectorization` sin integrar

- **Estado:** Pendiente
- **Ubicación:** `app/services/storage_service.py` (`upload_file`), marcado explícitamente en código como `PENDIENTE_INTEGRACION`.
- **Descripción:** En el micro Java origen, un upload exitoso podía disparar vectorización automática vía `ParameterCommonService`, `VectorStoreService`, `DocumentCommonService`. Esa continuación no se migró.
- **Impacto:** El upload conserva la API pública pero no ejecuta efectos laterales de vectorización ni actualización de estado documental.
- **Acción sugerida:** decidir si se replica ese flujo o si vectorización queda como paso explícito vía `/embedding/save_document_vecstore` (enfoque actual, más simple). **Con embeddings/Milvus reales (P-04/P-08) esta decisión ya no está bloqueada técnicamente** — antes no había vectorización real que disparar; ahora es una decisión de alcance de producto, no una limitación técnica.

### P-11 — `storage-chunk-consolidation` sin integrar

- **Estado:** Pendiente
- **Ubicación:** `app/services/storage_service.py` (`store_chunk`), marcado explícitamente en código como `PENDIENTE_INTEGRACION`.
- **Descripción:** Los chunks subidos se persisten en disco local (`STORAGE_CHUNK_UPLOAD_TEMP_DIR`), pero no hay consolidación final (merge), subida a GCS del archivo ensamblado, ni limpieza transaccional post-commit.
- **Impacto:** El endpoint recibe y guarda partes, pero el circuito de ensamblado y publicación del archivo final no está cerrado.
- **Acción sugerida:** implementar consolidación (merge de `.part` por `uploadId`, subida final, limpieza) cuando se necesite el flujo de upload por chunks completo.

### P-12 — Acoplamiento import-time con Vault en `app/schemas/embedding.py`

- **Estado:** Pendiente
- **Ubicación:** `app/schemas/embedding.py:9` (`settings = get_settings()` a nivel de módulo).
- **Descripción:** Importar el módulo de schemas ejecuta `get_settings()`, que internamente llama a Vault. Si Vault no está accesible, ni siquiera se puede importar el módulo.
- **Impacto:** Rompe testabilidad unitaria aislada (no se puede importar schemas sin Vault configurado) y acopla una capa de contratos HTTP a infraestructura de secretos.
- **Acción sugerida:** mover la resolución de defaults (`rag_default_list_limit`, `rag_default_top_k`) a `Field(default_factory=...)` evaluado en tiempo de request, o inyectar el valor por defecho en el controller en vez del schema.

### P-13 — CORS abierto (`*`) + `allow_credentials` sin autenticación

- **Estado:** Resuelto (parcial)
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-10
- **Ubicación:** `app/main.py` (`CORSMiddleware`), `app/core/config.py`.
- **Descripción:** `allow_origins=["*"]` estaba combinado con `allow_credentials=True` de forma fija en código. Esa combinación es una anti-práctica de seguridad y, en un browser real, ni siquiera es funcional para requests con credenciales (el spec CORS prohíbe wildcard + credentials, y Starlette responde literalmente `*` como origen permitido).
- **Impacto:** Configuración insegura y engañosa: parecía permitir CORS credenciado desde cualquier origen, pero en la práctica un browser lo rechaza para requests con credenciales. Además no había forma de restringir origins sin tocar código.
- **Solución aplicada:** se agregó `cors_allowed_origins` a `Settings` (env var `CORS_ALLOWED_ORIGINS`, lista separada por comas, default `*`). En `app/main.py`, si se configuran orígenes explícitos, se habilita `allow_credentials=True` solo para esos orígenes; si se deja el default `*`, se sirve CORS abierto pero **sin** credenciales. Esto elimina la combinación insegura y permite bloquear origins en producción sin cambiar código.
- **Qué queda pendiente:** la ausencia de autenticación en los endpoints sigue siendo una **exclusión intencional documentada en el README** ("Exclusiones intencionales: autenticación JWT/OAuth2"), no un bug — por eso este ítem se marca "resuelto (parcial)": se corrigió la mala configuración técnica de CORS, no se agregó autenticación (decisión de alcance de producto, no de esta corrección).

### P-14 — `/health/ready` nunca refleja fallas reales de dependencias

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-10
- **Ubicación:** `app/api/routes/health_controller.py`.
- **Descripción:** El endpoint siempre respondía `"status": "ready"` con `200`, incluso si Config Server o Eureka fallaron en el startup; solo informaba su estado, no bloqueaba.
- **Impacto:** Un orquestador (p. ej. Kubernetes) que esperara un `503` real ante fallos de dependencias críticas no lo recibía nunca.
- **Solución aplicada (primera pasada):** `readiness` evaluaba `config_server` y `eureka`: si una integración estaba **habilitada** (`enabled: true`) pero no lograba completarse (`loaded`/`registered` en `false`), se agregaba a `failed_dependencies` y la respuesta pasaba a `503` con `"status": "not_ready"`. Si una integración estaba deshabilitada, no afectaba el resultado.
- **Ajuste 2026-08-10:** a pedido explícito, se hizo configurable **cuáles** integraciones habilitadas-pero-fallidas deben escalar a `503`, en vez de tratar siempre a `config_server` y `eureka` como críticas por igual. Se agregó `Settings.readiness_critical_dependencies` (env var `READINESS_CRITICAL_DEPENDENCIES`, CSV, default `config_server,eureka` — preserva el comportamiento anterior si no se configura nada). El endpoint ahora distingue `failed_dependencies` (toda integración habilitada que falló, siempre reportada para diagnóstico) de `blocking_failures` (subconjunto que efectivamente causa el `503`, filtrado por esa env var). Una integración **deshabilitada** — típicamente porque sus variables (`USE_SPRING_CLOUD_CONFIG`, `EUREKA_ENABLED`) no llegaron y su default es `False` — nunca entra a `failed_dependencies`, sin importar la lista de críticas: por diseño no se procesa ese flujo y no puede generar un error de readiness. Probado en aislamiento: ambas deshabilitadas → ready; una habilitada+fallida y crítica → 503; la misma fallida pero removida de la lista de críticas → sigue ready pero se reporta en `failed_dependencies`.

### P-15 — Inconsistencia camelCase/snake_case entre `rag-services` y `embedding`/`storage`

- **Estado:** Resuelto
- **Detectado:** 2026-08-10, durante la redacción de `api.md`.
- **Resuelto el:** 2026-08-10
- **Ubicación:** `app/schemas/rag_service.py`.
- **Descripción:** Los endpoints de `/rag-services` usaban JSON en `snake_case` (nombres de campo Python tal cual), mientras que `/embedding` y `/storage` usan `camelCase` vía alias generado. Ambos grupos conviven en la misma API pública bajo el mismo prefijo `/api/v1`.
- **Impacto:** Un consumidor de la API tenía que recordar dos convenciones distintas según el recurso.
- **Solución aplicada:** se aplicó `get_camel_case_config()` (mismo helper de `app/core/schema.py` que ya usan `embedding`/`storage`) a `RagServiceBase`, `RagServiceStatusUpdate`, `RagServiceResponse` (con `from_attributes=True`, preservando la validación desde la entidad de dominio) y `RagServiceListResponse`. La API ahora serializa `serviceId`, `llmProvider`, `chatModel`, `embeddingModel`, `vectorBackend`, `baseUrl`, `createdAt`, `updatedAt` de forma consistente con el resto del servicio. Por `populate_by_name=True`, el `snake_case` original se sigue aceptando de entrada (no rompe a nadie que ya probara la API en `snake_case`), pero toda respuesta ahora sale en `camelCase`. `api.md` se actualizó con los nombres de campo nuevos.
- **Nota:** es un cambio de contrato de respuesta (rompe a cualquier consumidor que ya dependiera de los nombres `snake_case` de salida). Dado que el repositorio es en memoria, sin persistencia ni consumidores documentados fuera de este mismo servicio, se consideró de bajo riesgo aplicarlo ahora en vez de dejarlo como deuda perpetua.

### P-16 — `/storage/chunk` no declara sus campos como `Form()`, no aparece bien en OpenAPI

- **Estado:** Resuelto
- **Detectado:** 2026-08-10, durante la redacción de `api.md`.
- **Resuelto el:** 2026-08-10
- **Ubicación:** `app/api/routes/storage_controller.py` (`upload_chunk`).
- **Descripción:** A diferencia de `/storage/upload` y `/storage/public-upload`, que declaran sus campos con `Form(...)`/`File(...)` (y por lo tanto FastAPI los documenta en `/docs`), `upload_chunk` leía el formulario manualmente con `await request.form()` y resolvía valores también desde query params vía `_resolve_request_value`.
- **Impacto:** Swagger/OpenAPI no mostraba los campos reales requeridos; solo se descubrían leyendo el código. Además, `int(chunk_index)`/`int(total_chunks)` sin manejo de error podían producir un `500` no controlado ante un valor no numérico.
- **Solución aplicada:** se reemplazó el parsing manual por parámetros `Form(...)` explícitos (`upload_id` alias `uploadId`, `chunk_index`/`total_chunks` tipados como `int`, `file_name` alias `fileName`, `name`, `bucket`, `project_id` alias `projectId`, `id_area` opcional alias `idArea`), igual que el resto de endpoints de `storage`. Se eliminó `_resolve_request_value` (ya sin uso) y las validaciones manuales de campos faltantes: FastAPI/Pydantic ahora responde `422` automáticamente ante campo faltante o valor no numérico en `chunkIndex`/`totalChunks`, incluyendo el caso que antes producía `500` sin manejar.
- **Cambio de comportamiento:** se dejó de soportar enviar estos valores por **query params** (solo `multipart/form-data` ahora), ya que no había evidencia de que el cliente real lo necesitara y ningún otro endpoint de `storage` lo soportaba. Documentado en `api.md` por si algún consumidor dependía de esa vía.

### P-17 — `Settings` no carga `.env` automáticamente pese a lo que dice el README

- **Estado:** Resuelto
- **Detectado:** 2026-08-10, al crear `.env.example` para P-06.
- **Resuelto el:** 2026-08-11.
- **Ubicación:** `app/core/config.py` (`Settings.model_config`, `get_settings()`); `app/core/vault.py` (`is_vault_configured`).
- **Descripción:** El README afirmaba que `.env` quedaba como fallback, pero `SettingsConfigDict` no definía `env_file`, así que `pydantic-settings` no leía `.env` del disco; y encima Vault era un requisito duro (`get_settings()` siempre llamaba a `get_vault_client()`, que fallaba si `VAULT_ADDR`/`VAULT_TOKEN` no estaban, sin ninguna forma de omitirlo para trabajo local).
- **Solución aplicada:**
  - `Settings.model_config` ahora incluye `env_file=".env"` (+ `env_file_encoding="utf-8"`) — con esto `.env` sí se carga de verdad como fallback, por debajo de variables ya exportadas al proceso.
  - Se agregó `USE_VAULT_CONFIG` (default `false`), **mismo patrón explícito** que `USE_SPRING_CLOUD_CONFIG`/`EUREKA_ENABLED` — no se infiere nada por presencia de `VAULT_ADDR`/`VAULT_TOKEN`, es una decisión declarada. `is_vault_configured()` (`app/core/vault.py`) la lee directo de `os.environ` (Vault no puede depender de `Settings`, que es justo lo que está por construirse).
  - `get_settings()`: si `USE_VAULT_CONFIG=true` → intenta Vault, y si faltan `VAULT_ADDR`/`VAULT_TOKEN` falla fuerte con el mensaje ya existente en `VaultClient` (no cae a `.env` en silencio por una config a medias). Si `USE_VAULT_CONFIG` es false/ausente → construye `Settings()` directo, que resuelve desde variables de entorno y, como fallback, desde `.env`.
  - Se creó un `.env` real en la raíz (no versionado, ya cubierto por `.gitignore`) para trabajo local: `USE_VAULT_CONFIG=false`, `USE_SPRING_CLOUD_CONFIG=false`, `EUREKA_ENABLED=false`, y `VECTOR_DB_TYPE=milvus` apuntando al Milvus real ya usado en P-08.
  - Se agregó el alias `EUREKA_CLIENT_SERVICEURL_DEFAULTZONE` a `eureka_server_url` (convención Spring Boot), para interoperar con `company-secrets`/ambientes compartidos con microservicios Java que ya usan ese nombre de variable.
- **Verificación real** (no solo lectura de código): se probaron 3 casos con `Settings`/`get_settings()` aislados de variables de entorno del shell (`env -i`) — (1) sin `USE_VAULT_CONFIG`: `is_vault_configured()` devuelve `False` y `get_settings()` carga correctamente todo desde el `.env` del repo (`vector_db_type=milvus`, `debug=True`, etc.); (2) `USE_VAULT_CONFIG=true` sin credenciales: falla con `ValueError: Missing Vault environment variables: VAULT_ADDR, VAULT_TOKEN`, tal como se esperaba; (3) `EUREKA_CLIENT_SERVICEURL_DEFAULTZONE=http://eureka-server:8761/eureka/` resuelve correctamente `eureka_server_url`.
- **Efecto colateral encontrado y corregido:** al revisar `.gitignore` para confirmar que `.env` quedaba excluido, se encontró que la línea `.github` (sin más calificación) excluía **todo el directorio `.github/`**, incluyendo `.github/workflows/ci.yml` creado en P-18 — ese archivo nunca podría haberse subido a git, dejando el pipeline de CI/CD inexistente en la práctica pese a estar creado en disco. Se quitó esa línea de `.gitignore`. Ver P-18 para el detalle de qué falta para confirmar que el pipeline corre en un GitHub Actions real.
- **Redundancia encontrada y corregida (2026-08-11, validación pedida por el usuario de `config.py`/`vault.py`/`eureka.py`):** `Settings` tenía dos campos — `app_name` y `eureka_app_name` — que apuntaban al **mismo** `validation_alias` (`EUREKA_APP_NAME`) con el **mismo** default (`"ai-rag-service-manager"`); por construcción siempre iban a tener el mismo valor, nunca podían divergir. `EurekaRegistrar` usaba `eureka_app_name` en 3 lugares mientras el resto del código (`main.py`, `health_controller.py`, `config_server.py`) ya usaba `app_name` para el mismo propósito. Se eliminó el campo duplicado `eureka_app_name` y se migró `EurekaRegistrar` a usar `settings.app_name` directamente. Verificado: `Settings()` ya no expone `eureka_app_name`, y `EurekaRegistrar` sigue resolviendo el nombre correctamente desde `app_name`. Revisión completa de aliases (script que agrupa todos los `AliasChoices` de `config.py` por variable de entorno) confirma que no queda ningún otro alias reclamado por dos campos distintos. Los pares `EUREKA_SERVER_URL`/`EUREKA_SERVER`, `EUREKA_REGISTER_MAX_RETRIES`/`REGISTER_MAX_RETRIES`, etc. (un alias con prefijo `EUREKA_` y otro genérico) **no son redundancia** — es el mismo patrón de interoperabilidad con `company-secrets`/variables compartidas entre microservicios que ya se usa en todo el archivo, no una duplicación accidental.

### P-18 — Adopción del estándar corporativo de calidad/seguridad

- **Estado:** Resuelto (parcial)
- **Detectado:** 2026-08-10.
- **Resuelto (parcial) el:** 2026-08-10.
- **Ubicación:** originalmente `ESTANDAR_MICROSERVICIO_PYTHON.md` (raíz del repo); el 2026-08-10 su contenido se migró a la sección ["Estándar de calidad, seguridad y arquitectura"](./README.md#estándar-de-calidad-seguridad-y-arquitectura) del README y el archivo se eliminó para no mantener dos copias. Las referencias `§N` de esta entrada apuntan a esa sección del README.
- **Descripción:** El documento es un estándar corporativo de 36 secciones para microservicios Python (calidad, seguridad, arquitectura, CI/CD). Es internamente coherente y razonable — no tiene contradicciones ni requisitos exóticos —, pero está escrito pensando en un microservicio con base de datos relacional, cache y autenticación federada (SQLAlchemy, PostgreSQL, Redis, Keycloak/OIDC), que **no es el caso de `ai-rag-service-manager` hoy** (persistencia en memoria, sin auth — ambas exclusiones ya documentadas en el README). El resto (calidad de código, pruebas, seguridad de dependencias, Docker, CI/CD, health checks, logging) **sí aplica** independientemente del stack de persistencia.
- **Por qué "parcial" y no "resuelto":** se instalaron, configuraron y dejaron en verde todas las herramientas automatizables desde este entorno, se corrigió cada hallazgo real que arrojaron, se agregó el pipeline de CI/CD y Correlation ID. Lo que **no** se hizo, deliberadamente, por ser decisiones de mayor alcance o requerir infraestructura fuera de este entorno: escribir la suite de tests (P-07, requiere diseño de casos, no un fix mecánico), subir Python a 3.12 (cambia la imagen base y el runtime desplegado), y confirmar en un pipeline real de GitHub Actions que los jobs corren (aquí solo se validó que los comandos y el YAML son correctos).

**Instalación y verificación de cada herramienta (2026-08-10):**

| Herramienta | Antes | Después | Detalle |
|---|---|---|---|
| **Ruff** (lint) | No instalado en `.venv` (se había armado con `--no-dev`); no evaluado con la versión real del proyecto | `ruff check .` → **0 errores** | Se instaló vía `uv sync --extra dev`. Al refrescar `uv.lock` (necesario para resolver el resto de vulnerabilidades, ver pip-audit abajo), Ruff subió de `0.15.12` a `0.16.2`, que activa por defecto reglas nuevas (`BLE001`, `G202`, `B008`, `I001`, `UP017`, `PLR0402`, `TRY004`) y volvió a encontrar 25 errores. Se corrigieron todos: 6 `logger.exception(..., exc_info=True)` redundantes, 1 `ValueError`→`TypeError` en `storage_config.py` (tipo de excepción correcto para un chequeo de tipo), 6 `except Exception` en fronteras de integración externa (Spring Config, Eureka, GCS) documentados con `# noqa: BLE001` + razón (ya logueaban correctamente, no eran silenciosos), 3 `File(...)` como default de FastAPI reconocidos como patrón válido vía `[tool.ruff.lint.flake8-bugbear].extend-immutable-calls`, y el resto (`I001`, `UP017`, `PLR0402`) con `ruff check . --fix`. Se excluyeron los `.md` de la raíz (`extend-exclude`) porque Ruff ≥ 0.16 también formatea bloques de código embebidos en Markdown y por poco reformatea `ESTANDAR_MICROSERVICIO_PYTHON.md` (documento de referencia, no código propio). |
| **Ruff** (formato) | 18 de 36 archivos sin formatear | `ruff format --check .` → **0 archivos pendientes** | `ruff format .` aplicado. |
| **mypy** | No era dependencia del proyecto | `mypy` → **0 errores en 33 archivos** | Se agregó `mypy>=1.13.0,<2.0.0` como dev dep y `[tool.mypy]` con la config mínima del estándar, con dos ajustes documentados en el propio `pyproject.toml`: `python_version = "3.11"` (sigue al Dockerfile real, no al `"3.12"` literal del estándar) y `explicit_package_bases = true` (sin esto, mypy fallaba con `Duplicate module named "rag_service"` porque la mayoría de `app/` no tiene `__init__.py` y hay 4 archivos con ese nombre en carpetas distintas). Se corrigieron los 14 errores reales que aparecieron: 6 funciones sin anotación de retorno, 1 uso de `**kwargs: object` contra un `TypedDict` de Pydantic (se cambió a `Unpack[ConfigDict]`, PEP 692), y 5 parámetros `service: StorageServiceDep = None` en `storage_controller.py` (se resolvió con parámetros keyword-only `*,` en vez de forzar un tipo `| None` que no reflejaba la realidad). |
| **Bandit** | No era dependencia del proyecto | `bandit -r app/` → **0 issues** | Se agregó como dev dep. Encontró 1 Medium (`B104`, bind a `0.0.0.0` en `app_host`) — excepción aceptada y documentada inline (`# nosec B104` + comentario con la razón): el servicio corre en Docker y necesita aceptar conexiones desde fuera de su namespace de red, no es una exposición accidental. |
| **pip-audit** | No era dependencia del proyecto | 22 vulnerabilidades → **1 restante** | Se agregó como dev dep. El primer run encontró 22 vulnerabilidades conocidas en 7 paquetes (`cryptography`, `idna`, `pyasn1`, `pydantic-settings`, `python-multipart`, `pytest`, `starlette`). `uv lock --upgrade` (respeta los rangos ya declarados en `pyproject.toml`, no los cambia) resolvió 21 de las 22. La única restante es `pytest 8.4.2` (fix en `9.0.3`, un major bump bloqueado a propósito por el pin `<9.0.0`): no se subió sin poder correr una suite real que confirme compatibilidad (hoy no hay tests, ver P-07), y el riesgo de explotación es nulo (herramienta de desarrollo, no corre en producción). |
| **Gitleaks** | No corría en ningún lado | `gitleaks detect` (imagen oficial `zricethezav/gitleaks`, sin instalar nada local) → **9 commits escaneados, 0 leaks** | No es un paquete Python; se corrió vía Docker. Agregado también como job en `.github/workflows/ci.yml` (`gitleaks/gitleaks-action`). |
| **Trivy** | No corría en ningún lado | Ver detalle abajo | Igual que Gitleaks, corrido vía imagen oficial `aquasec/trivy` contra la imagen ya construida. |
| **pytest-cov** | No era dependencia del proyecto | Instalado, `pytest --cov=app --cov-report=term-missing` corre y reporta cobertura (`0%`, esperado sin tests) | Agregado como dev dep para que el comando de coverage de la sección 18 sea real, no aspiracional. |

**Trivy — hallazgo real de mayor volumen, resuelto parcialmente:** el primer escaneo contra la imagen construida (`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`, sin actualizar) encontró **10 CRITICAL / 40 HIGH** en paquetes del sistema operativo Debian (openssl, libssl3, perl-base, zlib1g, libgnutls30, libsqlite3-0, entre otros) y **3 HIGH** en paquetes Python del propio tooling de build (`jaraco.context`, `wheel` — no son dependencias declaradas del proyecto, vienen del bootstrap de `pip`/`uv` en la imagen base). Se agregó `apt-get update && apt-get upgrade -y` al Dockerfile (antes de copiar la app) para tomar los parches Debian ya publicados al momento del build. Un subconjunto de las vulnerabilidades del SO no tiene fix disponible todavía en el repositorio Debian (`fix: -` en el reporte de Trivy, ej. varias del paquete `util-linux`/`libblkid`, `ncurses`, y `zlib1g` marcada explícitamente `will_not_fix` upstream) — esas quedan como riesgo aceptado hasta que Debian publique parche, no como algo accionable desde este repo.
- **Estado exacto post-fix** (rescan con la imagen ya reconstruida, `docker build --no-cache`): el `apt-get upgrade` bajó el hallazgo de SO de **10 CRITICAL/40 HIGH → 6 CRITICAL/18 HIGH** (resolvió `libcap2`, `libgnutls30`, `libssl3`/`openssl`, que sí tenían paquete parchado disponible). Lo que queda (Perl, util-linux/libblkid, ncurses, sqlite3, `zlib1g`) muestra `fix: -` en el reporte de Trivy para cada CVE restante — Debian **todavía no publicó parche** para esas versiones específicas (excepto `zlib1g`/`CVE-2023-45853`, marcada explícitamente `will_not_fix` upstream). No es accionable desde este repo hoy: no hay una versión más nueva del paquete Debian a la que subir. Los 2 hallazgos Python (`jaraco.context`, `wheel`, 3 HIGH) **no son dependencias de este proyecto** — se verificó que viven vendorizadas dentro de `setuptools` en `/usr/local/lib/python3.11/site-packages/setuptools/_vendor/`, parte de la instalación de Python del sistema que trae la imagen base `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`, no de `uv.lock` ni de `pyproject.toml`. Corregirlas requeriría que la imagen base upstream actualice su `setuptools` vendorizado; forzar un upgrade manual de esos paquetes del sistema en el Dockerfile es frágil (podría romper el propio `uv`) y se descartó como fix para esta pasada.
- **Riesgo aceptado documentado:** las 6 CRITICAL + 21 HIGH restantes de Trivy (18 de SO sin fix disponible + 3 de Python vendorizadas en la imagen base) quedan como excepción aceptada siguiendo el proceso de la sección 35 del estándar — motivo: sin fix upstream disponible o fuera del árbol de dependencias del proyecto; revisar en cada actualización de la imagen base o cuando Debian/el vendor publiquen parche.

**Otros hallazgos corregidos durante esta pasada (fuera del checklist de herramientas):**

- `app/services/storage_service.py:45` y `:154` (`upload_file`, `upload_public_file`): tenían `except Exception: return ...Response(success=False)` sin loguear nada — funcionalmente equivalente al `except: pass` que el estándar prohíbe explícitamente en la sección 9. Se agregó `logger.exception(...)` en ambos casos.
- **Docker (§26):** se agregó usuario no-root (`useradd --uid 1000 appuser` + `USER appuser`) y `.dockerignore`. Verificado con un build + `docker run ... id` real: el contenedor corre como `uid=1000(appuser)`, no root, y puede escribir en `logs/` (directorio creado y con `chown` correcto durante el build).
- **Correlation ID (§23):** implementado `CorrelationIdMiddleware` (`app/core/middleware.py`) + `CorrelationIdFilter`/`ContextVar` (`app/core/logging.py`). Lee `X-Correlation-ID` del request entrante o genera un UUID, lo expone en `request.state.correlation_id`, lo inyecta en cada línea de log de esa request (consola y archivo) y lo devuelve en el header de respuesta. Probado con `TestClient`: sin header entrante genera uno nuevo y lo propaga a logs+respuesta; con header entrante lo respeta; fuera de una request el `ContextVar` vuelve a su default (`"-"`). No se propaga todavía a las llamadas salientes (Config Server, Eureka, GCS) — ver "Acción sugerida".
- **CI/CD (§31/§32):** creado `.github/workflows/ci.yml` con jobs de Ruff, mypy, Bandit, pip-audit, pytest (`continue-on-error` hasta que exista P-07), build de Docker + Trivy, y Gitleaks. El job de SonarQube está definido pero deshabilitado (`if: false`) porque `sonar.host.url` en `sonar-project.properties` apunta a un servidor interno (`ediaidev.softwarecumbre.com:9000`) cuya alcanzabilidad desde runners hosteados por GitHub no está confirmada. **No se pudo verificar que el pipeline corra en GitHub Actions real** (este entorno no tiene forma de disparar un workflow run) — solo se validó que el YAML es sintácticamente correcto y que cada comando referenciado (`ruff`, `mypy`, `bandit`, `pip-audit`, `pytest --cov`) efectivamente corre y produce el resultado esperado en local.

**Ya cubierto por otros pendientes de este documento** (no duplicar esfuerzo, solo referenciar): P-07 (tests/coverage — sigue pendiente, es la única pieza de código no abordada aquí), P-13 (autenticación, exclusión intencional documentada en README), P-17 (`.env` no auto-cargado, relacionado con la sección 28).

**Secciones que corresponde marcar como "No aplica"**, dado el alcance actual documentado en el README (no bug, decisión de producto): §29 Base de datos (SQLAlchemy/Alembic — no hay DB relacional), §30 Redis (no se usa), §11 Keycloak/OIDC completo (no hay auth), §25 OpenTelemetry (exclusión intencional).

**Tabla final de cumplimiento por sección:**

| Sección del estándar | Estado |
|---|---|
| §3 Python 3.12+ | No cumple (3.11) — decisión pendiente, no abordada en esta pasada |
| §4 Ruff (0 errores, sin pendientes de formato) | **Cumple** |
| §5 mypy | **Cumple** |
| §13 Bandit (High=0) | **Cumple** |
| §15 pip-audit | Parcial (1 vulnerabilidad restante, aceptada y justificada — ver tabla arriba) |
| §16 Gitleaks | **Cumple** (0 leaks; agregado también a CI) |
| §17 SonarQube Quality Gate | Parcial (config existe; job de CI creado pero deshabilitado hasta confirmar conectividad al server interno) |
| §18 Pruebas (coverage ≥ 80%) | No cumple (0%, ver P-07 — no abordado en esta pasada) |
| §22 Logging (no silenciar errores) | **Cumple** |
| §23 Correlation ID | **Cumple** (falta propagar a llamadas salientes, ver acción sugerida) |
| §26 Docker (usuario no-root, `.dockerignore`) | **Cumple** |
| §27 Trivy | Parcial — ver detalle de Trivy arriba |
| §31/§32 Pipeline CI/CD | Parcial (definido y con comandos verificados en local; no verificado corriendo en GitHub Actions real) |
| §6 Arquitectura por capas | **Cumple** (ya evaluado en el README) |
| §7 API REST + OpenAPI | **Cumple** |
| §8 Validación con Pydantic | **Cumple** |
| §12 Gestión de secretos (Vault) | **Cumple** |
| §14 Lock de dependencias | **Cumple** (`uv.lock`) |
| §20 Timeouts en llamadas externas | **Cumple** |
| §24 Health checks live/ready | **Cumple** (P-14) |
| §28 Variables de entorno separadas del código | **Cumple** |

- **Impacto:** el microservicio pasó de no tener ninguna herramienta de calidad/seguridad ejecutable a tener las 6 corriendo en 0 (o con excepciones documentadas) desde `pyproject.toml`, más un pipeline de CI/CD definido. Lo que falta para considerar el estándar "cumplido" en sentido estricto es acotado: tests reales (P-07), decidir sobre Python 3.12, y confirmar el pipeline en un runner real.
- **Acción sugerida (lo que queda):** (1) escribir la suite de tests de P-07 y quitar `continue-on-error` del job de pytest en CI; (2) decidir upgrade a Python 3.12 (afecta Dockerfile, `requires-python` y `[tool.mypy].python_version` a la vez); (3) push a un repo real de GitHub para confirmar que `ci.yml` corre correctamente en Actions; (4) resolver o aceptar formalmente las vulnerabilidades de Trivy que sí tienen fix disponible pero no se resolvieron con el `apt-get upgrade` inicial (ver nota de seguimiento); (5) si se necesita trazabilidad completa entre microservicios, propagar `X-Correlation-ID` en las llamadas salientes de `ConfigServerClient`, `EurekaRegistrar` y `StorageClient`.
- **Corrección 2026-08-11 (encontrada al resolver P-17):** `.gitignore` tenía una línea `.github` que excluía **todo** el directorio, incluyendo `.github/workflows/ci.yml` creado en esta misma entrada — el archivo nunca podría haberse commiteado, dejando el punto (3) de arriba literalmente imposible de cumplir hasta ahora. Se quitó esa línea; `git status` ya lo ve como archivo normal listo para `git add`.

### P-19 — Imagen Docker creció por embeddings locales (torch + sentence-transformers + pymilvus)

- **Estado:** Pendiente
- **Detectado:** 2026-08-11, al implementar P-04/P-08.
- **Ubicación:** `pyproject.toml` (dependencias core), `Dockerfile`.
- **Descripción:** Resolver P-04 (embeddings reales) requiere `sentence-transformers`, que arrastra `torch` como dependencia. El wheel de PyPI de `torch` trae CUDA completo por defecto (~5.4GB de `.venv`) aunque el servicio está configurado para CPU (`RAG_EMBEDDING_DEVICE=cpu`); se mitigó fijando `torch` contra el índice CPU-only oficial de PyTorch (`[tool.uv.sources]`/`[[tool.uv.index]]` en `pyproject.toml`), lo que bajó el `.venv` a ~1.6GB. La imagen final construida (con parches de SO de P-18 incluidos) pesa **2.82GB**.
- **Impacto:** Imagen notablemente más pesada que antes de esta integración (previamente sin ninguna dependencia de ML). Tiempos de build/pull más largos, más superficie para Trivy (nuevas dependencias de sistema que puedan traer los paquetes de ML). No es un bug — es el costo real de embeddings locales de calidad razonable — pero vale la pena que quede como decisión consciente y no un efecto secundario no documentado.
- **Mitigaciones ya aplicadas:** build-time pre-download del modelo default + `HF_HUB_OFFLINE=1` en runtime (evita descargas/verificaciones de red en cada arranque, ver Dockerfile); `torch` fijado a CPU-only (evita ~4GB de librerías CUDA innecesarias).
- **Acción sugerida:** si el tamaño de imagen se vuelve un problema operativo (tiempos de deploy, costo de registry, cold-start en autoscaling), evaluar alternativas más livianas: (a) un proveedor de embeddings por API (OpenAI, Cohere, Voyage — quita `torch`/`sentence-transformers` del todo, cambia el trade-off a latencia de red + costo por request); (b) modelos ONNX-only sin el runtime completo de `sentence-transformers`/`transformers` (más liviano pero más trabajo de integración); (c) separar el servicio de embeddings en un microservicio aparte si varios servicios lo van a reutilizar. Ninguna de estas se implementó — la decisión actual (local, CPU, `sentence-transformers`) fue la que pidió explícitamente el usuario.
- **Nota de auditoría (relacionado con P-18/pip-audit):** `pip-audit` no puede verificar `torch` porque se resuelve desde el índice CPU-only de PyTorch, no desde PyPI estándar (`torch==2.13.0+cpu` no tiene match en la base de datos de vulnerabilidades por ese sufijo de version). Es un "skip", no una vulnerabilidad confirmada ni descartada — si se necesita auditoría real de `torch`, hay que verificarlo manualmente contra los avisos de seguridad de PyTorch.
