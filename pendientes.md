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
| P-09 | `InMemoryRagServiceRepository` sin persistencia real | Baja | Resuelto |
| P-10 | `storage-upload-vectorization` sin integrar (marcado en código) | Baja | Resuelto |
| P-11 | `storage-chunk-consolidation` sin integrar (marcado en código) | Baja | Resuelto |
| P-12 | Acoplamiento import-time con Vault en `app/schemas/embedding.py` | Baja | Resuelto |
| P-13 | CORS abierto (`*`) + `allow_credentials` sin autenticación | Baja | Resuelto (parcial) |
| P-14 | `/health/ready` nunca refleja fallas reales de dependencias | Baja | Resuelto |
| P-15 | Inconsistencia camelCase/snake_case entre `rag-services` y `embedding`/`storage` | Baja | Resuelto |
| P-16 | `/storage/chunk` no declara sus campos como `Form()`, no aparece bien en OpenAPI | Baja | Resuelto |
| P-17 | `Settings` no carga `.env` automáticamente pese a lo que dice el README | Baja | Resuelto |
| P-18 | Adopción del estándar corporativo de calidad/seguridad (CI/CD, mypy, Bandit, pip-audit, Gitleaks, Trivy, coverage) | Media | Resuelto (parcial) |
| P-19 | Imagen Docker creció ~1.6GB por embeddings locales (torch + sentence-transformers + pymilvus) | Baja | Pendiente |
| P-20 | `id_document` incompatible: Java manda `String` (=`uniqueCode`), Python exige `int` | Alta | Resuelto |
| P-21 | `list_parameters` incompatible: Java manda `{code,value}`, Python solo reconoce `{key,value}` (pérdida silenciosa de datos) | Alta | Resuelto |
| P-22 | Falta endpoint para borrar un documento individual del índice (Java lo usa hoy vía `deleteEmbeddingDocument`) | Media | Resuelto |
| P-23 | Falta endpoint liviano de listado por namespace equivalente a `getListUniqueCodeDocuments` de Java | Baja | Resuelto |
| P-24 | Migrar `edi-ai-proyectos-backend` (Java) para consumir `/storage/*` y `/embedding/*` de `ai-rag-service-manager` en vez de GCS local + `analysis-ai-service` | Media | Resuelto (parcial) |
| P-25 | Nombres de colección con caracteres inválidos para Milvus (ej. `project-42`) no se sanitizaban | Alta | Resuelto |
| P-26 | Borrado de registros en Milvus (`delete_records`) no era visible de inmediato para queries subsiguientes (faltaba `flush`) | Media | Resuelto |
| P-27 | Embeddings solo soportaban `sentence-transformers` local; faltaba la API real de OpenAI (`text-embedding-3-large`, ya productiva en `edi-ai-analysis-ai`) | Media | Resuelto |
| P-28 | Integrar `edi-ai-operator` con `ai-rag-service-manager`: tool nueva de búsqueda semántica para el agente + migrar el storage propio (GCS directo) al storage centralizado del RAG | Media | Resuelto (parcial) |
| P-29 | `search_similar_documents` devolvía `results[].text_preview` en `snake_case`, inconsistente con el resto de la API (`camelCase`) | Baja | Resuelto |
| P-30 | `RAG_OPENAI_EMBEDDING_DIMENSIONS=""` rompía el arranque con Vault (`int \| None` no acepta string vacío) | Media | Resuelto |

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
- **Actualizado 2026-08-11 (ver P-27):** este modelo local ahora es solo una de dos opciones (`RAG_EMBEDDING_PROVIDER=local`); el default pasó a ser la API real de OpenAI (`text-embedding-3-large`, `RAG_EMBEDDING_PROVIDER=openai`), por continuidad con el modelo ya productivo en `edi-ai-analysis-ai`.
- **Impacto en imagen Docker:** agrega `torch`+`sentence-transformers`+`pymilvus` como dependencias core — ver P-19.

### P-05 — No hay integración LLM real en `rag_query`

- **Estado:** Pendiente
- **Detectado:** 2026-08-10
- **Ubicación:** `app/services/rag/rag_agent.py` (`answer_with_context`).
- **Descripción:** `POST /api/v1/embedding/rag_query` siempre responde `answer: "LLM integration pending. Retrieved context returned."`.
- **Impacto:** El endpoint no genera respuestas basadas en LLM, solo retorna contexto recuperado y fuentes.
- **Acción sugerida:** conectar `RAGAgent` con un cliente LLM real, con el proveedor/modelo resuelto desde `Settings` (env vars), igual que el resto de la configuración del servicio. **Actualizado 2026-08-11:** el catálogo `rag-services` que originalmente se pensó como fuente de ese proveedor/modelo se eliminó por no tener consumidor (ver P-09) — no depender de él en la solución de este pendiente.

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

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-11
- **Ubicación (eliminada):** `app/domain/entities/rag_service.py`, `app/domain/repositories/rag_service_repository.py`, `app/infrastructure/repositories/in_memory_rag_service_repository.py`, `app/services/rag_service.py`, `app/schemas/rag_service.py`, `app/api/routes/rag_services_controller.py`, y su wiring en `app/api/router_controller.py`/`app/api/dependencies/services.py`.
- **Descripción:** Las definiciones de `rag-services` (CRUD completo: nombre, proveedor LLM, modelo de chat/embeddings, backend vectorial, estado) vivían solo en memoria del proceso, sin persistencia real.
- **Análisis antes de decidir cómo resolverlo:** se verificó si algo consumía este catálogo. Resultado: **nada lo consume**. Ni el flujo real de embeddings dentro de este mismo servicio (`DocumentEmbeddingService`/`RAGService`/`RAGAgent` reciben `indexVecstore`/modelo/backend directo en cada request o desde `Settings`, nunca desde un `RagService` guardado) ni `edi-ai-proyectos-backend` (grep completo del repo Java: cero referencias a `/rag-services*`). Era un CRUD administrativo bien capeado (dominio/repositorio/servicio/controller separados correctamente) pero desconectado del resto del sistema — scaffolding para un futuro modelo multi-configuración que nunca se conectó a lógica real.
- **Decisión:** en vez de elegir un motor de persistencia para código sin consumidor (lo que además habría requerido revisar la exclusión intencional de ORM/SQLAlchemy y Alembic del README), se **eliminó el feature completo** por no tener uso. `app/domain/` quedó vacío y se eliminó también (ya no queda capa de dominio en el servicio — se actualizó la sección "Arquitectura" del README en consecuencia). El puerto `RagServiceRepository` seguía siendo la abstracción correcta si este catálogo vuelve a ser necesario; queda en el historial de git, no en el código activo.
- **Verificación real:** `ruff`/`mypy` limpios tras el borrado; se levantó la app (`uvicorn`) y se confirmó por `openapi.json` que `/api/v1/rag-services*` ya no existe (`404`) y que el resto de rutas (`health`, `embedding`, `storage`) sigue registrado sin cambios.
- **Impacto:** Ninguno funcional — no había consumidores. Se redujo superficie de código muerto y una futura fuente de confusión (una API que aparentaba estar completa pero no hacía nada).

### P-10 — `storage-upload-vectorization` sin integrar

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/services/storage_service.py` (`upload_file`, `VectorizationTrigger`, `_resolve_vectorization_index`, `_vectorize_uploaded_file`); `app/api/routes/storage_controller.py` (`_vectorization_trigger_form`); `app/schemas/storage.py`.
- **Descripción:** En el micro Java origen (`edi-ai-proyectos-backend`, `StorageManager.uploadFile`), un upload exitoso dispara vectorización automática de forma condicional: solo si `codeTypeDocument` está presente y pertenece a una lista configurable de tipos vectorizables (`ParameterCommonService`, parámetro `is_vectorizable`). Esa continuación no se migró a `ai-rag-service-manager`.
- **Análisis con el código Java real** (ver `integracion-java-storage.md`): el trigger real de Java depende de un parámetro de BD fuera del alcance de este servicio; **no hace falta ningún callback HTTP de vuelta hacia Java** (Java ya resuelve su propio estado con la respuesta síncrona de `/embedding/save_document_vecstore` dentro de su propia tarea async); la colección vectorial real es `project-{idProject}` (una por proyecto), no `codeTypeDocument`.
- **Solución aplicada:** `/storage/upload` acepta ahora `uniqueCode`, `idDocument` (opcionales) además de los campos ya existentes. Trigger: `uploadContentBucket=true` + `uniqueCode` presente (más simple que replicar la regla de negocio de Java, que vive en su propia BD). Colección: `project_{projectId}` si llega `projectId` (ver P-25 sobre el guión bajo), si no `codeTypeDocument`, si no el default global. Ejecución en `BackgroundTask` con `asyncio.to_thread` (no bloquea el event loop durante el cómputo de embeddings); `UploadFileResponse` no cambia — la vectorización es best-effort, sin callback, solo logueada. Los 5 campos nuevos (`codeTypeDocument`, `uploadContentBucket`, `uniqueCode`, `idDocument`, `background_tasks`) se agruparon en un dataclass `VectorizationTrigger` para no violar el límite de parámetros por función (regla Sonar S107); en el controller, `BackgroundTasks` se resuelve vía una sub-dependencia de FastAPI (`_vectorization_trigger_form`) por el mismo motivo.
- **Verificación real (no simulada):** se levantó la app completa (`TestClient` + Milvus real en `localhost:19530` + modelo de embeddings real) mockeando solo `StorageClient.upload_bytes` (la única dependencia no disponible en este sandbox: credenciales GCS reales). `POST /storage/upload` con `uploadContentBucket=true`, `projectId=42`, `uniqueCode=TEST-P10-0001` devolvió `{"success": true}`; tras la respuesta, la colección `project_42` se creó en Milvus y el documento quedó indexado y recuperable vía `get_embeddings_by_unique_code`, con `code_type_document` correctamente presente en la metadata (no como nombre de colección).

### P-11 — `storage-chunk-consolidation` sin integrar

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/services/storage_service.py` (`store_chunk`, `_collect_ordered_parts`, `_consolidate_chunks`, `_cleanup_upload`); `app/schemas/storage.py` (`ChunkUploadResponse`).
- **Descripción:** Los chunks subidos se persistían en disco local (`STORAGE_CHUNK_UPLOAD_TEMP_DIR`), pero no había consolidación final (merge), subida a GCS del archivo ensamblado, ni limpieza post-commit.
- **Solución aplicada:** consolidación automática, en la misma request que recibe la última parte (no en background — el merge en disco es rápido, a diferencia de la vectorización): cuando el conteo de `.part` en disco iguala `totalChunks`, se concatenan en orden numérico, se sube el archivo resultante a GCS (reusando `StorageClient.upload_bytes`) y se limpia el directorio temporal + archivo índice (limpieza best-effort, no tumba una consolidación ya exitosa si falla). `/storage/chunk` ganó los mismos campos opcionales que `/storage/upload` (`codeTypeDocument`, `uploadContentBucket`, `uniqueCode`, `idDocument`) para poder disparar la misma vectorización una vez consolidado — mismo `VectorizationTrigger`/`_resolve_vectorization_index` reusados de P-10. El endpoint pasó de devolver `200` con cuerpo vacío a devolver `ChunkUploadResponse {consolidated, success}` — cambio de contrato documentado en `api.md` y `integracion-java-storage.md`.
- **Limitación conocida, aceptada:** si la última parte se reintenta después de una consolidación ya exitosa, queda un directorio residual con una parte huérfana — no rompe nada, no se autolimpia. No se construyó un mecanismo de idempotencia distribuida completo para esto.
- **Verificación real:** mismo setup que P-10 (Milvus real, GCS mockeado). Se subieron 3 partes de un archivo fragmentado vía `POST /storage/chunk`: las dos primeras devolvieron `{"consolidated": false, "success": true}`, la última `{"consolidated": true, "success": true}`. Tras la última parte, el directorio temporal y el archivo índice ya no existían (limpieza confirmada), y el documento quedó indexado en Milvus (`project_77`) con la metadata correcta.

### P-12 — Acoplamiento import-time con Vault en `app/schemas/embedding.py`

- **Estado:** Resuelto
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/schemas/embedding.py` (`ListDocumentsRequest.limit`, `SearchSimilarDocumentsRequest.top_k`, `RagQueryRequest.top_k`).
- **Descripción:** El módulo ejecutaba `settings = get_settings()` a nivel de módulo para usar `settings.rag_default_list_limit`/`settings.rag_default_top_k` como default de tres campos. Importar el módulo disparaba resolución completa de `Settings` (y, con `USE_VAULT_CONFIG=true`, una llamada real a Vault) solo por importar un archivo de schemas.
- **Impacto:** Rompía testabilidad unitaria aislada (no se podía importar schemas sin Vault/Settings resuelto) y acoplaba una capa de contratos HTTP a infraestructura de secretos, sin necesidad real — el valor solo hace falta cuando efectivamente se construye un request.
- **Solución aplicada:** se eliminó el `settings = get_settings()` a nivel de módulo. Los tres campos ahora usan `Field(default_factory=lambda: get_settings().rag_default_list_limit, ...)` (y equivalente para `top_k`) — la resolución de `Settings` queda diferida a cuando efectivamente se construye una instancia del schema (por request), no al importar el módulo. `get_settings()` sigue siendo `@lru_cache`, así que el costo real de resolución solo se paga una vez independientemente de dónde se invoque.
- **Verificación real:** se importó `app.schemas.embedding` con `get_settings` monkeypercheado para lanzar una excepción si se llama — el import terminó sin errores, confirmando que ya no se invoca en tiempo de import. Luego, con `get_settings` real, se construyeron instancias de los tres schemas y se confirmó que los defaults siguen resolviendo correctamente (`limit=100`, `top_k=5`) y que un valor explícito en el request sigue pisando el default (`limit=7`).

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
- **Nota 2026-08-11:** el feature `rag-services` completo (incluyendo `app/schemas/rag_service.py`, mencionado arriba) se eliminó al resolver P-09 por no tener ningún consumidor. Esta entrada queda como registro histórico de la decisión tomada mientras el feature existió.

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

---

## Pendientes de integración con `edi-ai-proyectos-backend` (Java)

Detectados el 2026-08-11 al analizar el código real de `edi-ai-proyectos-backend` (`StorageManager.java`, `VectorStoreServiceImpl.java`, `VectorStoreMapper.java`, `SaveFileVecstoreRequest.java`) para planear la migración de storage/vectorización de Java hacia `ai-rag-service-manager`. Detalle completo, con fragmentos de código y diagramas de flujo, en [`integracion-java-storage.md`](./integracion-java-storage.md).

### P-20 — `id_document` incompatible: Java manda `String`, Python exige `int`

- **Estado:** Resuelto
- **Detectado:** 2026-08-11
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/schemas/embedding.py` (`SaveDocumentVecstoreRequest.id_document`); `app/services/embedding/document_embedding_service.py` (`save_document_to_vecstore`); `api.md`. Java: `SaveFileVecstoreRequest.idDocument` (`String`, seteado por `VectorStoreMapper` al mismo valor que `uniqueCode`, no a un ID numérico real).
- **Descripción:** Java no tiene un `idDocument` numérico separado — usa el mismo string que `uniqueCode` (`uploadFileRequest.name()`). El schema Python exigía `id_document: int`, sin default.
- **Impacto:** Era bloqueante real para la integración: si Java mandaba su `idDocument` string tal cual, `ai-rag-service-manager` respondía `422` antes de indexar nada.
- **Solución aplicada:** `id_document` cambiado a `str` en `SaveDocumentVecstoreRequest` (`app/schemas/embedding.py`) y en la firma de `DocumentEmbeddingService.save_document_to_vecstore` — el método solo usaba `id_document` como valor de metadata, sin aritmética, así que el cambio de tipo no tocó ninguna otra lógica. Actualizado también `api.md`.
- **Verificación real:** se construyó un `SaveDocumentVecstoreRequest` con el payload exacto que arma `VectorStoreMapper` en Java (`idDocument="DOC-2026-0001"`, igual a `uniqueCode`) — valida correctamente y `id_document` queda como `str`.

### P-21 — `list_parameters` incompatible: Java manda `{code,value}`, Python solo reconoce `{key,value}`

- **Estado:** Resuelto
- **Detectado:** 2026-08-11
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/services/embedding/document_embedding_service.py` (`_normalize_parameters`); `api.md`. Java: `ParametersDTO` (campos `code`/`value`, confirmado leyendo la clase — no `key`/`value`).
- **Descripción:** `_normalize_parameters` solo reconocía el patrón `{"key": ..., "value": ...}`; cualquier otra forma caía al `else: metadata.update(item)`. Como Java manda `{"code": "VECTOR_CHUNK_SIZE", "value": "1000"}` y luego `{"code": "VECTOR_CHUNK_OVERLAP", "value": "200"}`, ambas entradas se aplanaban bajo las mismas claves literales `"code"`/`"value"` — la segunda pisaba a la primera silenciosamente.
- **Impacto:** No era un error visible (no lanzaba excepción) — era **pérdida silenciosa de datos**. Los parámetros de chunking que Java mandaba no llegaban a la metadata del vector tal como se esperaba.
- **Solución aplicada:** se agregó una rama `elif "code" in item and "value" in item: metadata[str(item["code"])] = item["value"]` en `_normalize_parameters`, antes del fallback genérico — acepta `{code, value}` como alias de `{key, value}`, sin tocar el formato original ni requerir cambios en Java.
- **Verificación real:** se llamó a `_normalize_parameters` con el payload exacto de `StorageManager` (`VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP` vía `{code, value}`) — resultado `{"VECTOR_CHUNK_SIZE": "1000", "VECTOR_CHUNK_OVERLAP": "200"}`, ambos parámetros distintos, sin pisarse. Se confirmó además que el formato original `{key, value}` sigue funcionando igual que antes (compatibilidad hacia atrás).

### P-22 — Falta endpoint para borrar un documento individual del índice

- **Estado:** Resuelto
- **Detectado:** 2026-08-11
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/infrastructure/vector_store/vector_store_interface.py`/`vector_store_manager.py`/`milvus_vector_store.py` (`delete_records`), `app/services/rag/rag_service.py` (`RAGService.delete_records`), `app/services/embedding/document_embedding_service.py` (`delete_document`), `app/schemas/embedding.py` (`DeleteDocumentVecstoreRequest`/`Response`), `app/api/routes/embedding_controller.py` (`POST /embedding/delete_document`).
- **Descripción:** `ai-rag-service-manager` solo podía borrar la colección completa (`/embedding/delete_index_vecstore`). Java tiene un caso de uso real de borrar un solo documento sin afectar el resto del índice (`VectorStoreService.deleteEmbeddingDocument(indexVecstore, idDocument)`).
- **Solución aplicada:** se agregó `delete_records(collection_name, filter_conditions)` al contrato `VectorStoreInterface`, implementado en ambos backends (memoria: filtra y reconstruye la lista; Milvus: `MilvusClient.delete` con expresión de filtro, reutilizando `_build_filter_expression`, ya validado contra inyección de filtro). Se expuso un endpoint nuevo `POST /embedding/delete_document`, síncrono (a diferencia de `delete_index_vecstore`, que es `BackgroundTask` por ser potencialmente más costoso), que filtra por `id_document`. El `DeleteDocumentVecstoreRequest` (`{indexVecstore, idDocument}`) es **compatible byte a byte** con el `DeleteEmbeddingRequest` que Java ya arma hoy — no requiere cambiar cómo Java construye el request, solo repuntar la URL.
- **Verificación real:** contra Milvus real (no en memoria): se indexaron dos documentos en una colección, se borró uno por `idDocument` (`deletedCount: 1`), se confirmó que el otro documento seguía intacto y que el borrado no afectaba el resto de la colección. Este mismo test destapó P-26 (ver abajo).
- **Impacto:** Ya no bloquea repuntar `deleteEmbeddingDocument` en Java a `ai-rag-service-manager`.

### P-23 — Falta endpoint liviano de listado por namespace

- **Estado:** Resuelto
- **Detectado:** 2026-08-11
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/services/embedding/document_embedding_service.py` (`list_unique_code_documents`), `app/schemas/embedding.py` (`UniqueCodeDocumentResponse`), `app/api/routes/embedding_controller.py` (`POST /embedding/list_unique_code_documents`), `app/core/config.py` (`rag_unique_code_list_limit`, default 10000).
- **Descripción:** `/embedding/list_documents` ya cubría este caso de uso conceptualmente, pero con una forma de request/response distinta a la que espera Java (`VectorStoreService.getListUniqueCodeDocuments(namespace)` → `List<Metadata{namespace, codigo, fileName, id, nombreDocumento}>`, con el namespace mandado como string JSON plano, no un objeto).
- **Solución aplicada:** se agregó un endpoint dedicado que replica el contrato exacto de Java: acepta un **body string JSON plano** (no un objeto envolvente) y devuelve un **array JSON plano** (no una respuesta envuelta con `success`/`message`) de objetos `{namespace, codigo, fileName, id, nombreDocumento}` — mismos nombres de campo que la clase `Metadata` de Java gracias al alias generator camelCase ya existente. Se optó deliberadamente por replicar la forma "rara" del contrato de Java (string plano en vez de objeto) para que el repunte en Java sea **solo un cambio de URL de configuración**, sin tocar cómo arma el request ni cómo deserializa la respuesta. `codigo`/`fileName` se completan con `unique_code`/`file_name` del payload (los únicos dos campos que el código Java real (`VectorStoreManager.getDocumentsByType`) efectivamente lee de `Metadata`); `nombreDocumento` repite `fileName` porque no existe hoy un concepto de "nombre de documento" separado del nombre físico del archivo; `id` usa el id del chunk/registro.
- **Verificación real:** contra Milvus real, con dos documentos indexados en una colección, `POST /embedding/list_unique_code_documents` con body `"<nombre-coleccion>"` devolvió ambos, deduplicados por `unique_code`, con los 5 campos esperados y en camelCase.
- **Impacto:** Ya no bloquea repuntar `getListUniqueCodeDocuments` en Java a `ai-rag-service-manager`.

### P-26 — Borrado en Milvus no era visible de inmediato para queries subsiguientes

- **Estado:** Resuelto
- **Detectado:** 2026-08-11, verificando P-22 end-to-end contra Milvus real.
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/infrastructure/vector_store/milvus_vector_store.py` (`MilvusVectorStore.delete_records`).
- **Descripción:** al implementar `delete_records`, la primera versión llamaba a `MilvusClient.delete(...)` (que respondía con `delete_count: 1`, aparentando éxito) pero una consulta inmediatamente después (`list_records`) seguía devolviendo el registro borrado. Con ~3 segundos de espera entre el borrado y la consulta, el registro sí desaparecía — el mismo patrón de eventual consistency por el que `insert_vectors` ya llama a `client.flush()` para que lo insertado sea buscable de inmediato, pero que no se había replicado para `delete`.
- **Impacto:** Sin este fix, `POST /embedding/delete_document` reportaría éxito (`success: true`, `deletedCount: 1`) pero el documento seguiría apareciendo en búsquedas/listados inmediatamente después — inconsistencia silenciosa, análoga en severidad a P-21 (dato incorrecto sin excepción visible).
- **Solución aplicada:** se agregó `client.flush(collection_name)` después de `client.delete(...)` en `MilvusVectorStore.delete_records`, igual que ya hace `insert_vectors`.
- **Verificación real:** se repitió el test de P-22 sin ningún `sleep` entre el borrado y el listado subsiguiente — el documento borrado ya no aparecía.

### P-24 — Migrar `edi-ai-proyectos-backend` (Java) para consumir `ai-rag-service-manager`

- **Estado:** Resuelto (parcial)
- **Detectado:** 2026-08-11
- **Avance el:** 2026-08-11
- **Ubicación:** `edi-ai-proyectos-backend`: `RagServiceConfigProperties` (nuevo), `RagServiceStorageClient` (nuevo), `StorageServiceImpl` (marcada `@Primary`), `VectorStoreServiceImpl` (repuntado, ya sin `OpenAiConfigProperties`), `application.yml`/`application-dev.yml`.
- **Descripción:** Iniciativa de integración de más alto nivel que agrupa P-20 a P-23: Java subía archivos directo a GCS (sin pasar por `ai-rag-service-manager`) y vectorizaba contra un servicio distinto (`analysis-ai-service:7002`, contrato `/documents/*`).
- **Lo que quedó activo (cambia comportamiento real):**
  - Los cuatro métodos de vectorización de `VectorStoreServiceImpl` (`saveEmbeddingFile`, `deleteIndexVecstore`, `deleteEmbeddingDocument`, `getListUniqueCodeDocuments`) están repuntados a `app.rag-service.*` en vez de `app.openai.*`. Los últimos dos se cerraron el 2026-08-11 al resolver P-22/P-23 en `ai-rag-service-manager` — con esos endpoints ya disponibles, el repunte fue solo cambiar la URL de configuración, sin tocar cómo Java arma el request ni deserializa la respuesta (ver `integracion-java-storage.md` secciones 4 y 5.2). El campo `openaiConfig` (y su import) se eliminaron de la clase por quedar sin uso — verificado con `./gradlew compileJava`/`compileTestJava`/`assemble`.
- **Lo que quedó implementado pero NO activo (decisión deliberada, no un olvido):**
  - `RagServiceStorageClient` — nueva implementación de `StorageService` que llama a `/api/v1/storage/*` de `ai-rag-service-manager`, contrato completo (`uploadFile` con y sin `UploadFileRequest`, `getFile`, `getFileBytes`, `uploadPublicFile`). `StorageServiceImpl` (GCS directo) se marcó `@Primary` para seguir siendo el bean activo — cambiar `StorageManager` a inyectar el cliente nuevo (vía `@Qualifier`) es una decisión de corte aparte, no ejecutada aquí, porque implica credenciales/datos reales de storage y este microservicio Java no se pudo levantar ni probar end-to-end desde este entorno.
- **Verificación real:** `./gradlew compileJava`, `compileTestJava` y `assemble` (build completo del jar) exitosos tras todos los cambios. No se pudo verificar en runtime (arrancar el contexto de Spring, hacer una llamada real) — limitación del entorno, no algo que quedó sin intentar por descuido.
- **Impacto:** Ya no bloquea nada del lado `ai-rag-service-manager` (P-10/P-11/P-20/P-21/P-25 resueltos). Queda: confirmar el hostname real de `ai-rag-service-manager` en cada ambiente, probar en dev, y decidir cuándo cortar el storage al nuevo cliente.
- **Hallazgos colaterales, reportados sin corregir (fuera de alcance de esta tarea):** el repo Java tiene un merge sin resolver en `src/main/resources/edward-creds.json` (no se tocó), y `application.yml`/`application-dev.yml` tienen secretos reales en texto plano versionados en git (client secret de Keycloak, password de email, token de Webex) — preexistente, no introducido por este cambio.
- **Acción sugerida:** ver `integracion-java-storage.md` sección 7 para el checklist actualizado y el detalle completo de qué falta.

### P-25 — Nombres de colección con caracteres inválidos para Milvus no se sanitizaban

- **Estado:** Resuelto
- **Detectado:** 2026-08-11, probando P-10 end-to-end contra Milvus real.
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/services/rag/rag_service.py` (`_resolve_collection_name`, nueva `_sanitize_collection_name`).
- **Descripción:** Milvus solo acepta letras, números y guion bajo en nombres de colección (rechaza con `MilvusException code=1100` cualquier otro carácter, incluyendo guiones). `_resolve_collection_name` nunca validó ni saneó el nombre recibido — funcionaba con el backend en memoria (P-08, cualquier string servía de key de dict) pero nunca se probó contra Milvus real hasta ahora. La convención real del micro Java origen para nombres de colección es `project-{idProject}` (con guion) — exactamente el patrón que P-10 empezó a generar y que rompió contra Milvus real en la primera prueba end-to-end.
- **Impacto:** Sin este fix, **cualquier** `index_vecstore`/colección con guiones, espacios, puntos u otro carácter no-ASCII-alfanumérico fallaba en cualquier operación (`create_collection`, `search`, `list_records`, etc.) con una excepción de Milvus no manejada — no solo el caso de P-10, sino cualquier llamada a `/embedding/*` con un `indexVecstore` que contuviera esos caracteres (por ejemplo, si Java llega a mandar `"project-42"` literal como `indexVecstore` en `/embedding/save_document_vecstore`).
- **Solución aplicada:** `_sanitize_collection_name` en `RAGService` reemplaza cualquier carácter fuera de `[0-9a-zA-Z_]` por `_` (usando `\W` con `re.ASCII` para no dejar pasar letras unicode, que Python trata como "word chars" pero Milvus no acepta), y antepone `_` si el resultado empieza con dígito. Se aplica tanto al nombre de colección como al prefijo (`rag_collection_name_prefix`) antes de combinarlos. Es un fix central en `RAGService`, no solo en el código nuevo de P-10 — protege cualquier caller de `/embedding/*`, incluyendo la futura integración real de Java.
- **Verificación real:** `_sanitize_collection_name('project-42')` → `'project_42'`; con espacios/puntos (`'mi coleccion.v2'`) → `'mi_coleccion_v2'`; empezando con dígito (`'42-cosas'`) → `'_42_cosas'`. Confirmado además indirectamente por las pruebas end-to-end de P-10/P-11 (colecciones `project_42`/`project_77` creadas y usadas correctamente en Milvus real).
- **Nota para integración Java:** documentado en `integracion-java-storage.md` — el nombre de colección que Java construya como `"project-{id}"` va a llegar sanitizado a `"project_{id}"` en Milvus; no hace falta que Java cambie su convención, pero el nombre real en Milvus difiere ligeramente (guion → guion bajo) de lo que Java arma internamente.

### P-27 — Embeddings vía API real de OpenAI (además del modelo local)

- **Estado:** Resuelto
- **Detectado:** 2026-08-11, a pedido explícito: usar el mismo modelo de embeddings que ya es productivo en `edi-ai-analysis-ai` (`text-embedding-3-large`, vía `OpenAIEmbeddings` de langchain, dimensión 3072 — ver `edi-ai-analysis-ai/EMBEDDINGS_Y_BUSQUEDA_VECTORIAL.md` sección 1).
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/infrastructure/embeddings/embedding_provider.py` (reescrito con dos backends), `app/core/config.py` (`rag_embedding_provider`, `openai_api_key`, `rag_openai_embedding_dimensions`), `pyproject.toml` (dependencia `openai`, y `numpy<2.5.0` — ver nota aparte abajo), `.env`/`.env.example`, `Dockerfile` (comentarios).
- **Descripción:** Antes de este cambio, `EmbeddingProvider` estaba hardcodeado a `sentence-transformers` local (resultado de P-04). Se pidió agregar la API real de OpenAI como opción, configurable por variable de entorno, con OpenAI como default (no el local) porque ya es el modelo productivo del servicio que este microservicio reemplaza.
- **Solución aplicada:** `EmbeddingProvider` ahora delega en uno de dos backends internos según `RAG_EMBEDDING_PROVIDER` (`openai` default | `local`): `_OpenAIEmbeddingBackend` (cliente oficial `openai`, modelo `RAG_EMBEDDING_MODEL`, default `text-embedding-3-large`) y `_LocalEmbeddingBackend` (el `SentenceTransformerEmbeddingFunction` que ya existía, sin cambios de comportamiento). La dimensión del vector (necesaria para crear la colección en el vector store) se resuelve sin llamar a la API: tabla de dimensiones nativas conocidas para los modelos de OpenAI soportados (`text-embedding-3-large`=3072, `text-embedding-3-small`=1536, `text-embedding-ada-002`=1536), con `RAG_OPENAI_EMBEDDING_DIMENSIONS` como override explícito (también permite pedirle a la API un vector truncado vía el parámetro `dimensions`, solo soportado por los modelos v3, para bajar costo/almacenamiento). Falla rápido y con mensaje claro en el constructor (no en el primer request real) si: falta `OPENAI_API_KEY` con provider `openai`, el modelo no está en la tabla de dimensiones conocidas y no hay override, o el valor de `RAG_EMBEDDING_PROVIDER` no es `openai`/`local`.
- **Seguridad:** la API key y la key de Pinecone que se compartieron como ejemplo de la config vieja quedaron expuestas en la conversación — se le indicó al usuario rotarlas de inmediato y no se escribió esa key literal en ningún archivo del repo ni en `.env`. `.env` local quedó con `OPENAI_API_KEY=` vacío, pendiente de que el usuario pegue una key nueva directamente en el archivo.
- **Verificación real:** `ruff`/`mypy` limpios. Backend OpenAI verificado con el cliente mockeado (sin key real, sin llamadas de red): dimensión default 3072, override de `RAG_OPENAI_EMBEDDING_DIMENSIONS` respetado end-to-end, y los tres casos de error (key faltante, modelo desconocido sin override, provider inválido) fallan con el mensaje esperado. Backend local verificado real (carga el modelo real, dim=384, igual que antes de este cambio). Se levantó la app completa con el `.env` real (provider `openai`, sin key todavía): arranca sin error (la construcción de `EmbeddingProvider` es lazy, no ocurre en el startup), y `/embedding/save_document_vecstore` responde `500` con el mensaje claro de `OPENAI_API_KEY` faltante — no un traceback opaco. **No se pudo verificar una llamada real a la API de OpenAI** (sin una key vigente disponible en este entorno que no fuera la comprometida) — pendiente de que el usuario la pruebe con una key real.
- **Nota colateral (hallazgo, no pedido):** agregar `openai` como dependencia rompió `mypy` (no `ruff`) con un error de sintaxis en el stub empaquetado de `numpy>=2.5` (usa `type X = ...`, sintaxis PEP 695, incompatible con `python_version=3.11` configurado en `[tool.mypy]`). `pymilvus`/`sentence-transformers` no disparaban este problema porque `pymilvus.*` está en la lista de `ignore_missing_imports` — `openai` sí tiene stubs propios y por eso mypy sigue sus imports, incluida su dependencia opcional de `numpy` (helpers de audio, sin relación con embeddings). Se fijó `numpy<2.5.0` como dependencia explícita (antes era 100% transitiva) hasta que P-18 suba el proyecto a Python 3.12.
- **Pendiente relacionado (ver también P-04):** el modelo default (`text-embedding-3-large`) se eligió por continuidad con el sistema que se reemplaza, no por una evaluación propia de calidad de retrieval — igual que ya estaba anotado para el modelo local.

### P-28 — Integrar `edi-ai-operator` con `ai-rag-service-manager`

- **Estado:** Resuelto (parcial) — código base implementado y verificado; faltan dos piezas de contenido/DB que no se pueden completar desde este repo (ver abajo).
- **Detectado:** 2026-08-11.
- **Avance el:** 2026-08-11.
- **Ubicación:** análisis completo en [`integracion-operator-rag.md`](./integracion-operator-rag.md). Código en `edi-ai-operator` (rama `dev`): `src/service/rag/rag_service_client.py` (nuevo), `src/agents/deep_insight_engine/tools/rag_document_search.py` (nuevo), `src/agents/deep_insight_engine/tools/tools_registry.py` (registrada), `src/agents/deep_insight_engine/tools/company_document_query.py` (migrado), `src/agents/deep_insight_engine/prompts_constants.py` (`PromptTemplate.RAG_DOCUMENT_SEARCH`), `src/service/report/cache_service.py` (mensajes de progreso), `.env` (`RAG_SERVICE_BASE_URL`).
- **Investigación previa a implementar (resolvió las dos preguntas abiertas originales):**
  - **Mapeo de proyecto:** confirmado por código (no solo inferido) que `parameters["company_id"]` (= `planning_input.project.id`, construido en `build_parameters`, `deep_insight_utils.py:730`) es el mismo `id_project`/`projectId` que entra a la API (`src/api/deep_insight_engine/request.py`, campo requerido `projectId`). El schema de `edi-ai-operator` tiene `database/entities/document.py` con `unique_code`, `id_project`, `is_vectorized` — mismos campos que la entidad `Document` de Java — evidencia fuerte de que comparten el mismo espacio de IDs de proyecto, aunque no se confirmó que sea literalmente la misma instancia de Postgres (hosts distintos en los `.env` revisados). **Se implementó sobre esta asunción**; queda como riesgo a confirmar con el equipo antes de un ambiente real.
  - **Quién indexa:** no se encontró ningún pipeline de indexación activo en `edi-ai-operator` (`dev`) — se asume que Java ya indexa vía P-10, y esta tool solo busca. No se implementó indexación nueva en `edi-ai-operator`.
- **Lo que quedó implementado y activo:**
  - `rag_service_client.py`: `search_similar_documents()` y `download_file()`, únicos puntos de entrada HTTP a `ai-rag-service-manager` desde este repo.
  - Tool `rag_document_search`, registrada en `TOOLS_REGISTRY`. Resuelve la colección como `project_{company_id}`, llama a `search_similar_documents`, arma contexto y sintetiza respuesta con `invoke_model` — mismo patrón que `company_document_query`.
  - `company_document_query.py` migrado: ya no usa `StorageService` (GCS directo) para descargar documentos de la empresa, usa `rag_service_client.download_file`.
  - **API de simulación** (`POST /rag-document-search/simulate`, mismo patrón que la de `company_document_query`): `src/api/rag_document_search/` (request/response/controller), `src/service/rag_document_search/rag_document_search_simulation_service.py`, wiring en `src/api/dependencies.py` y `src/api/routes.py`. Llama a la tool real con `company_id`+`query`, sin pasar por moderator/planner/selector de tools — pensada exactamente para lo que se pidió: poder probar la tool aislada antes de validarla integrada al agente completo.
- **Lo que NO se pudo completar (bloqueantes de contenido/DB, no de código):**
  - El LLM (`invoke_model`) resuelve el prompt de cada tool desde una tabla `CatPrompt` en la base de datos, por `(nombre, id_project)` (`prompt_config_service.get_prompt_by_type`). `PromptTemplate.RAG_DOCUMENT_SEARCH` no tiene fila correspondiente todavía — sin eso, la tool falla en runtime al intentar construir el mensaje. Es contenido/prompt-engineering, no algo que deba inventarse sin el equipo. **El usuario indicó que se encarga de crear esta fila.**
  - Que un "worker" del agente pueda seleccionar esta tool (`name_tool_implemented`) también es configuración en base de datos (`cat_tools`/`tools_implemented`, consumida vía `team_members_by_area`) — hace falta una fila nueva ahí para que el agente pueda elegirla en runtime. Tampoco se puede completar desde código.
  - **Hallazgo adicional, no introducido por esta integración:** `build_placeholders` (`src/agents/deep_insight_engine/prompt_utils.py:38`) busca el prompt con `parameters.get("id_company", None)`, pero la clave real que se puebla en todo el sistema es `company_id` — nunca `id_company`. Esto significa que el lookup de prompt **siempre** resuelve con `id_project=None`, para las 13 tools del registry, no solo para esta. **Consecuencia práctica para cuando se cree la fila de `CatPrompt`: debe tener `id_project = NULL` (global), no scoped a un proyecto específico, o nunca se va a encontrar.** Es un bug preexistente y transversal — no se corrigió aquí por su alcance (afecta a todas las tools), solo se documenta.
- **Verificación real (no simulada, dos rondas):**
  1. Se instaló el entorno de `edi-ai-operator` (`uv pip install -e ".[dev]"`), se corrigió un bug de entorno (`uv` apuntaba al `.venv` de otro proyecto por una variable `VIRTUAL_ENV` residual), se formateó con `black`, y se corrió un import-check real de todo el grafo de módulos tocados (sin mocks) — pasa limpio. Se levantó `ai-rag-service-manager` real (Milvus real, `RAG_EMBEDDING_PROVIDER=local`), se indexó un documento de prueba en `project_999`, y se llamó la función real del cliente de `edi-ai-operator` (`rag_service_client.search_similar_documents`) y las funciones internas de la tool contra ese servicio real — funcionó de punta a punta. Esto destapó P-29 (ver abajo).
  2. Con la API de simulación ya construida, se llamó `RagDocumentSearchSimulationService.simulate(70, None)` **contra la base de datos Postgres real de `edi-ai-operator`** (proyecto real, id 70, "Event Express", consultado directo con SQL para confirmarlo) y contra `ai-rag-service-manager` real: encontró el proyecto, resolvió `indexVecstore=project_70`, ejecutó la búsqueda semántica real, y se detuvo exactamente en el punto esperado (`KeyError` por la fila de `CatPrompt` faltante) — confirmando con precisión el único bloqueante real restante, y destapando el bug de `id_company`/`company_id` de paso. No se probó el flujo de storage migrado en `company_document_query.py` (requiere credenciales GCS reales) ni la tool integrada al agente completo (requiere las dos filas de DB).
- **Pendiente para continuar (checklist actualizado, ver también `integracion-operator-rag.md`):**
  - [ ] Confirmar con el equipo que `company_id` = mismo `idProject` que Java (ver arriba).
  - [ ] Agregar la fila de `CatPrompt` para `rag_document_search`, **con `id_project = NULL`** (ver hallazgo del bug `id_company`/`company_id` arriba) — a cargo del usuario.
  - [ ] Agregar la fila de worker/tool (`cat_tools`/`tools_implemented`) para que el agente pueda seleccionar la tool — a cargo del usuario.
  - [ ] Una vez creadas esas filas, volver a correr `POST /rag-document-search/simulate` para confirmar `200` con respuesta real del LLM.
  - [ ] Migrar el resto de consumidores de `StorageService` (`thought_persistence_service.py`, `chat_history_service.py`, `context_memory_service.py`, `comun_service.py`, y los no revisados en detalle) — solo se migró `company_document_query.py` en esta pasada.
  - [ ] Probar `rag_document_search` integrada al agente completo (moderator/planner/selector de tools) una vez resueltas las filas de DB.
- **Nota histórica:** existe una rama divergente en `edi-ai-operator` (`embedding`, no fusionada a `dev`, commit `1dfcf78`) con un prototipo previo de RAG embebido (`rag_service.py`, `vector_store_manager.py`, mismas variables de entorno que hoy tiene `ai-rag-service-manager`) — es, literalmente, el antecesor de este mismo microservicio. Se abandonó ahí antes de conectarse a ninguna tool, al decidir extraerlo a un servicio separado.

### P-29 — `search_similar_documents` devolvía `text_preview` en snake_case dentro de `results[]`

- **Estado:** Resuelto
- **Detectado:** 2026-08-11, probando P-28 end-to-end: `edi-ai-operator` esperaba `textPreview` (documentado en `api.md`) pero recibía `text_preview`.
- **Resuelto el:** 2026-08-11
- **Ubicación:** `app/schemas/embedding.py` (`SearchSimilarDocumentsResponse.results`).
- **Descripción:** `results` estaba tipado como `list[dict[str, Any]]` — un dict libre, no un modelo Pydantic. `get_camel_case_config()` en el modelo contenedor (`SearchSimilarDocumentsResponse`) solo convierte los *campos* del propio modelo a camelCase; no toca las claves de un `dict[str, Any]` anidado. El dict se armaba en `document_embedding_service.py` con la clave Python literal `text_preview`, que salía tal cual en el JSON — inconsistente con el resto de la API (`list_documents`, que sí usa un modelo tipado, `DocumentSummaryResponse`, y sí sale en camelCase).
- **Impacto:** Cualquier consumidor que confiara en `api.md` (que documenta camelCase para toda la API) y buscara `textPreview` no encontraba el campo. Encontrado al integrar `edi-ai-operator`, que construyó su cliente contra la documentación, no contra una prueba real.
- **Solución aplicada:** se cambió `results: list[dict[str, Any]]` a `results: list[DocumentSummaryResponse]` — el mismo modelo que ya usa `list_documents` y que tiene exactamente los mismos campos (`id`, `score`, `metadata`, `text_preview`) que ya armaba `search_similar_documents`. Cero cambios en `document_embedding_service.py`: al ser un modelo Pydantic con `get_camel_case_config()`, la serialización a `textPreview` es automática.
- **Verificación real:** se indexó un documento real en Milvus, se llamó `POST /embedding/search_similar_documents`, y se confirmó que la clave en la respuesta cambió de `text_preview` a `textPreview` sin ningún otro cambio en el payload. Verificado también desde el lado consumidor (`edi-ai-operator`'s `rag_service_client.search_similar_documents`, ver P-28).

### P-30 — `RAG_OPENAI_EMBEDDING_DIMENSIONS=""` rompía el arranque leyendo config desde Vault

- **Estado:** Resuelto
- **Detectado:** 2026-08-12, arranque real con `USE_VAULT_CONFIG=true` contra un Vault real: `pydantic_core.ValidationError: Input should be a valid integer, unable to parse string as an integer [...] input_value=''`.
- **Resuelto el:** 2026-08-12
- **Ubicación:** `app/core/config.py` (`Settings.rag_openai_embedding_dimensions`, campo `int | None`).
- **Descripción:** en `.env`, un valor "sin definir" para este campo se resuelve dejando la línea comentada — la key ni siquiera llega al proceso, y `Settings` usa el default `None`. Vault (y cualquier fuente de config que no pueda "omitir" una key, solo mandarla vacía) no tiene ese mecanismo: si la key existe en el secret con valor `""`, `Settings(**config)` recibe literalmente `rag_openai_embedding_dimensions=""`, y pydantic intenta parsearlo como `int` y falla — tumba el arranque completo del servicio, no solo el embedding provider.
- **Impacto:** Cualquier despliegue con Vault que incluyera esta key vacía (recomendada así en el JSON de referencia armado en esta misma conversación) no podía arrancar en absoluto — `ValidationError` en `create_app()`, antes de que el servidor HTTP levante.
- **Solución aplicada:** `field_validator("rag_openai_embedding_dimensions", mode="before")` que convierte `""` a `None` antes de la validación de tipo. Es el único campo `int | None` de `Settings` (confirmado por grep), no hizo falta un mecanismo genérico para otros campos.
- **Verificación real:** `Settings(rag_openai_embedding_dimensions="")` → `None`; `Settings(rag_openai_embedding_dimensions="256")` → `256` (un valor real sigue funcionando); `Settings()` sin la key → `None` (default, sin cambios). `ruff`/`mypy` limpios.
- **Nota:** no hizo falta que el usuario quite la key de Vault — con este fix, dejarla en `""` es válido y equivalente a omitirla.

