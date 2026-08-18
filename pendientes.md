# Pendientes — ai-rag-service-manager

Registro de trazabilidad de hallazgos detectados durante la revisión del microservicio. No reemplaza al README: aquí se documentan brechas, riesgos y deuda técnica, con su estado de resolución.

Cómo usarlo:

- Cada hallazgo tiene un ID estable (`P-XX`). No reutilizar IDs.
- Al resolver un pendiente, cambiar `Estado` a `Resuelto`, agregar `Resuelto el` y una línea `Solución aplicada`.
- Agregar hallazgos nuevos al final de su sección de prioridad, no reordenar los existentes.

Última actualización: 2026-08-12.

## Resumen de estado

| ID | Título | Prioridad | Estado |
|----|--------|-----------|--------|
| P-01 | SSRF sin validar en `url_download_file` | Alta | Resuelto |
| P-02 | `/storage/public-upload` roto (falta `storage_public_bucket_name`) | Alta | Resuelto |
| P-03 | README no documenta `storage_controller` | Alta | Resuelto |
| P-04 | Embeddings no son reales (hash determinístico) | Media | Resuelto |
| P-05 | No hay integración LLM real en `rag_query` | Media | Resuelto (por eliminación) |
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
| P-19 | Imagen Docker creció ~1.6GB por embeddings locales (torch + sentence-transformers + pymilvus) | Baja | Resuelto (OpenAI-only, backend local eliminado; imagen 2.82GB→580MB) |
| P-20 | `id_document` incompatible: Java manda `String` (=`uniqueCode`), Python exige `int` | Alta | Resuelto |
| P-21 | `list_parameters` incompatible: Java manda `{code,value}`, Python solo reconoce `{key,value}` (pérdida silenciosa de datos) | Alta | Resuelto |
| P-22 | Falta endpoint para borrar un documento individual del índice (Java lo usa hoy vía `deleteEmbeddingDocument`) | Media | Resuelto |
| P-23 | Falta endpoint liviano de listado por namespace equivalente a `getListUniqueCodeDocuments` de Java | Baja | Resuelto |
| P-24 | Migrar `edi-ai-proyectos-backend` (Java) para consumir `/storage/*` y `/embedding/*` de `ai-rag-service-manager` en vez de GCS local + `analysis-ai-service` | Media | Resuelto |
| P-25 | Nombres de colección con caracteres inválidos para Milvus (ej. `project-42`) no se sanitizaban | Alta | Resuelto |
| P-26 | Borrado de registros en Milvus (`delete_records`) no era visible de inmediato para queries subsiguientes (faltaba `flush`) | Media | Resuelto |
| P-27 | Embeddings solo soportaban `sentence-transformers` local; faltaba la API real de OpenAI (`text-embedding-3-large`, ya productiva en `edi-ai-analysis-ai`) | Media | Resuelto |
| P-28 | Integrar `edi-ai-operator` con `ai-rag-service-manager`: tool nueva de búsqueda semántica para el agente + migrar el storage propio (GCS directo) al storage centralizado del RAG | Media | Resuelto |
| P-29 | `search_similar_documents` devolvía `results[].text_preview` en `snake_case`, inconsistente con el resto de la API (`camelCase`) | Baja | Resuelto |
| P-30 | `RAG_OPENAI_EMBEDDING_DIMENSIONS=""` rompía el arranque con Vault (`int \| None` no acepta string vacío) | Media | Resuelto |
| P-31 | Java/operator propagaban su propio nombre de bucket en vez de dejar que `ai-rag-service-manager` resuelva el suyo | Media | Resuelto |
| P-32 | Integrar `edi-ai-chat-backend` (microservicio nuevo en el workspace): quitar GCS directo y config de storage propia, dejar plumbing para consumir `ai-rag-service-manager` | Media | Resuelto |
| P-33 | Documento "Mapeo Pinecone→Milvus" propone Namespace→Partition; no coincide con el diseño real. Ampliado con evidencia real de Pinecone en producción; se implementó `RAG_ENVIRONMENT` (edi-local/edi-dev/edi-stage/edi-prod) como **partición real de Milvus** dentro de la colección de cada proyecto (colección = proyecto solo, sin concatenar) | Media | Resuelto (partición real de Milvus) |
| P-34 | `DELETE .../resources/{resourceId}/documents/delete/{documentId}` (Java) inactiva el documento en Postgres pero no borra su vector en Milvus | Alta | Resuelto |
| P-35 | `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP`/`VECTOR_K_SIMILILARITY` (parámetros configurables de Java, aplicados en `edi-ai-analysis-ai`) no se aplican en `ai-rag-service-manager` | Media | Resuelto (parcial) |
| P-36 | La condición para vectorizar un documento no considera `resources_type.code = 'data_base_embedding'` — solo mira `codeTypeDocument` | Alta | Resuelto |
| P-37 | `VECTOR_K_SIMILILARITY` (uso completo) y "adjacent chunks" (expansión de contexto) en `edi-ai-analysis-ai` — no replicado en `ai-rag-service-manager` ni en `rag_document_search`; además `text_preview` trunca a 200 caracteres | Media | Resuelto |
| P-38 | `_DEFAULT_TOP_K`/`_PREVIEW_TOP_K` hardcodeados en `edi-ai-operator`/`rag_document_search` — no usan la tabla `parameters`/`ConfigKey` ya existente en ese mismo repo | Media | Resuelto |
| P-39 | `_extract_text_from_file` para PDF hacía `decode("latin-1")` de los bytes crudos en vez de extraer texto real — descubierto en la primera prueba E2E real (Java→RAG→operator) con un PDF real | Alta | Resuelto |

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

- **Estado:** Resuelto (por eliminación) — decisión explícita de alcance del usuario, 2026-08-12: "el requisito y objetivo del microservicio rag es solo gestionar storage y embeddings". No se implementa síntesis con LLM en este repo; queda a cargo de cada consumidor (como ya hace `edi-ai-operator` con `rag_document_search`, ver P-28).
- **Detectado:** 2026-08-10
- **Resuelto el:** 2026-08-12
- **Ubicación (código eliminado):** `app/services/rag/rag_agent.py` (`RAGAgent`, archivo completo), `RagQueryRequest`/`RagQueryResponse` (`app/schemas/embedding.py`), endpoint `POST /api/v1/embedding/rag_query` y `RagAgentDep` (`app/api/routes/embedding_controller.py`), `get_rag_agent()` (`app/api/dependencies/services.py`), setting `rag_agent_collection_name` (`app/core/config.py`, y `RAG_AGENT_COLLECTION_NAME` en `.env`/`.env.example`), y los métodos `retrieve_context`/`answer_question` de `RAGService` (`app/services/rag/rag_service.py`) — quedaron muertos al eliminar su único caller (`RAGAgent`).
- **Descripción:** `POST /api/v1/embedding/rag_query` siempre respondía `answer: "LLM integration pending. Retrieved context returned."` — nunca invocó un LLM real. Al analizar cómo cerrarlo (conectar un LLM real vs. eliminar), surgieron dos hallazgos que motivaron la eliminación en vez de la implementación:
  1. **Ningún consumidor lo llama.** Grep completo en `edi-ai-operator` y `edi-ai-proyectos-backend`: cero referencias a `rag_query`/`rag-query`. La tool `rag_document_search` del operator (la única integración RAG real y probada end-to-end, ver P-28) no lo usa — hace su propio retrieval vía `search_similar_documents` y su propia síntesis vía su LLM/prompt (`invoke_model` + `CatPrompt`) del lado operator.
  2. **Gap estructural adicional, no solo el LLM:** `RagQueryRequest` no tenía `index_vecstore`/`project_id` — el agente se armaba una sola vez (`@lru_cache`) contra una colección fija (`rag_agent_collection_name`, default `"company_knowledge_base"`), incompatible con el modelo multi-tenant por proyecto (`project_{id}`) que usa el resto de la API (`search_similar_documents`, etc.).
- **Decisión:** en vez de invertir en conectar un LLM + resolver el gap de multi-tenancy para un endpoint sin consumidores, se confirmó con el usuario el alcance real del microservicio (solo storage + embeddings, ya cubierto por el resto de la API) y se eliminó el código en vez de dejarlo implementado sin uso.
- **Verificación real:** `ruff check .` y `mypy app` limpios tras la eliminación. Import real de `app.main:app` (no solo sintaxis) y del `openapi()` generado: `/api/v1/embedding/rag_query` ya no aparece en las rutas ni en el spec; el resto de endpoints de `embedding`/`storage` siguen intactos.
- **Documentación actualizada:** `README.md` (diagrama de arquitectura, componentes clave, exclusiones intencionales, lista de endpoints), `api.md` (sección del endpoint y tabla resumen), `integracion-java-storage.md` (diagrama TO-BE y snippet de config de la sección 5.2 — Java nunca llegó a adoptar una URL `rag-query` en su config real, confirmado por grep contra `application.yml`/`application-dev.yml`).

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

- **Estado:** Resuelto — decisión de negocio (2026-08-18): usar exclusivamente `RAG_EMBEDDING_PROVIDER=openai`/`RAG_EMBEDDING_MODEL=text-embedding-3-large`. Se implementó la opción (a) que ya estaba sugerida en este mismo pendiente ("un proveedor de embeddings por API... quita torch/sentence-transformers del todo").
- **Detectado:** 2026-08-11, al implementar P-04/P-08.
- **Resuelto el:** 2026-08-18.
- **Ubicación:** `pyproject.toml`, `Dockerfile`, `app/infrastructure/embeddings/embedding_provider.py`, `app/core/config.py`.
- **Descripción original:** Resolver P-04 (embeddings reales) había agregado `sentence-transformers`, que arrastraba `torch` como dependencia. Se había mitigado fijando `torch` contra el índice CPU-only oficial de PyTorch, pero la imagen final igual pesaba **2.82GB**.
- **Implementación (2026-08-18):**
  - **`app/infrastructure/embeddings/embedding_provider.py`:** eliminado `_LocalEmbeddingBackend` (`sentence-transformers`) y el `Protocol`/dispatch multi-backend (ya no hace falta con un solo proveedor) — `EmbeddingProvider` ahora es una única implementación directa contra la API de OpenAI.
  - **`app/core/config.py`:** `rag_embedding_provider` ahora tiene un `field_validator` que **solo acepta `"openai"`** (falla fuerte ante cualquier otro valor, ej. `"local"` de una config vieja sin actualizar — mismo criterio que `RAG_ENVIRONMENT`, ver P-33). Eliminados `rag_embedding_device`/`rag_normalize_embeddings` (solo los usaba el backend local, ahora dead code).
  - **`pyproject.toml`:** eliminadas las dependencias `sentence-transformers` y `torch`; `pymilvus[model]` → `pymilvus` (se quita el extra `[model]`, ya no hace falta `SentenceTransformerEmbeddingFunction`); eliminado el índice `pytorch-cpu`/`[tool.uv.sources]` completo (ya no hay `torch` que fijar a CPU-only).
  - **`Dockerfile`:** eliminado el paso de pre-descarga del modelo local (`RUN uv run python -c "from pymilvus.model.dense import SentenceTransformerEmbeddingFunction..."`), `ENV HF_HUB_OFFLINE=1` y `HF_HOME=/app/.cache/huggingface` (nada de esto aplica sin backend local).
  - **`app/services/rag/rag_service.py`** (hallazgo colateral, ver también P-33 punto 6): `RAGService.__init__` recibía `collection_name: str | None = None` con fallback a `settings.rag_default_collection_name`, pero el único caller real (`DocumentEmbeddingService._get_rag_service`) siempre pasa un `index_name` explícito — el fallback nunca se ejecutaba. Cambiado a `collection_name: str` (obligatorio), eliminando la referencia muerta. **`RAG_DEFAULT_COLLECTION_NAME` se mantiene intacta** para su otro uso real y sí alcanzable en `storage_service.py._resolve_vectorization_index` (fallback cuando un `/storage/upload` llega sin `project_id` ni `code_type_document`) — decisión explícita del usuario tras confirmarse que ese caso sí es reachable en el flujo real de `resources`, aunque el backend ya valida que llegue `code_resource` o `code_type_document` antes de vectorizar.
  - `.env`/`.env.example`/`README.md`/`api.md` actualizados, quitando las menciones al backend local y a `RAG_EMBEDDING_DEVICE`/`RAG_NORMALIZE_EMBEDDINGS`.
- **Verificación real:**
  1. `uv lock` real: removió 25 paquetes del árbol de dependencias (`torch` x2, `sentence-transformers`, `transformers`, `tokenizers`, `scipy`, `scikit-learn`, `onnxruntime`, `sympy`, `networkx`, `pymilvus-model`, etc.).
  2. `.venv` bajó de lo que antes rondaba ~1.6GB a **362MB**.
  3. `ruff check .` y `mypy app` limpios tras el cambio.
  4. Verificación real de que `torch`/`sentence_transformers`/`pymilvus.model` ya no están instalados (`ImportError` confirmado los 3).
  5. `Settings(RAG_EMBEDDING_PROVIDER="local")` lanza `ValidationError` real (falla fuerte, ya no degrada a un backend inexistente).
  6. **Build real de la imagen Docker (`docker build`, no simulado):** imagen final **580MB** (antes 2.82GB — reducción de ~80%). Contenedor real levantado (`docker run`) con `OPENAI_API_KEY` fake: arrancó limpio (`Uvicorn running on http://0.0.0.0:8000`, `Application startup complete`) y respondió a una petición HTTP real (`GET /health/live` → `404` porque el path no era el correcto, pero confirma que el servidor procesa requests reales — no fue necesario dar con el path exacto para validar el objetivo de este pendiente). Contenedor e imagen de prueba eliminados al terminar.
- **Nota de auditoría (ya no aplica):** la excepción de `pip-audit` sobre `torch==...+cpu` (no auditable por el sufijo de versión del índice CPU-only) queda sin efecto — `torch` ya no es una dependencia del proyecto.
- **Acción sugerida:** ninguna — resuelto de fondo (no era una mitigación parcial, se eliminó la causa raíz).

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

- **Estado:** Resuelto
- **Detectado:** 2026-08-11
- **Avance el:** 2026-08-11
- **Resuelto el:** 2026-08-12 — corte de storage completado, a pedido explícito del usuario ("quitar código y referencias de storage en java backend y operator, deben consumir ambos el rag").
- **Ubicación:** `edi-ai-proyectos-backend`: `RagServiceConfigProperties`, `RagServiceStorageClient` (ahora único `StorageService`, `@Service` simple, ya sin `@Primary`), `VectorStoreServiceImpl`, `StorageConfigProperties` (sin `projectId`/`publicBucketName`), `application.yml`/`application-dev.yml` (sin bloque `app.google.jsonCredentials`), `build.gradle`.
- **Descripción:** Iniciativa de integración de más alto nivel que agrupa P-20 a P-23: Java subía archivos directo a GCS (sin pasar por `ai-rag-service-manager`) y vectorizaba contra un servicio distinto (`analysis-ai-service:7002`, contrato `/documents/*`).
- **Corte de storage (2026-08-12) — eliminado, no solo desactivado:**
  - **Borrados:** `StorageServiceImpl.java` (GCS directo), `StorageConfig.java`, `GoogleCloudConfig.java`.
  - `RagServiceStorageClient` pasó a ser la única implementación de `StorageService` (ya no hace falta `@Primary`/`@Qualifier`, no hay ambigüedad de beans).
  - `StorageConfigProperties`: se quitaron `projectId`/`publicBucketName` (muertos sin GCS); se conservó `defaultBucketName` (sigue viajando como valor en los requests a `RagServiceStorageClient`) y `chunkUploadTempDir` (disco local, sin relación con GCS).
  - `application.yml`/`application-dev.yml`: se quitó el bloque `app.google.jsonCredentials` completo y `app.storage.projectId`/`publicBucketName`.
  - `build.gradle`: se quitaron las dos líneas duplicadas de `com.google.cloud:google-cloud-storage` y el `libraries-bom`. Esto rompió compilación en dos puntos que dependían de transitivos de esa BOM sin declararlos explícitamente (`UserAgentDTO.java` vía `@AutoValue`, `BackendServiceApplication.java` vía `javax.annotation.PostConstruct`) — se agregaron como dependencias explícitas `com.google.auto.value:auto-value-annotations:1.10.2` y `javax.annotation:javax.annotation-api:1.3.2` (versiones confirmadas contra lo que ya estaba resuelto transitoriamente, vía caché de Gradle).
  - `ChunkUploadServiceImpl.java` no se tocó: hace consolidación en disco local y llama a `storageManager.uploadFile(...)`, que ahora enruta automáticamente por `RagServiceStorageClient` sin cambios propios.
- **Verificación real:** `./gradlew compileJava`, `compileTestJava` y `assemble` — `BUILD SUCCESSFUL` tras el fix de dependencias transitivas. **No se pudo verificar en runtime** (arrancar el contexto de Spring, ejercitar `/storage/*` con una llamada real end-to-end) — limitación del entorno, no se pudo levantar este microservicio Java desde acá. Sigue siendo la única brecha de verificación de este ítem.
- **Impacto:** Java ya no tiene ninguna dependencia de código ni de librería contra GCS directo — todo el storage pasa exclusivamente por `ai-rag-service-manager`, igual que `edi-ai-operator` (ver P-28).
- **Hallazgos colaterales:** el repo Java tenía un merge sin resolver en `src/main/resources/edward-creds.json` — **corregido por el usuario, 2026-08-13: el archivo fue eliminado del repo** (confirmado, ya no aparece en `git ls-files`). `application.yml`/`application-dev.yml` siguen con secretos reales en texto plano versionados en git (client secret de Keycloak, password de email, token de Webex) — preexistente, no corregido, sigue fuera de alcance salvo instrucción explícita.
- **Acción sugerida:** ver `integracion-java-storage.md` sección 7 para el checklist actualizado. Queda pendiente exclusivamente una prueba en runtime real cuando el usuario pueda levantar el servicio en un ambiente con credenciales/datos reales.

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

- **Estado:** Resuelto — la tool `rag_document_search` está verificada end-to-end de forma aislada (real, con LLM real, ver ronda 3 abajo) y el corte de storage está completo y verificado (ver ronda 4 abajo). La fila de `cat_tools`/`tools_implemented` ya fue creada por el usuario (2026-08-13) — falta solo probar la tool integrada al agente completo (moderator/planner/selector de tools), no bloqueada por código.
- **Detectado:** 2026-08-11.
- **Avance el:** 2026-08-12.
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
- **Verificación real (no simulada, tres rondas):**
  1. Se instaló el entorno de `edi-ai-operator` (`uv pip install -e ".[dev]"`), se corrigió un bug de entorno (`uv` apuntaba al `.venv` de otro proyecto por una variable `VIRTUAL_ENV` residual), se formateó con `black`, y se corrió un import-check real de todo el grafo de módulos tocados (sin mocks) — pasa limpio. Se levantó `ai-rag-service-manager` real (Milvus real, `RAG_EMBEDDING_PROVIDER=local`), se indexó un documento de prueba en `project_999`, y se llamó la función real del cliente de `edi-ai-operator` (`rag_service_client.search_similar_documents`) y las funciones internas de la tool contra ese servicio real — funcionó de punta a punta. Esto destapó P-29 (ver abajo).
  2. Con la API de simulación ya construida, se llamó `RagDocumentSearchSimulationService.simulate(70, None)` **contra la base de datos Postgres real de `edi-ai-operator`** (proyecto real, id 70, "Event Express", consultado directo con SQL para confirmarlo) y contra `ai-rag-service-manager` real: encontró el proyecto, resolvió `indexVecstore=project_70`, ejecutó la búsqueda semántica real, y se detuvo exactamente en el punto esperado (`KeyError` por la fila de `CatPrompt` faltante) — confirmando con precisión el único bloqueante real restante, y destapando el bug de `id_company`/`company_id` de paso.
  3. **2026-08-12, ronda 3 — el usuario creó la fila de `CatPrompt` (`id_project = NULL`, siguiendo el hallazgo del punto anterior) y corrió la guía completa de [`pruebas-manuales-rag-document-search.md`](./pruebas-manuales-rag-document-search.md)** contra los 3 servicios reales arriba (`ai-rag-service-manager`, `edi-ai-operator`; Java no hizo falta para esta prueba) con un documento PDF real (política de privacidad) y proyecto real (`93`): upload+vectorización, confirmación de indexado, y `POST /rag-document-search/simulate` con una pregunta real sobre el documento — **`200` con respuesta real del LLM basada en el contenido del PDF**. En el camino se encontraron y corrigieron dos bugs más: P-30 (`RAG_OPENAI_EMBEDDING_DIMENSIONS=""` rompía `Settings` leyendo desde Vault) y una `OPENAI_API_KEY` inválida (error del usuario al pegarla, no bug de código). **La tool aislada vía `/simulate` queda confirmada end-to-end, incluyendo la síntesis real de respuesta del LLM.**
  4. **2026-08-12, ronda 4 — corte de storage completado.** Se migraron los 7 consumidores restantes de `StorageService` (`thought_persistence_service.py`, `chat_history_service.py`, `context_memory_service.py`, `comun_service.py`, `report_service.py`, `ia_functions.py`, `ia_functions_cache.py`, `common_duck_db.py`) para usar `rag_service_client.upload_file`/`download_file` (se agregó `upload_file` al cliente, que no existía hasta ahora); se eliminó por completo `src/service/util/storage_service.py`, `src/service/util/storage_config.py` (ya estaba huérfano) y la dependencia `google-cloud-storage` de `pyproject.toml`; se eliminó de paso el helper `file_upload()` de `comun_service.py`, que quedó sin ningún caller. **Verificación real:** grep confirmó cero referencias a `StorageService`/`storage_service` en `src/` (fuera de docstrings de `rag_service_client.py`); `black` reformateó los 7 archivos con cambios sustanciales (se dejó `report_service.py` sin reformatear completo — su diff de `black` es 100% deuda preexistente no relacionada a las 2 líneas tocadas); **import-check real** (no solo sintaxis) de los 10 módulos tocados, incluida `company_document_query.py`, contra la base de datos real de `edi-ai-operator` — los 10 importan limpio, sin ciclos ni símbolos faltantes. **No probado:** una llamada real a `/storage/upload`/`/storage/download` end-to-end desde estos 8 archivos (a diferencia de `rag_document_search`, que sí se probó de punta a punta en la ronda 3) — el import-check confirma que el cableado es correcto, pero no ejercita el HTTP real contra `ai-rag-service-manager`.
- **Pendiente para continuar (checklist actualizado, ver también `integracion-operator-rag.md`):**
  - [x] Confirmar con el equipo que `company_id` = mismo `idProject` que Java — validado en la práctica (ronda 3, proyecto real `93`), sin cruce formal contra la base de Java.
  - [x] Agregar la fila de `CatPrompt` para `rag_document_search` con `id_project = NULL` — hecho por el usuario, confirmado funcionando (ronda 3).
  - [x] **Completar el corte de storage** (ronda 4, 2026-08-12) — `edi-ai-operator` ya no tiene ningún acceso directo a GCS, igual que Java (ver P-24). Mismo mandato cumplido en ambos repos: `ai-rag-service-manager` es el único con storage propio.
  - [x] Agregar la fila de worker/tool (`cat_tools`/`tools_implemented`) para que el agente pueda seleccionar la tool — hecho por el usuario, 2026-08-13.
  - [ ] Probar `rag_document_search` integrada al agente completo (moderator/planner/selector de tools) — pendiente (ver también nota general al final del documento: "pendiente probar flujo desde front, backends y rag"). Único ítem restante de este pendiente.
  - [ ] Ejercitar en runtime real (no solo import-check) al menos un flujo de `upload_file`/`download_file` migrado (por ejemplo `save_thought` → `comun_service.py`) contra `ai-rag-service-manager` real.
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

### P-31 — El bucket de storage se propagaba desde Java/operator en vez de resolverse solo en `ai-rag-service-manager`

- **Estado:** Resuelto
- **Detectado:** 2026-08-12, revisión de código a pedido explícito del usuario: "`STORAGE_DEFAULT_BUCKET_NAME` o variables de entorno en las apis del backend java u operator no deben existir, ya el rag debe tener la variable con la que se halla desplegado y esa usará, no se debe propagar en otros micros".
- **Resuelto el:** 2026-08-12
- **Ubicación:**
  - `ai-rag-service-manager`: `app/api/routes/storage_controller.py` (`bucket` ahora opcional en `/storage/get`, `/storage/getFileByte`, `/storage/chunk`), `app/services/storage_service.py` (`store_chunk`/`_consolidate_chunks` con `bucket: str | None`), `app/services/embedding/document_embedding_service.py` (`_load_file_content`, bug de paso corregido).
  - `edi-ai-operator`: `src/service/rag/rag_service_client.py` (`upload_file`/`download_file`), `.env` (quitadas `STORAGE_DEFAULT_BUCKET_NAME` y, de paso, `GOOGLE_APPLICATION_CREDENTIALS`, ambas huérfanas desde el corte de storage de P-28), `Dockerfile` (quitado `ENV GOOGLE_APPLICATION_CREDENTIALS`).
  - `edi-ai-proyectos-backend`: `VectorStoreServiceImpl.java` (quitado el campo `@Value("${app.storage.defaultBucketName}") bucketDocuments`), `StorageManager.java` (quitado `storageConfigProperties` — quedó sin uso), `AnalysisInfoManager.java` (3 de los 7 sitios que usaban `storageConfigProperties.getDefaultBucketName()`).
- **Descripción:** aunque `ai-rag-service-manager` es, desde P-24/P-28, el único microservicio con acceso directo a GCS, tanto Java como `edi-ai-operator` seguían leyendo su **propia** copia del nombre del bucket (`app.storage.defaultBucketName` en Java, `STORAGE_DEFAULT_BUCKET_NAME` en el `.env` de `edi-ai-operator`) y mandándola explícitamente en cada request de storage — exactamente el mismo dato que `ai-rag-service-manager` ya tiene configurado para sí mismo (`storage_default_bucket_name`) y que `StorageClient._get_bucket` ya sabe usar como default cuando no llega `bucket` en el request. Era propagación de config redundante entre microservicios, contraria al principio "un solo dueño de storage" ya establecido en P-24/P-28.
- **Hallazgo colateral (bug de paso, no solo config):** `DocumentEmbeddingService._load_file_content` solo intentaba el fallback a bucket cuando `bucket` era *truthy* (`if bucket: ...`) — si Java/operator dejaban de mandarlo, la carga de contenido fallaba con `ValueError: No document source was provided` en vez de usar el default del servicio. Se quitó ese guard: ahora siempre intenta `download_from_bucket(file_name, bucket)`, y es `StorageClient._get_bucket` (que ya hacía `bucket_name or self._config.default_bucket_name`) quien resuelve el fallback o levanta un error claro si tampoco hay default configurado.
- **Alcance deliberadamente excluido:** Java también manda `storageConfigProperties.getDefaultBucketName()` en 4 sitios de `AnalysisInfoManager.java` (`AskAnalysisRequest`/`AskEvaluationRequest`/`AskVariablesFinancialAnalysisRequest.bucket`) — pero esos van a `analysis-ai-service` (`app.openai.askUrl`), un microservicio distinto, sin relación con `ai-rag-service-manager` y fuera de la visibilidad de este trabajo. Se dejó `StorageConfigProperties.defaultBucketName` intacto en Java precisamente porque esos 4 sitios lo siguen necesitando — no se puede eliminar el campo de config completo, solo dejar de inyectarlo en las llamadas hacia `ai-rag-service-manager`.
- **Verificación real:**
  - `ai-rag-service-manager`: `ruff check .` y `mypy app` limpios; import real de `app.main:app` + `app.openapi()` confirmando `bucket.required = False` en los 3 endpoints corregidos.
  - `edi-ai-operator`: import real de `rag_service_client` y sus 3 consumidores contra la base de datos real; `black --check` limpio.
  - `edi-ai-proyectos-backend`: `./gradlew compileJava compileTestJava assemble` → `BUILD SUCCESSFUL`; grep confirmando que los únicos 4 usos restantes de `getDefaultBucketName()` son los de `analysis-ai-service` (fuera de alcance), no los de `ai-rag-service-manager`.
- **Pendiente relacionado:** no se probó en runtime real (con credenciales GCS reales) que un upload/download sin `bucket` explícito efectivamente resuelva al default configurado del lado servidor — mismo tipo de brecha de verificación que ya tienen P-24 y la mitad de P-28 (no se pudo levantar Java ni ejercitar HTTP real end-to-end contra `ai-rag-service-manager` desde este entorno).

### P-32 — Integrar `edi-ai-chat-backend` (microservicio nuevo): quitar GCS directo, dejar plumbing hacia `ai-rag-service-manager`

- **Estado:** Resuelto
- **Detectado:** 2026-08-12 — `edi-ai-chat-backend` apareció como microservicio nuevo en el workspace (Python/FastAPI, Clean Architecture, Postgres+Redis), sin ninguna integración previa con `ai-rag-service-manager`.
- **Resuelto el:** 2026-08-12
- **Ubicación:** análisis completo en [`integracion-chat-backend-storage.md`](./integracion-chat-backend-storage.md). Código en `edi-ai-chat-backend` (rama `eatroyano/dev/feature/embbedings-vectors`): `src/app/infrastructure/external/rag_service_client.py` (nuevo), `src/app/application/services/storage/storage_service.py` (eliminado, GCS directo), `src/app/utils/upload_file.py` (eliminado), `src/app/utils/utils.py` (`file_upload()` eliminado, sin callers), `src/app/core/config/settings.py` (`rag_service_base_url` nuevo; `storage_default_bucket_name`/`google_application_credentials` eliminados), `src/app/core/config/config_client.py` (migrado de `requests` a `httpx`), `pyproject.toml`/`uv.lock` (sin `google-cloud-storage`), `.env`, `Dockerfile`.
- **Descripción:** el patrón era idéntico al de Java/operator antes de su corte de storage (P-24/P-28): un `StorageService` con cliente GCS directo (`google.cloud.storage`) y config propia (`STORAGE_DEFAULT_BUCKET_NAME`, `GOOGLE_APPLICATION_CREDENTIALS`). **Diferencia importante:** a diferencia de los otros dos repos, este `StorageService` estaba completamente huérfano — grep exhaustivo confirmó cero importadores en todo `src/`, ni wiring en `dependencies.py`, ni ningún endpoint/flujo de negocio que subiera o bajara archivos. No había nada que "migrar" funcionalmente, solo quitar el acceso directo a GCS y dejar la plumbing correcta (mismo contrato que `rag_service_client.py` de `edi-ai-operator`) para uso futuro.
- **Hallazgo colateral, corregido de paso:** al quitar `google-cloud-storage`, se perdió `requests` (dependencia transitiva no declarada explícitamente) — `config_client.py` (cliente de Spring Cloud Config, también confirmado huérfano) lo usaba sin declararlo. Se migró a `httpx` (ya era dependencia directa del proyecto) en vez de re-agregar `requests`, mismo criterio de "no depender de transitivos sin declarar" ya aplicado en P-24 (Java, `auto-value-annotations`/`javax.annotation-api`).
- **Hallazgo colateral — corregido por el usuario, 2026-08-13:** `edward-creds.json` (credencial real de GCS, versionada en git tanto en este repo como en `edi-ai-proyectos-backend`) fue eliminado de ambos repos — confirmado (`git ls-files` ya no lo lista en ninguno de los dos). `.env` (con `DATABASE_PASSWORD`) sigue versionado en este repo; no se tocó.
- **Verificación real (ronda 1, sin caller de negocio):** import real de los módulos tocados y de `src.main:app` completo (con lifespan/routers/CORS) — arranca sin error, 19 rutas registradas. Grep final sin residuos de `google.cloud`/`StorageService`/config de storage. `uv lock`+`uv sync` resolvieron 36 paquetes (antes 52) sin errores. **No se pudo correr `black --check`**: el grupo `dev` de `pyproject.toml` no está declarado como `[dependency-groups]`/`[project.optional-dependencies]` válido para `uv` — preexistente, no introducido por este cambio, fuera de alcance corregir aquí; se verificó en su lugar con `py_compile`.
- **Verificación real (ronda 2, 2026-08-13 — end-to-end genuino, a pedido del usuario):** se creó un controller de validación temporal (`POST /api/chat-ai/v1/storage-test/upload`, `GET /api/chat-ai/v1/storage-test/download` — `src/app/api/v1/controllers/storage_test_controller.py`, `src/app/api/v1/schemas/storage_test.py`) para tener un caller de negocio real que ejercite `rag_service_client.py`, ya que no existía ninguno (ver hallazgo principal arriba). Requirió agregar `python-multipart` como dependencia (faltaba para `UploadFile`/`File(...)` de FastAPI, no declarada antes). Se levantó `edi-ai-chat-backend` real (puerto 7005) contra `ai-rag-service-manager` real ya corriendo (puerto 7006, bucket real `dev-documentos`): `POST /storage-test/upload` con un archivo de prueba → `200 {"success":true,...}`; `GET /storage-test/download?name=...` → `200` con el contenido exacto subido (`sizeBytes`/`contentPreview` correctos). Confirmado además desde los logs reales de `ai-rag-service-manager` (`app/infrastructure/clients/storage_client.py`): `downloading p32-e2e-test.txt with metadata from bucket dev-documentos` — el fallback de bucket server-side (P-31) se ejercitó de verdad, sin que `edi-ai-chat-backend` mandara `bucket` en ningún momento. **Primera verificación real y completa de punta a punta de este pendiente**, cerrando la brecha que quedaba abierta en la ronda 1.
- **Nota:** el controller de validación es temporal, pensado para desaparecer cuando exista una feature de negocio real que use `rag_service_client.py` — no está pensado como superficie pública permanente.

---

### P-33 — Documento "Mapeo Pinecone → Milvus" propone Namespace→Partition y metadata como dynamic fields; no coincide con lo ya implementado

- **Estado:** Pendiente — análisis hecho, sin cambios de código (a pedido explícito del usuario: "NO ejecutes cambios hasta determinar").
- **Detectado:** 2026-08-13, revisión de un documento de guía de migración Pinecone→Milvus (screenshot de Pinecone + doc en markdown) recibido para evaluación.
- **Ubicación revisada:** `app/services/rag/rag_service.py` (`_resolve_collection_name`, `RAGService.__init__`), `app/infrastructure/vector_store/milvus_vector_store.py` (schema real, `create_collection`, `search`, `delete_records`).
- **Análisis — dónde el documento es correcto (en abstracto):** la tabla de equivalencias es razonable como conocimiento general de Milvus: `Partition` es, en efecto, el análogo conceptual más cercano a un `Namespace` de Pinecone, y `enable_dynamic_field=True` es una forma válida y documentada de simular metadata flexible en Milvus. Nada de esto es "falso" como afirmación aislada sobre Milvus.
- **Análisis — dónde el documento NO coincide con lo ya implementado en `ai-rag-service-manager`:**
  1. **Namespace → Collection, no Partition.** El código real resuelve cada "namespace" (`indexVecstore`, ej. `project_127`) como el **nombre de una colección Milvus separada** (`RAGService.collection_name` = el namespace sanitizado, `_vector_store.create_collection(self.collection_name, ...)`). Grep exhaustivo sobre `milvus_vector_store.py` confirma **cero uso de la API de particiones de Milvus** (`create_partition`, `partition_names`, etc. no aparecen en ningún lado del código). Este diseño (una colección por proyecto) es el que se probó, se corrigió (P-25: sanitización de nombres tipo `project-42`→`project_42`) y se verificó end-to-end (P-10/P-11/P-26) — no es un detalle incidental, es la arquitectura actual, ya en uso por Java (`project-{id}`) y por `edi-ai-operator` (`project_{company_id}`).
  2. **Metadata → un único campo JSON `payload`, no dynamic fields.** El schema real se crea con `enable_dynamic_field=False` y exactamente tres campos: `id` (VARCHAR, PK), `vector` (FLOAT_VECTOR), `payload` (JSON, con **toda** la metadata anidada adentro — `codigo`, `file_name`, `position`, `source`, `start_index`, etc., no como columnas propias). El filtrado (`_build_filter_expression`) interpola las claves como `payload["<key>"] == valor`, no como filtros sobre columnas dinámicas de nivel superior. El ejemplo de código del documento (`schema.add_field` solo para `id`/`vector`, `enable_dynamic_field=True`, e insertar `codigo`/`file_name`/etc. como claves sueltas del dict) construiría una colección con un schema distinto al que ya usa el resto del sistema — inconsistente con `record["payload"].get(...)`, usado en todo el codebase.
- **Impacto de implementar el documento tal cual:** no es un simple "ajuste" — implica (a) migrar todas las colecciones ya existentes (una por proyecto) hacia particiones de una única colección compartida, con todo lo que eso conlleva (reindexar o migrar datos, cambiar `_resolve_collection_name`/`create_collection`/`delete_collection`/`search`/`delete_records` para operar con `partition_name`/`partition_names` en vez de `collection_name`); y (b) cambiar el schema de almacenamiento de metadata (de `payload` JSON a campos dinámicos), rompiendo cualquier código que dependa de `payload["..."]` hoy. Ninguno de los dos cambios es trivial ni está pedido por ningún otro pendiente de este documento.
- **Nota sobre el trade-off real (para cuando se decida, no una recomendación de acción ahora):** el diseño actual (colección por proyecto) da aislamiento total pero cada colección de Milvus tiene su propio índice y consume recursos propios al cargarse — con muchos proyectos, el número de colecciones puede volverse un problema operativo (mantener cientos/miles de colecciones cargadas). El diseño que propone el documento (partición por proyecto dentro de una colección compartida) reduce ese overhead por tenant pero comparte el índice/schema entre todos los proyectos. Es una decisión de arquitectura real, no una corrección de bug — debe evaluarse deliberadamente, no adoptarse porque un documento de mapeo genérico lo sugiere.
- **Acción sugerida:** no implementar el documento tal cual. Si se quiere evaluar el cambio a particiones por volumen de proyectos/colecciones, tratarlo como un rediseño explícito (con plan de migración de datos existentes), no como una corrección menor.

#### Ampliación (2026-08-18) — evidencia real de Pinecone en producción + qué se requeriría para replicar ese árbol en Milvus

El usuario mostró capturas reales de la consola de Pinecone (proyecto "Jose Milciades Ordoñez Argote's Org", app `Chatbot`) con 3 índices (`edi-dev`, `edi-prod`, `edi`) y el browser de registros de `edi-dev`, namespace `project_127`, con un registro real y su metadata. **Esto no es un mock ni un ejemplo del documento en disputa: es el vector store real y en uso hoy de `edi-ai-analysis-ai`** (el micro que `ai-rag-service-manager` está reemplazando) — confirmado cruzando las capturas contra el código real de ese repo (`app/utils/vector_store_utils.py`, `app/utils/tools_document.py`) y su propio doc `EMBEDDINGS_Y_BUSQUEDA_VECTORIAL.md`, que ya documentaba esto de forma independiente ("la config vectorial 'viva' del sistema de análisis es la de Pinecone").

**TL;DR — qué se requiere:** nada, si el objetivo es solo "que `ai-rag-service-manager` siga funcionando" (ya funciona, es un sistema nuevo, no tiene que heredar la forma de Pinecone). Pero si el objetivo es **migrar sin perder la separación operativa que ya existía en producción** (1 índice por ambiente, proyectos como namespaces dentro de ese único índice), entonces sí falta trabajo real: hoy `ai-rag-service-manager` crea **una colección Milvus por proyecto** (sin nivel "ambiente" ni "namespace/partición" intermedio), que es una jerarquía distinta a la de Pinecone. Ver el detalle de qué implicaría cada opción en "Qué se requeriría" más abajo — sigue siendo, como ya concluía este pendiente, una decisión de arquitectura explícita, no algo para ejecutar de oficio.

**1. Árbol real de Pinecone en producción (`edi-ai-analysis-ai`), confirmado por código:**

```
Cuenta Pinecone ("Jose Milciades Ordoñez Argote's Org" / app "Chatbot")
└── Index  (1 por ambiente — resuelto por Spring Cloud Config Server,
            key remota `pinecone.collection.name`, vía
            ConfigServer.get_pinecone_collection_name();
            se crea perezosamente si no existe, dimension=3072,
            metric=cosine, ServerlessSpec(aws, us-east-1))
    ├── edi-dev    (ambiente dev — 3072 dim, on-demand, us-east-1)
    ├── edi-prod   (ambiente prod — idéntica config)
    └── edi        (tercer índice visible en la captura; no confirmado a
                    qué perfil/ambiente corresponde — candidato: un
                    profile de config-server anterior al split dev/prod,
                    o un ambiente adicional no documentado. Pendiente de
                    confirmar con el equipo si hace falta.)
        └── Namespace  (1 por proyecto — "índice lógico"; se arma como
                        `f"project-{id}".replace("-", "_")`, ej.
                        `project_127`; Pinecone lo autocrea en el primer
                        upsert, sin llamada explícita de creación — a
                        diferencia de una colección Milvus, que sí
                        requiere `create_collection` antes de insertar)
            ├── project_127   (7 namespaces visibles en la captura de
            ├── ...           `edi-dev`: "NAMESPACES (7)")
            └── Record  (1 por chunk, id interno tipo UUID — `_id` en la
                         captura, ej. `011085d6-54c8-...` — no confundir
                         con el campo de metadata `id`, que es otra cosa,
                         ver tabla de metadata)
                └── metadata (campos PLANOS al nivel del record — no hay
                              un único campo JSON anidado como en Milvus)
```

**2. Árbol real actual en `ai-rag-service-manager` (Milvus), confirmado por código (`app/services/rag/rag_service.py`, `app/infrastructure/vector_store/milvus_vector_store.py`):**

```
Instancia Milvus (una por ambiente — dev y prod corren instancias
Milvus separadas por completo, no una compartida con namespacing
lógico interno; ver docker-compose de edi-ai-orquestadores/milvus)
└── Collection  (1 POR PROYECTO directamente — sin nivel "ambiente" ni
                 "namespace/partición" intermedio dentro de la
                 instancia. El nombre de colección ES el
                 `indexVecstore`/`index_name` que manda el caller,
                 sanitizado por `_sanitize_collection_name`
                 (RAGService/rag_service.py) + prefijo opcional
                 `RAG_COLLECTION_NAME_PREFIX` — Settings, default ""
                 en todos los ambientes probados hasta ahora, o sea:
                 hoy NO hay prefijo de ambiente aplicado al nombre)
    ├── project_127   (= collection_name; equivalente al namespace de
    ├── project_93     Pinecone, pero acá es la unidad de aislamiento
    ├── ...             completa: su propio schema, su propio índice
    │                    vectorial cargado en memoria)
    └── Record  (1 por chunk)
        ├── id       (PK, VARCHAR, uuid — generado por
        │             MilvusVectorStore.insert_vectors)
        ├── vector   (FLOAT_VECTOR, dim = embedding_provider.dim)
        └── payload  (un único campo JSON, TODA la metadata anidada
                      adentro — ver tabla abajo. Schema creado con
                      `enable_dynamic_field=False`, exactamente estos
                      3 campos top-level, nada más)
```

**Diferencia estructural real (no solo terminológica):** en Pinecone, "ambiente" y "namespace/proyecto" son dos niveles reales y separados (1 índice por ambiente, N namespaces por índice). En Milvus hoy, el "ambiente" ni siquiera es un concepto dentro de la instancia (se resuelve por tener instancias Milvus separadas), y "proyecto" pasó a ser el nivel más alto y único (la colección) — se perdió el nivel intermedio que en Pinecone se resolvía con namespaces (y que el documento en disputa proponía resolver con particiones dentro de una colección compartida).

**3. Metadata — dónde queda cargada y descripción de cada campo**

**3a. Pinecone real / `edi-ai-analysis-ai` (legado, confirmado en `app/utils/tools_document.py:28-44`, `setMetadataDoc`):**

Campos planos al nivel del record (no anidados), asignados por chunk al indexar:

| Campo | Origen / valor | Descripción |
|---|---|---|
| `source` | = `file_name` | Duplicado de `file_name`; convención de LangChain (`Document.metadata["source"]` es la clave "estándar" que varios loaders/chains de LangChain esperan por defecto). |
| `id` | = `id_document` | Identificador lógico del documento (el mismo que Java/Postgres conoce como `id_document`). **No confundir con el `_id` interno de Pinecone** (UUID autogenerado, visible arriba de la metadata en la captura) — son dos IDs distintos con el mismo nombre corto. |
| `file_name` | nombre del archivo | Nombre del archivo tal cual se subió/guardó en storage. |
| `nombre_documento` | = `file_name` | Segundo duplicado de `file_name` (además de `source`) — así quedan 3 copias del mismo valor bajo 3 claves distintas por cada chunk. |
| `position` | contador secuencial, 0-based | Índice del chunk dentro del documento (0, 1, 2...) — usado por `find_adjacent_chunks_old` para pedir los siguientes N chunks por rango de `position`. Equivalente a `chunk_index` en `ai-rag-service-manager`. |
| `codigo` | = `id_document` | Segundo duplicado de `id` (mismo valor, otra clave) — usado como filtro exacto (`{"id": {"$eq": id}}`) en varios puntos de `tools_agent.py`. |
| `start_index` | autogenerado por LangChain | `RecursiveCharacterTextSplitter(..., add_start_index=True)` lo agrega solo, sin código propio — offset de caracteres donde empieza el chunk en el texto original. Es la base de `find_adjacent_chunks_new` (expansión ±500 caracteres). Equivalente a `start_index` en `ai-rag-service-manager` (mismo nombre, mismo propósito — P-37 lo replicó a propósito). |
| *(el "Show 1 more" de la captura)* | probablemente `text` | `PineconeVectorStore`/`langchain_pinecone` guarda el `page_content` del chunk como un campo de metadata más (clave por defecto `"text"`) — no se ve en la captura por estar colapsado, pero es el comportamiento estándar de esa librería y coincide con que sea el único campo faltante de los 8 totales. No confirmado por captura completa, sí por comportamiento documentado de `langchain_pinecone`. |

**3b. `ai-rag-service-manager` / Milvus (actual, confirmado en `document_embedding_service.py` + `rag_service.py`):**

Todos estos campos viven **anidados dentro de un único campo `payload` (JSON)** del record Milvus — no son columnas propias:

| Campo (clave dentro de `payload`) | Origen | Descripción |
|---|---|---|
| `file_name` | parámetro del caller | Nombre del archivo (equivalente a `file_name`/`nombre_documento`/`source` de Pinecone, pero sin duplicar — una sola clave). |
| `id_document` | parámetro del caller | Identificador lógico del documento (equivalente a `id`/`codigo` de Pinecone, una sola clave en vez de dos). |
| `unique_code` | parámetro del caller | Código único de Java/operator para el documento (`Document.uniqueCode`/`uniqueCodeStorage` en Java) — es la clave real usada para filtrar/borrar/listar chunks de un documento (`delete_records({"id_document": ...})`, `list_records(filter_conditions={"unique_code": ...})`). No tiene equivalente 1:1 en el esquema de Pinecone de arriba (ese repo no maneja este concepto). |
| `bucket` | parámetro del caller | Bucket de storage (GCS) donde vive el archivo original — necesario para poder re-descargarlo (P-37, `_expand_via_source_reslice`). Sin equivalente en Pinecone (ese repo no re-descarga el original para expandir contexto del mismo modo). |
| `source` | constante `"document_upload"` | A diferencia de Pinecone (donde `source` = nombre de archivo), acá es un valor fijo que indica el origen del chunk (por ahora siempre el mismo, sin otros valores en uso). |
| `chunk_index` | contador secuencial, 0-based | Equivalente exacto a `position` en Pinecone — mismo propósito (fallback de "adjacent chunks" por rango, P-37 `_expand_via_adjacent_chunk_index`). |
| `start_index` / `end_index` | offsets calculados por `RAGService._split_text` | Mismo propósito que `start_index` en Pinecone (expansión por offset de caracteres, P-37), pero acá se guardan **ambos** extremos (Pinecone/LangChain solo agrega el de inicio) — permite recortar la ventana exacta del chunk sin tener que inferir el final. |
| `text` | el propio texto del chunk | Igual que el campo homónimo (probable) de Pinecone — el contenido del chunk, para no depender de recuperar el vector para leer qué dice. |
| *(claves de `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP`/etc.)* | `list_parameters` normalizado (`_normalize_parameters`) | Todo lo que Java mande en `listParameters` (ver P-21/P-35) se vuelca tal cual dentro del mismo `payload`, con la clave literal que mande Java (ej. `payload["VECTOR_CHUNK_SIZE"]`) — metadata de auditoría/trazabilidad, no se relee para nada operativo salvo `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP` (P-35, ya sí tienen efecto real en el chunking, ver ese pendiente). |

**Equivalencias directas entre ambos esquemas** (mismo concepto, otro nombre):

| Concepto | Pinecone (legado) | Milvus (actual) |
|---|---|---|
| Documento lógico | `id` / `codigo` (duplicados) | `id_document` |
| Nombre de archivo | `file_name` / `nombre_documento` / `source` (triplicados) | `file_name` |
| Posición del chunk | `position` | `chunk_index` |
| Offset de inicio (para expandir contexto) | `start_index` (autogenerado por LangChain) | `start_index` (calculado a mano en `_split_text`, P-37) |
| Offset de fin | *(no existe — solo inicio)* | `end_index` (mejora respecto al esquema legado) |
| Texto del chunk | `text` (probable, vía `langchain_pinecone`) | `text` |
| Código único para filtrar/borrar por documento | *(no existe un equivalente directo — Pinecone usa `id`/`codigo`)* | `unique_code` |

**4. Qué se requeriría para replicar el árbol real de Pinecone (1 índice por ambiente + namespace por proyecto) en Milvus — sin implementar, solo enumerado:**

1. **Colapsar todas las colecciones-por-proyecto en una única colección compartida por ambiente** (`RAGService`/`_resolve_collection_name` dejarían de recibir el proyecto como `collection_name`; el proyecto pasaría a ser un parámetro aparte).
2. **Adoptar la API de particiones de Milvus** (`create_partition`, `partition_names`, `load_partitions`, `drop_partition`) en `MilvusVectorStore` y en el contrato de `VectorStoreInterface`/`VectorStoreManager` — hoy ninguno de los dos la conoce (grep confirmado: cero referencias). Cada método (`insert_vectors`, `search`, `list_records`, `delete_records`) necesitaría un `partition_name` explícito además del `collection_name`.
3. **Redefinir la semántica de "borrar todo un proyecto".** Hoy `delete_index`/`delete_collection` borra la colección completa (aislada, 1 por proyecto) — bajo particiones, el equivalente sería `drop_partition` (deja intacta la colección compartida y el resto de proyectos), una operación distinta a "borrar la colección entera" (que ya no tendría sentido hacer por proyecto).
4. **Plan de migración de datos ya existentes:** las colecciones-por-proyecto que ya están en uso (confirmadas en producción vía P-25/P-26/P-28/etc.) tendrían que migrarse (leer vía `list_records` de cada colección vieja, reinsertar en la partición correspondiente de la colección compartida) — no hay atajo, Milvus no tiene un "mover colección a partición" nativo.
5. **Decidir si conviene 1 colección compartida por ambiente (mimetizando 1:1 el índice de Pinecone) o mantener el criterio actual de "1 instancia Milvus por ambiente" y usar particiones solo para separar proyectos dentro de esa instancia** — con el volumen real observado en las capturas (3 índices, 7 namespaces, 0.97GB/2GB de uso), la escala actual de producción es chica; el argumento original de P-33 ("con muchos proyectos, mantener cientos/miles de colecciones es un problema operativo") todavía no se manifiesta en los datos reales vistos, lo que resta urgencia (no descarta la decisión, la vuelve menos apremiante).
6. **Fuera de esta migración de árbol (independiente, no lo exige):** unificar/renombrar los campos de metadata duplicados del esquema legado (`codigo`/`id`, `file_name`/`nombre_documento`/`source`) no es necesario para el cambio de partición — son dos decisiones ortogonales. `ai-rag-service-manager` ya usa un esquema sin esas duplicaciones; no hay necesidad de heredar la redundancia de Pinecone al migrar.

**5. Decisión del usuario (2026-08-18) y qué se implementó:**

Ante las dos preguntas abiertas de la sección anterior, el usuario decidió explícitamente:
- **Diseño del "index" de ambiente:** opción liviana — **prefijo de ambiente en el nombre de colección** (no particiones reales de Milvus). Sigue existiendo 1 colección Milvus por proyecto, pero su nombre ahora queda `{ambiente}_{proyecto}` (ej. `edi_local_project_127`). Se descartó explícitamente la opción de particiones reales (ítems 1-4 de arriba) por ser mucho más invasiva y no justificada por la escala real observada (ítem 5 de arriba).
- **Datos ya indexados sin prefijo** (`project_93`, `project_p37test`, `project_70` — generados durante las pruebas E2E de esta misma sesión, P-34/P-36/P-37): **eliminar**, no migrar — son datos de prueba de desarrollo, no de clientes reales.
- **Valores permitidos:** exactamente `edi-local` (ambiente de pruebas de desarrollo local, el que se usó en toda esta sesión), `edi-dev`, `edi-stage`, `edi-prod` — mismos 4 nombres que pidió el usuario, con el prefijo `edi-` ya usado por los índices reales de Pinecone vistos en las capturas (`edi-dev`, `edi-prod`, `edi`).

**Implementación, `ai-rag-service-manager`:**

- **`app/core/config.py`:** se reemplazó `rag_collection_name_prefix` (`str`, default `""`, opcional) por `rag_environment` (`str`, validation_alias `RAG_ENVIRONMENT`, default `"edi-local"`) con un `field_validator` nuevo (`_validate_rag_environment`) que **falla fuerte** (`ValueError`) si el valor no es exactamente uno de los 4 permitidos — mismo criterio que `VaultClient` (fallar explícito ante un typo, no caer en silencio a un ambiente distinto al pedido). Funciona igual desde `.env`, variable de entorno exportada, o Vault (`vault.load_configs(["ai-rag-service-manager", ...])` pasa las claves tal cual a `Settings(**config)` — no requiere ningún cambio adicional de plumbing, es el mismo mecanismo que ya usaban todas las demás variables `RAG_*`).
- **`app/services/rag/rag_service.py`:** `_resolve_collection_name` (renombrado el parámetro `prefix`→`environment` para reflejar que ya no es opcional) y `RAGService.__init__` ahora usan `settings.rag_environment` en vez de `settings.rag_collection_name_prefix`. Ningún otro archivo llamaba a `_resolve_collection_name` directamente ni conocía el nombre de campo viejo (grep confirmado) — el cambio queda contenido a estos dos puntos.
- **`.env` / `.env.example` / `README.md`:** `RAG_COLLECTION_NAME_PREFIX=` reemplazado por `RAG_ENVIRONMENT=edi-local` (con comentario explicando los 4 valores permitidos y la referencia a este pendiente).
- **Sin cambios de contrato HTTP:** Java y `edi-ai-operator` siguen mandando `indexVecstore`/`index_name` exactamente igual que hoy (ej. `project_127`) — el ambiente no es algo que ellos manden, lo resuelve `ai-rag-service-manager` internamente a partir de su propia config. Cero impacto en esos dos repos.
- **Verificación real, contra Milvus real (`localhost:19530`, mismo contenedor usado en toda la sesión):**
  1. `ruff check .` y `mypy app` limpios.
  2. `Settings(RAG_ENVIRONMENT=...)` probado con default (`edi-local`), valor explícito (`edi-dev`) y valor inválido (`bogus`) — los 3 casos correctos: default correcto, override correcto, `ValidationError` real lanzado para el valor inválido.
  3. `_resolve_collection_name` probado con ambos ambientes: `project_999` → `edi_local_project_999` / `edi_dev_project_999`.
  4. **Prueba real de punta a punta contra Milvus real** (no mockeada): `RAGService(settings, ..., collection_name="project_999")` con `RAG_ENVIRONMENT` default creó efectivamente la colección `edi_local_project_999` en el Milvus real (`vector_store_manager.collection_exists(...)` → `True`), confirmando que el prefijo llega hasta la creación real de la colección, no solo hasta el cálculo del nombre.
- **Limpieza de datos huérfanos (decisión explícita del usuario, "eliminar"):** se listaron las colecciones reales existentes en el Milvus local antes de borrar (`project_93` con 77 registros, `project_p37test` con 1, `project_70` con 0 — las tres generadas durante las pruebas E2E de P-34/P-36/P-37 de esta sesión) y se eliminaron (`client.drop_collection(...)`), junto con la colección de verificación (`edi_local_project_999`) creada en el punto anterior. Milvus local queda sin colecciones — todo lo que se indexe de ahora en más nace ya con el prefijo de ambiente.
- **Pendiente del lado del usuario (no ejecutable desde acá):** los despliegues reales vía `run-local-vault.sh`/Vault (`USE_VAULT_CONFIG=true`) leen `RAG_ENVIRONMENT` del secreto Vault en el path `ai-rag-service-manager` (mismo mecanismo que el resto de variables `RAG_*`) — mientras ese secreto no incluya la clave `RAG_ENVIRONMENT`, el servicio arranca igual (cae al default `edi-local`) pero **sin reflejar el ambiente real** de ese despliegue. Falta que el equipo agregue `RAG_ENVIRONMENT=edi-dev` (o el que corresponda) al secreto de Vault de cada ambiente — no se puede hacer desde este entorno (requiere acceso de escritura al Vault real del equipo).
- **Acción sugerida:** ninguna — resuelto en su momento (diseño de prefijo liviano). **Reemplazado el mismo día por el punto 6 de abajo** (partición real de Milvus), a pedido del usuario.

**6. Ajuste (2026-08-18, mismo día): de prefijo en el nombre a partición real de Milvus**

El usuario pidió explícitamente cambiar el diseño recién implementado: en vez de concatenar `{ambiente}_{proyecto}` como nombre de colección, usar la **API de particiones real de Milvus** — colección = proyecto solo (sin concatenar, ej. `project_127`), partición = ambiente (ej. `edi_dev`) dentro de esa colección — "será más fácil de administrar" (browsear/borrar un ambiente puntual en Attu sin que su nombre quede mezclado con el del proyecto, y sin tener que recrear la colección completa para cambiar de ambiente).

Esto es justo el ítem 2 de la sección "4" de arriba (que se había descartado por invasivo), pero **acotado**: no colapsa múltiples proyectos en una colección compartida (seguía siendo 1 colección por proyecto, eso no cambió) — solo mueve el ambiente de "prefijo en el nombre" a "partición dentro de la colección". Mucho menos invasivo que el rediseño completo de la sección "4".

**Implementación, `ai-rag-service-manager`:**

- **`app/infrastructure/vector_store/vector_store_interface.py`:** contrato ampliado con `create_partition`/`delete_partition` (nuevos, abstractos) y parámetro opcional `partition_name` en `insert_vectors`/`search`/`list_records`/`delete_records`.
- **`app/infrastructure/vector_store/milvus_vector_store.py`:** implementación real vía `pymilvus.MilvusClient` — `create_partition`/`has_partition`/`drop_partition` (con `release_partitions` antes de `drop_partition`, requerido por Milvus para una partición cargada), `insert(..., partition_name=...)` (parámetro singular en la API real), `search(..., partition_names=[...])`/`query(..., partition_names=[...])` (plural, lista, para buscar/listar dentro de esa partición nada más), `delete(..., partition_name=...)`. Firmas exactas confirmadas por introspección real de `pymilvus` 3.0.1 instalado (no asumidas).
- **`app/infrastructure/vector_store/vector_store_manager.py`:** `InMemoryVectorStore` (backend de desarrollo sin Milvus real) simula particiones etiquetando cada registro con `_partition` y filtrando por ella cuando se pide; `VectorStoreManager` (facade) expone los métodos nuevos y reenvía `partition_name` en los existentes.
- **`app/services/rag/rag_service.py`:** **eliminada** `_resolve_collection_name` (la función de concatenación, ya no hace falta). `RAGService.collection_name` ahora es el proyecto solo, sanitizado (`_sanitize_collection_name(collection_name or rag_default_collection_name)`); `RAGService.partition_name` (atributo nuevo, público) es el ambiente solo, sanitizado (`_sanitize_collection_name(settings.rag_environment)`). El constructor crea la colección si falta y **siempre** asegura que la partición del ambiente actual exista (`create_partition`, idempotente). `index_documents`/`search`/`delete_records` pasan `partition_name=self.partition_name`. `clear_collection` (antes: `delete_collection` de la colección completa) ahora llama a `delete_partition` — **borra solo el ambiente actual, sin tocar los demás ambientes que comparten la misma colección/proyecto**.
- **Hallazgo colateral corregido (bug real, no parte de este pedido pero en el mismo código):** al revisar `document_embedding_service.py` para agregar `partition_name`, se encontró que **4 métodos llamaban a `vector_store_manager` directamente con el `index_name` crudo** (`list_documents_by_index`, `get_embeddings_by_unique_code`, `_expand_via_adjacent_chunk_index`, `delete_index`), sin pasar por `_get_rag_service(...)` para resolver el nombre real de colección — esto ya estaba roto desde la implementación del prefijo de ambiente (punto 5 de arriba, mismo día): esos 4 métodos hubieran consultado una colección `project_127` que ya no existía (la real pasó a llamarse `edi_local_project_127`), devolviendo listas vacías en silencio. Corregido: los 4 ahora resuelven `rag_service = self._get_rag_service(index_name)` primero y usan `rag_service.collection_name`/`rag_service.partition_name`. `delete_index` además cambió de `vector_store_manager.delete_collection(...)` (borraba TODO, cross-ambiente si la colección llegara a compartirse) a `rag_service.clear_collection()` (borra solo la partición/ambiente actual).
- **Verificación real, contra Milvus real (`localhost:19530`):**
  1. `ruff check .` y `mypy app` limpios.
  2. **Prueba de punta a punta con dos ambientes simultáneos sobre el mismo proyecto** (`RAGService` con `RAG_ENVIRONMENT=edi-local` y otra instancia con `RAG_ENVIRONMENT=edi-dev`, mismo `collection_name="project_verif"`): confirmado que ambas resuelven **la misma colección** (`project_verif`) con **particiones distintas** (`edi_local`/`edi_dev`); se indexó un documento distinto en cada una y se confirmó **aislamiento real**: buscar en `edi-local` el contenido indexado en `edi-dev` devuelve 0 resultados relevantes (sin fuga cruzada). `client.list_partitions('project_verif')` (Milvus real) confirmó `['_default', 'edi_local', 'edi_dev']`.
  3. Se probó el borrado por ambiente (`clear_collection()`/equivalente a `delete_index`): tras borrar la partición `edi_local`, la partición `edi_dev` siguió intacta y buscable (`list_partitions` confirmó `['_default', 'edi_dev']`, ya sin `edi_local`) — el borrado no afecta a otros ambientes.
  4. Milvus local quedó limpio al final de la verificación (`list_collections()` → `[]`).
- **Acción sugerida:** ninguna — resuelto con partición real de Milvus, reemplazando el diseño de prefijo del punto 5.

### P-34 — Inactivar un documento en Java (`DELETE .../resources/{resourceId}/documents/delete/{documentId}`) no elimina el registro vectorial en Milvus

- **Estado:** Resuelto (a pedido explícito del usuario: "ejecuta P-34 - validando el tipo de resource, ya inactiva en postgres, se requiere eliminar de milvus").
- **Detectado:** 2026-08-13, a partir de un caso real reportado: `DELETE https://api.ediaidev.softwarecumbre.com/proxy/api/backend/resources/24/documents/delete/5940?updating_id_user=user4.prueba4`.
- **Resuelto el:** 2026-08-13.
- **Ubicación:** `edi-ai-proyectos-backend`: `ResourcesController.deleteDocument`/`deleteDocuments` (`DELETE {resourceId}/documents/delete/{documentId}` y `.../delete-batch`, `ResourcesRoute.DELETE_DOCUMENT`), `ResourcesServiceImpl.deleteDocument`/`deleteDocuments` (líneas ~241-300).
- **Descripción:** `ResourcesServiceImpl.deleteDocument` hace **únicamente** un soft-delete en Postgres:
  ```java
  document.setActive(false);
  document.setUpdatingUser(updatingUser.getId());
  documentRepository.save(document);
  ```
  No llama a `VectorStoreService`/`VectorStoreManager` en ningún punto. **No es un olvido de una línea: `ResourcesServiceImpl` ni siquiera tiene `VectorStoreService`/`VectorStoreManager` inyectado como dependencia** (confirmado revisando sus campos/constructor) — la clase estructuralmente no tiene forma de llegar a `ai-rag-service-manager` hoy. `deleteDocuments` (borrado batch) tiene exactamente el mismo problema.
- **Contraste — el patrón correcto SÍ existe en este mismo repo, solo que en otros módulos:** hay 7 sitios reales donde borrar un documento sí dispara `vectorStoreService.deleteEmbeddingDocument(indexVecstore, uniqueCode)` (o el equivalente `VectorStoreManager.deleteDocumentVectorStore`): `VectorStoreController`, `KnowledgeBaseManager` (x2), `UserServiceImpl`, `TicketManager`, `EvaluationMaturityManager` (x2). El módulo `aiResourcesManagement` (el que expone `.../resources/{resourceId}/documents/delete/{documentId}`) es el único de los flujos de borrado de documentos que no sigue este patrón ya establecido.
- **Impacto:** cualquier documento borrado/inactivado a través de este endpoint específico deja su vector **huérfano y buscable** en Milvus indefinidamente — `search_similar_documents`/`rag_document_search` pueden seguir devolviendo contenido de un documento que en Postgres ya figura como `active=false`. Es un problema de integridad de datos con efecto visible: el agente/RAG puede citar o basarse en contenido que el usuario ya marcó como eliminado.
- **Lo que faltaba (ya no):** inyectar `VectorStoreService` en `ResourcesServiceImpl` (ya estaba inyectado desde P-36, resuelto en la misma sesión) y resolver el `indexVecstore` — la convención de P-36 (`resource.getArea().getProject().getId()` → `project-{id}`) resultó ser exactamente la misma que necesita este pendiente, así que no hizo falta "descubrir" nada nuevo.

**Implementación (2026-08-13), `edi-ai-proyectos-backend`:**

- **`ResourcesServiceImpl.deleteDocument`** y **`deleteDocuments`** (batch) ahora capturan la referencia a `Resources` (antes solo se usaba para verificar existencia, no se guardaba en una variable) y, después de inactivar el/los documento(s) en Postgres, llaman a un nuevo helper privado compartido `deleteFromVectorStoreIfDataBaseEmbedding(resource, documents)`:
  - Contraparte simétrica exacta de `triggerVectorizationIfDataBaseEmbedding` (P-36): mismo chequeo de `resourcesType.code == data_base_embedding`, misma resolución de `indexVecstore` (`project-{resource.area.project.id}`).
  - Por cada documento con `uniqueCode` no nulo, llama a `vectorStoreService.deleteEmbeddingDocument(indexVecstore, document.getUniqueCode())` — mismo método ya usado por `KnowledgeBaseManager`/`UserServiceImpl`/`TicketManager`/`EvaluationMaturityManager` para el mismo propósito, sin cliente nuevo.
  - No hizo falta `try/catch` adicional: `VectorStoreServiceImpl.deleteEmbeddingDocument` ya atrapa sus propias excepciones internamente y solo loguea — un fallo de red no revierte la inactivación ya confirmada en Postgres.
  - `deleteDocuments` (batch) reusa el mismo helper con la lista completa de documentos inactivados, para no duplicar lógica.
- **Verificación real, con `ai-rag-service-manager` desplegado vía `run-local-vault.sh`** (a pedido explícito del usuario, en vez del arranque plano con `.env` usado en la ronda de P-36 — Vault trae credenciales reales de GCS, a diferencia de la ronda anterior donde `edward-creds.json` ya no existía y el arranque plano fallaba con "default credentials not found"):
  1. `./gradlew compileJava compileTestJava` → `BUILD SUCCESSFUL`.
  2. Se resolvió un problema de red local (Java no podía resolver el hostname Docker `ai-rag-service-manager`, igual que en la ronda de P-36) editando temporalmente `application-dev.yml` para apuntar a `localhost:7006` — **revertido a `ai-rag-service-manager:7006` inmediatamente después de la prueba**, confirmado con `git diff` que no queda ningún cambio residual en ese archivo.
  3. Se restauró `STORAGE_DEFAULT_BUCKET_NAME=dev-documentos` en el `.env` de `ai-rag-service-manager` (había quedado vacío, rompiendo el arranque plano) — este sí se dejó (no era un cambio solo-para-la-prueba, es la config real que ya se había usado y verificado en rondas anteriores de esta sesión).
  4. Flujo completo real: `POST /storage/upload` (archivo real) → `POST /resources/25/documents/create` → `Disparando vectorizacion para documento 5946 (resource 25, data_base_embedding) en project-93` → descarga real exitosa desde `ai-rag-service-manager` (`GET /storage/getFileByte` → `200`, confirmando que las credenciales GCS vía Vault sí funcionan, a diferencia de la ronda de P-36). El último paso (`POST /embedding/save_document_vecstore`) falló, pero por una causa **completamente ajena a este cambio**: `VectorStoreServiceImpl.saveEmbeddingFile` intenta obtener un token de Keycloak antes de llamar a `ai-rag-service-manager`, y el certificado TLS de `keycloak.ediaimx.softwarecumbre.com` **está vencido** (`certificate_expired`, confirmado en el stacktrace real) — afecta a *todos* los flujos de vectorización de Java que pasan por ese método, no solo a este. Nota aparte: ese token ni siquiera cumple una función real del lado de `ai-rag-service-manager`, que no implementa autenticación (P-13) — ya se había señalado en P-24 que Java podría dejar de mandarlo sin romper nada.
  5. **`DELETE /resources/25/documents/delete/5946` sí se probó de punta a punta con éxito total:** log real `Eliminando vector para documento 5946 (resource 25, data_base_embedding) en project-93`, seguido de `ai-rag-service-manager` conectándose a Milvus real (`connecting to milvus at http://localhost:19530`) y respondiendo `POST /api/v1/embedding/delete_document HTTP/1.1" 200`. Este método (`deleteEmbeddingDocument`) no pasa por Keycloak — esa línea está comentada en el código (`//headers.setBearerAuth(...)`) — por eso no lo afectó el certificado vencido.
- **Hallazgo colateral, reportado sin corregir (fuera de alcance, es un problema de infraestructura externa):** el certificado TLS de `keycloak.ediaimx.softwarecumbre.com` está vencido, y bloquea `VectorStoreServiceImpl.saveEmbeddingFile` — es decir, **todo** el flujo de guardado de vectores desde Java (no solo `aiResourcesManagement`), incluyendo el que ya se daba por resuelto en P-24. No se puede corregir desde código ni desde este entorno (requiere renovar el certificado del lado del servidor Keycloak). Vale la pena que el equipo lo sepa: mientras el certificado siga vencido, ningún documento se vectoriza exitosamente desde Java, sin importar qué tan bien esté resuelto el resto del flujo.
- **Acción sugerida:** ya no aplica — resuelto. Queda como acción externa (no de este repo) renovar el certificado de Keycloak para que el guardado de vectores desde Java vuelva a funcionar de punta a punta.

### P-35 — `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP`/`VECTOR_K_SIMILILARITY`: Java los manda (o los mandaba a `edi-ai-analysis-ai`), `ai-rag-service-manager` no los aplica

- **Estado:** Resuelto (parcial — solo `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP`; `VECTOR_K_SIMILILARITY` sigue sin acción porque el flujo que lo usaría en Java, `askInDocuments`, todavía no está migrado a `ai-rag-service-manager`, ver abajo).
- **Detectado:** 2026-08-13, a partir de `Constants.CODE_PARAMETER_VECTOR_CHUNK_SIZE`/`CODE_PARAMETER_VECTOR_CHUNK_OVERLAP`/`CODE_PARAMETER_VECTOR_K_SIMILILARITY` en `edi-ai-proyectos-backend` (`business/util/Constants.java:31-33`).
- **Resuelto el:** 2026-08-13.
- **Qué son (confirmado leyendo Java + `edi-ai-analysis-ai`, el micro que reemplaza `ai-rag-service-manager`):** los tres son códigos de filas en la tabla `Parameters` de Java (`parameterCommonService.getParameterByCode(...)`), es decir, **configurables desde base de datos/admin, no hardcodeados** — un admin puede ajustarlos sin desplegar código.
  - `VECTOR_CHUNK_SIZE` (default histórico 1000) y `VECTOR_CHUNK_OVERLAP` (default histórico 200): tamaño de chunk y solapamiento en caracteres para el *text splitter* al indexar un documento.
  - `VECTOR_K_SIMILILARITY` (default histórico 4): el `top_k` — cuántos chunks similares recuperar al responder una pregunta contra documentos.
- **Dónde se usan en Java:**
  - `VectorStoreManager.buildListParameters()` (`vectorstore/VectorStoreManager.java:152-165`) arma `listParameters` con `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP` (valores leídos de `Parameters` en ese momento) y los adjunta a `SaveFileVecstoreRequest` — **este es el mismo payload que hoy llega a `ai-rag-service-manager`** (`POST /embedding/save_document_vecstore`, `listParameters`), no a un servicio distinto.
  - `AnalysisInfoManager.askInDocuments()` (`analysisInfo/AnalysisInfoManager.java:373-376`) lee `VECTOR_K_SIMILILARITY` y lo manda como `parameterKsimilarity` en `AskAnalysisRequest` — pero este flujo (`askInDocuments`) todavía va a `analysis-ai-service` (`app.openai.*`), **no** a `ai-rag-service-manager`; Java no ha migrado el flujo de "preguntar contra documentos" a la RAG, solo storage/vectorización (ver P-24).
- **Cómo los aplica `edi-ai-analysis-ai` (el micro que se está reemplazando) — confirma que sí eran funcionales, no solo transportados:**
  - `app/services/document_service.py:91-93`: `DocumentService.save_document_vecstore` lee `request.list_parameters` (mismo payload, mismos códigos `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP`, con `get_param(...)` y default 1000/200 si no vienen) y **los aplica de verdad** a `ToolsDocuments.chunk_size`/`chunk_overlap` antes de trocear el texto.
  - `app/utils/tools_agent.py:56,462`: `k_similarity` (desde `parameterKsimilarity`) se usa literalmente como `k=self.k_similarity` en `vecstore.similarity_search(...)`.
- **Qué hace hoy `ai-rag-service-manager` con lo mismo — confirmado leyendo el código real:**
  - `app/services/embedding/document_embedding_service.py._normalize_parameters` mete `list_parameters` (con `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP` adentro, tal cual los manda Java) dentro del `payload` de metadata de cada chunk — **quedan guardados como metadata inerte, nunca se leen de vuelta para nada**.
  - `RAGService._split_text` (`app/services/rag/rag_service.py:121-133`) siempre usa `self._settings.rag_chunk_size`/`self._settings.rag_chunk_overlap` — **config global de `Settings`/`.env` de este servicio, fija para todas las colecciones y todos los requests**, sin ningún mecanismo para recibir un chunk_size/overlap por request. Lo que Java manda en `listParameters` se ignora por completo para este propósito.
  - `VECTOR_K_SIMILILARITY`: no hay ningún equivalente hoy en el contrato de `ai-rag-service-manager` que Java consuma — no aplica todavía porque Java no manda preguntas a este servicio (ver arriba). `search_similar_documents`/`SearchSimilarDocumentsRequest` sí acepta `top_k` por request (eso ya existe), pero nadie en Java lo está poblando con `VECTOR_K_SIMILILARITY` porque ese flujo no está migrado.
- **Impacto:** si/cuando se complete la migración de Java a `ai-rag-service-manager` para estos flujos, el comportamiento configurable por admin (ajustar chunk size/overlap/K sin desplegar) se pierde silenciosamente — todos los proyectos indexados quedarían con el mismo chunk_size/overlap global de `.env`, sin importar lo que el admin haya configurado en `Parameters` para un caso puntual. No es un blocker hoy (nada se rompe, los valores simplemente no producen efecto), pero es una regresión de funcionalidad respecto a `edi-ai-analysis-ai`.
**Implementación (2026-08-13), `ai-rag-service-manager`:**

- **`app/services/rag/rag_service.py`:** `RAGService.index_documents`/`_split_text` ahora aceptan `chunk_size`/`chunk_overlap` opcionales por llamada. Sin ellos, cae exactamente al comportamiento anterior (`Settings.rag_chunk_size`/`rag_chunk_overlap`) — sin cambio para ningún caller existente que no los mande. El `overlap` efectivo se clampa a `[0, chunk_size-1]` (antes solo se clampaba el límite superior) para que un valor negativo/inválido llegado por request no produzca un resultado distinto a simplemente omitirlo.
- **`app/services/embedding/document_embedding_service.py`:** `save_document_to_vecstore` extrae `VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP` de `list_parameters` (ya normalizados por `_normalize_parameters`, que ya soportaba el formato `{code, value}` de Java desde P-21) vía un nuevo helper `_parse_int_parameter` (convierte el string que manda Java a `int`; si falta la clave o no es un entero válido, devuelve `None` y loguea un warning — nunca rompe la indexación, cae al default global) y los pasa a `index_documents`. Siguen guardándose también en la metadata del chunk (comportamiento preexistente, sin cambios) — ahora además tienen efecto real.
- **`VECTOR_K_SIMILILARITY`: sin acción.** Confirmado que no aplica todavía porque Java no manda preguntas a `ai-rag-service-manager` (`askInDocuments` sigue yendo a `analysis-ai-service`) — no hay ningún punto de este repo donde conectarlo hoy. `search_similar_documents` ya acepta `top_k` por request de forma independiente; cuando Java migre ese flujo, alcanza con que mande `VECTOR_K_SIMILILARITY` como `top_k` — no requiere cambios adicionales de este lado.
- **Verificación real (sin infraestructura externa, con las clases de producción reales, no reimplementadas):**
  1. `ruff check .` y `mypy app` limpios.
  2. `RAGService._split_text` probado directamente: sin override usa el default global (1000/200, igual que antes); con override `chunk_size=500, chunk_overlap=50` produce chunks distintos y correctos; override parcial (solo `chunk_size`) cae al `chunk_overlap` global para el resto; `chunk_overlap=-5` (valor inválido) no rompe ni genera loop infinito, se clampa a `0`.
  3. `DocumentEmbeddingService._parse_int_parameter` probado con los 4 casos reales: valor entero válido, valor no-entero (loguea warning, devuelve `None`), clave ausente, y el formato exacto `{"code": "VECTOR_CHUNK_SIZE", "value": "1200"}` que manda Java — los 4 casos correctos.
  4. **Prueba de integración real (clases de producción reales, solo Milvus/embedding mockeados por no requerir infraestructura para esto):** `DocumentEmbeddingService.save_document_to_vecstore` con `list_parameters=[{"code": "VECTOR_CHUNK_SIZE", "value": "500"}, {"code": "VECTOR_CHUNK_OVERLAP", "value": "50"}]` sobre un texto de 3000 caracteres generó **7 chunks** (correcto para 500/50: antes, con el bug, hubiera generado los mismos 4 chunks de siempre con 1000/200 sin importar lo que mandara Java). Sin `list_parameters` (caso preexistente): mismo número de chunks que antes de este cambio — sin regresión confirmada.
- **Acción sugerida:** ninguna — resuelto para chunk_size/overlap. `VECTOR_K_SIMILILARITY` queda correctamente sin acción hasta que Java migre `askInDocuments` a `ai-rag-service-manager` (fuera del alcance de este pendiente).
- **Re-verificado el 2026-08-18, tras implementar P-37** (que modifica `_split_text`/`index_documents`, los mismos métodos que este pendiente): se repitieron las pruebas de `_split_text` con y sin override — mismos resultados exactos que arriba (`sizes = [1000, 1000, 900]` default, 6 chunks con override 500/50) — **sin regresión**. `_split_text` ahora devuelve `(texto, start_index, end_index)` en vez de solo `texto` (necesario para P-37), pero el comportamiento de chunking en sí no cambió.

### P-36 — La condición para vectorizar un documento no considera `resources_type.code = 'data_base_embedding'`

- **Estado:** Resuelto (opción 2 de las dos diagnosticadas — disparar la vectorización en `{resourceId}/documents/create`, a pedido explícito del usuario: "usa el fix - disparar la vectorización en {resourceId}/documents/create"). La opción 1 (agregar `resourceId` a `/storage/upload`) se dejó **documentada como nota en el código, sin implementar**, también a pedido explícito.
- **Detectado:** 2026-08-13, a raíz del mismo análisis que P-34 (módulo `aiResourcesManagement`).
- **Resuelto el:** 2026-08-13.
- **Condición actual de vectorización (confirmada en código):** `StorageManager.validateAndSendToSaveDocsOnVecstore` (`storage/StorageManager.java:84-102`) dispara la vectorización (`sendAsyncRequestVectored` → `ai-rag-service-manager`) si y solo si:
  1. El upload fue exitoso, y
  2. `uploadFileRequest.codeTypeDocument()` está presente, y
  3. Ese `codeTypeDocument` está en la lista configurada en el parámetro `is_vectorizable` (`Parameters`, `CodesParams.CODE_TYPE_DOC_IS_VECTORIZABLE`).

  Es una condición basada **exclusivamente en el tipo de documento** (`codeTypeDocument`), sin ninguna relación con el concepto de "Resource"/`resources_type`.
- **El concepto `data_base_embedding` ya existe en el modelo de datos, pero desconectado de esta condición:**
  - `resources_type` (tabla, entidad `ResourcesType.java`) tiene 3 códigos seed: `data_base_memory`, `data_base_embedding` ("Documentos de la base de datos vectorial"), `llm_cache` (`liquibase/changelogs/data/csv/resources_type.csv`).
  - `Resources.resourcesType` (`@ManyToOne`) — cada `Resources` (ej. el `resourceId=24` del ejemplo de P-34) tiene un tipo.
  - `tools_implemented3.csv` ya usa exactamente este código para ligar la tool `rag_document_search` (la del agente de `edi-ai-operator`, ver P-28) a un `resources_type` con `code = 'data_base_embedding'` — **esta es la fila que el usuario creó para cerrar el checklist de P-28**. O sea: `data_base_embedding` ya es, por diseño, "el tipo de recurso cuyos documentos deben estar en la base vectorial".
  - Pese a eso, **la API de upload (`/storage/upload`, `UploadFileRequest`) no tiene ningún campo `resourceId`/`resourceType`** — no hay forma de que `validateAndSendToSaveDocsOnVecstore` sepa a qué `Resource` (ni a qué `resources_type`) pertenece el archivo que se está subiendo.
- **Por qué esto es un gap real, no solo una idea nueva:** el flujo de `aiResourcesManagement` (ver P-34) es de **dos pasos separados**: (1) `POST /storage/upload` (sin `resourceId`, dispara o no vectorización solo por `codeTypeDocument`), y (2) `POST {resourceId}/documents/create` (`ResourcesServiceImpl.createDocument`, con `filePath` del paso 1) — que **tampoco** dispara vectorización (confirmado en P-34, solo hace `documentRepository.save`). Es decir: **hoy no existe ningún punto del flujo donde "este documento pertenece a un recurso `data_base_embedding`" se traduzca en "vectorizar este documento"** — a menos que, por coincidencia, su `codeTypeDocument` ya esté en la lista `is_vectorizable`.
- **Impacto:** un documento subido específicamente para alimentar `rag_document_search` (vía un `Resource` de tipo `data_base_embedding`) puede terminar **sin vectorizar**, si su `codeTypeDocument` no está en la lista `is_vectorizable` — silenciosamente, sin error visible, porque la condición actual no sabe nada del recurso al que pertenece.
- **Lo que falta para corregirlo (dos opciones, no implementado, solo diagnosticado):**
  1. **En el upload (`/storage/upload`):** agregar `resourceId` opcional a `UploadFileRequest`/`StorageController`; en `validateAndSendToSaveDocsOnVecstore`, si viene `resourceId`, resolver `Resources.resourcesType.code` y disparar vectorización también si `code == 'data_base_embedding'` (condición OR con la ya existente por `codeTypeDocument`).
  2. **En el registro (`{resourceId}/documents/create`, `ResourcesServiceImpl.createDocument`):** dado que ahí SÍ se conoce `resourceId` (viene en el path), resolver `resource.resourcesType.code` y, si es `data_base_embedding`, disparar la vectorización en ese punto (reutilizando el mecanismo ya existente de `VectorStoreManager.saveDocumentOnVectorStore`/`VectorStoreController`, que ya expone exactamente esa operación como llamada explícita). Esta opción no requiere tocar el contrato de `/storage/upload`.
  - La opción 2 es menos invasiva (no cambia el contrato de subida, que además usan otros flujos que no pasan por `aiResourcesManagement`) y resuelve el gap en el mismo punto donde ya se detectó el hueco de P-34 (borrado) — probablemente conviene resolver ambos (P-34 y P-36) juntos en `ResourcesServiceImpl`, ya que los dos requieren la misma dependencia nueva (`VectorStoreService`/`VectorStoreManager`) y la misma resolución de `indexVecstore` para este módulo.

**Implementación (2026-08-13), `edi-ai-proyectos-backend`:**

- **`ResourcesServiceImpl.createDocument`:** ahora setea `Document.uniqueCode = request.getFilePath()` (además de `uniqueCodeStorage`, que ya se seteaba) — mismo criterio que el resto del repo (`unique_code` == nombre del objeto en storage), necesario para poder vectorizar/desvectorizar por `unique_code`. Después de guardar el documento, llama a un nuevo helper privado `triggerVectorizationIfDataBaseEmbedding(resource, document)`:
  - Si `resource.getResourcesType().getCode()` **no** es `data_base_embedding` (constante nueva `Constants.CODE_RESOURCE_TYPE_DATA_BASE_EMBEDDING`), no hace nada.
  - Si lo es, resuelve `indexVecstore = "project-" + resource.getArea().getProject().getId()` — la cadena `Resources.area.project.id` es el mismo "companyId"/project que usa `ResourcesCustomRepositoryImpl` para filtrar (`areaJoin.get("project").get("id")`), y coincide con la convención `project_{id}` que ya usa `edi-ai-operator`/`rag_document_search` (P-28) y el resto de `VectorStoreManager` (sanitizado a `project_{id}` por `ai-rag-service-manager`, P-25).
  - Llama a `VectorStoreService.saveDocumentOnVecstoreAsync(indexVecstore, document)` — **método ya existente**, ya usado por `KnowledgeBaseManager` para el mismo propósito, y ya compatible con P-31 (descarga el archivo con `GetFileRequest(uniqueCode, Optional.empty())`, sin mandar bucket). No se escribió ningún cliente HTTP nuevo — se reusó infraestructura ya probada.
  - Todo el bloque está en un `try/catch`: un fallo al disparar vectorización no rompe la creación del documento (mismo criterio defensivo que `StorageManager.validateAndSendToSaveDocsOnVecstore`).
- **Opción 1 (no implementada, dejada como nota explícita en el código):** comentarios agregados en `UploadFileRequest.java` y `StorageManager.validateAndSendToSaveDocsOnVecstore` explicando que ese endpoint no tiene `resourceId` y, si en el futuro hace falta que también dispare vectorización por tipo de recurso, hay que agregarlo ahí siguiendo el mismo patrón.
- **Hallazgo colateral corregido (no era parte de P-36, bloqueaba probarlo):** `ResourcesServiceImpl.createDocument` nunca seteaba `Document.user` (`id_user`), campo `NOT NULL` en la tabla `document_` — el insert **siempre fallaba** con `DataIntegrityViolationException` antes de este fix. Confirmado contra la base de datos real (`POST {resourceId}/documents/create` devolvía `500` en todos los intentos hasta agregar `.user(user)` al builder). Corregido con autorización explícita del usuario tras preguntarle. De paso, esto también corrigió que `buildDocumentResponse` devolviera siempre `filePath: null` (usaba `document.getUniqueCode()`, que ahora sí se puebla).
- **Verificación real (no simulada):**
  1. `./gradlew compileJava compileTestJava` → `BUILD SUCCESSFUL`.
  2. Consulta real (solo lectura) a la base de datos de dev (`37.60.225.200`) confirmó un `Resources` real ya existente de tipo `data_base_embedding`: `id=25`, `code=company_document_vector_query`, `area_id=76`, `project_id=93` — el mismo proyecto 93 usado en la prueba end-to-end de P-28.
  3. Con Java real corriendo (puerto 7001, perfil `dev`) contra esa base real: `POST /resources/25/documents/create` → `201 Created` (documento id `5942`).
  4. **Log real de Java confirma el trigger disparando exactamente como se diseñó:** `Disparando vectorizacion para documento 5942 (resource 25, data_base_embedding) en project-93` — `indexVecstore` resuelto correctamente a `project-93`, coincidiendo con el `project_id` real del resource.
  5. La llamada HTTP posterior a `ai-rag-service-manager` falló (`Error disparando vectorizacion ...: I/O error ... "ai-rag-service-manager"`) — **no por un bug de este cambio**: `ai-rag-service-manager` está configurado en este ambiente de dev con el hostname Docker `ai-rag-service-manager:7006`, que no resuelve fuera de una red docker-compose (limitación de probar Java localmente, no del código); adicionalmente, las credenciales de GCS no están disponibles en este entorno (`edward-creds.json` fue eliminado, sin ADC alternativo configurado) — esta segunda limitación también afecta a **todos** los flujos de vectorización preexistentes de Java (`/storage/upload`, `KnowledgeBaseManager`, etc.), no es específica de este cambio.
- **Pendiente para verificación completa (fuera de alcance de este cambio puntual):** probar el round-trip real (documento efectivamente vectorizado y buscable en Milvus) requiere un ambiente donde `ai-rag-service-manager` sea resoluble por Java (docker-compose real, o túnel/hosts local) y tenga credenciales GCS válidas — ninguna de las dos cosas depende de este código.
- **Acción sugerida:** ver arriba — resuelto. La opción 1 (upload) queda documentada para el futuro si se necesita.

### P-37 — `VECTOR_K_SIMILILARITY` (uso completo) y "adjacent chunks" (expansión de contexto) en `edi-ai-analysis-ai`: no replicado en `ai-rag-service-manager` ni en el consumidor real (`rag_document_search`)

- **Estado:** Resuelto — implementado el 2026-08-18, a pedido explícito del usuario ("ajusta P-38, P-37 y P-35... documenta muy bien el servicio que consume y la funcionalidad de adyacentes").
- **Detectado:** 2026-08-13, profundizando P-35 en `edi-ai-analysis-ai` (`app/utils/tools_agent.py`, `app/utils/tools_document.py`).
- **Resuelto el:** 2026-08-18.
- **Contexto obligatorio para este análisis (indicado por el usuario):** el consumidor real de `ai-rag-service-manager` para búsqueda semántica **no es Java** — es la tool `rag_document_search` de `edi-ai-operator` (P-28). Todo el análisis de impacto de abajo, y toda la implementación, está pensado y hecho en función de esa tool, no de un hipotético consumidor Java.
- **Nota de estado del repo `edi-ai-operator`, ya resuelta:** al momento del análisis (2026-08-13) el checkout local estaba en `eatroyano/dev/feature/channel_gateway`, sin `rag_document_search.py`. El usuario cambió a `eatroyano/dev/feature/embbedings-vectors` antes de pedir la implementación — confirmado, es la rama correcta, con el archivo presente y árbol limpio.

#### 1. `VECTOR_K_SIMILILARITY` — alcance completo (ampliando P-35)

P-35 ya documentó que este parámetro no se aplica en `ai-rag-service-manager` porque el único flujo de Java que lo lee (`askInDocuments`) no está migrado. Profundizando en `edi-ai-analysis-ai/app/utils/tools_agent.py`, el parámetro se usa en **1 de 3** llamadas a `similarity_search`:

| Línea | Método | `k` usado | ¿Configurable? |
|---|---|---|---|
| 348 | `find_in_all_documents_tool` | `k=10` | No, hardcodeado |
| 434 | `find_adjacent_chunks_old` | `k=number_results` (=8, hardcodeado arriba) | No |
| 462 | `find_in_all_documents` (el que realmente arma la respuesta de la tool) | `k=self.k_similarity` | **Sí**, vía `VECTOR_K_SIMILILARITY` |

O sea: incluso dentro de `edi-ai-analysis-ai`, solo el retrieval principal usa el K configurable — los otros dos (búsqueda genérica y expansión "old") están hardcodeados. **Equivalente hoy en `rag_document_search` (operator):** `_DEFAULT_TOP_K = 5`, hardcodeado, no conectado a ninguna tabla de parámetros — mismo problema de fondo que P-35 ya señaló, confirmado en el código real de la tool.

#### 2. "Adjacent chunks" — qué es

Cuando el retrieval por similitud encuentra un chunk relevante, `edi-ai-analysis-ai` no lo devuelve aislado — expande el contexto trayendo texto adyacente, con **dos implementaciones paralelas** seleccionadas automáticamente por chunk según qué metadata tenga disponible (`split_documents_by_valid_chunk`, `tools_document.py:60-83`, según presencia de `start_index` + `id`):

- **`find_adjacent_chunks_new`** (chunks "nuevos", indexados con `start_index`): agrupa los chunks encontrados por documento, calcula una ventana de ±500 caracteres alrededor del `start_index` de cada match (`assign_fragment_to_documents`), **fusiona ventanas solapadas o adyacentes en un rango mínimo sin duplicar texto** (`unir_fragmentos`), **vuelve a descargar el documento original completo de storage** (`download_and_process_document`, busca `{unique_code}_storage` — una copia en texto plano que `edi-ai-analysis-ai` guarda aparte al indexar, específicamente para esto) y recorta el texto exacto por offset de caracteres (`txt_content[start:end]`). Resultado: un contexto contiguo y limpio, no chunks fragmentados.
- **`find_adjacent_chunks_old`** (fallback para chunks indexados antes de tener `start_index`, ej. legacy): toma el primer chunk encontrado, lee su `position` (índice secuencial dentro del documento) y hace una **segunda búsqueda** filtrada por `id == codigo AND position in [pos+1 .. pos+8]` — trae los siguientes 8 chunks consecutivos del mismo documento ya indexados, los deduplica y ordena por `position` (`merge_and_deduplicate_docs`), y concatena su `page_content` a continuación del chunk original.

#### 3. Qué hay hoy en `ai-rag-service-manager` / `rag_document_search` — nada de esto

- `search_similar_documents` devuelve cada resultado tal cual vino del vector store, sin fusión ni expansión de contexto adyacente — confirmado leyendo `document_embedding_service.py`.
- **Hallazgo adicional, compuesto con lo anterior:** el `text_preview` que arma `search_similar_documents` está truncado a **200 caracteres** (`payload.get("text", "")[:200]`, `document_embedding_service.py:254`) — y `rag_document_search._format_results` (operator) usa ese mismo `textPreview` truncado para construir el prompt que recibe `invoke_model`. O sea: hoy el LLM del operator responde con fragmentos de **como mucho 200 caracteres** por resultado, muy por debajo incluso del tamaño de un chunk completo (hasta 1000 caracteres por default, ver P-35) — antes de pensar siquiera en "adjacent chunks", ya hay un límite de contexto más chico de lo necesario en el propio contrato de la API.

#### 4. Implementación (2026-08-18) — pensada para `rag_document_search`, no Java

- **Encaje con el alcance ya decidido (P-05):** confirmado — es una mejora de **calidad de retrieval** (parte de "embeddings"), no síntesis de LLM. No hubo conflicto de arquitectura.
- **`app/core/config.py`:** dos settings nuevos — `rag_adjacent_window_chars` (default 500, ventana ± alrededor del match para la variante "nueva") y `rag_adjacent_chunk_count` (default 8, cantidad de chunks siguientes para la variante "legacy").
- **`app/services/rag/rag_service.py`:** `RAGService.index_documents`/`_split_text` ahora persisten `start_index`/`end_index` (offset de caracteres) en el `payload` de cada chunk, además de `chunk_index` (que ya existía). `_split_text` cambió su tipo de retorno de `list[str]` a `list[tuple[str, int, int]]` — único caller interno (`index_documents`), sin impacto externo. Documentos indexados antes de este cambio no tienen esta metadata — quedan en el camino "legacy" (variante 2, abajo), sin retro-completarse.
- **`app/services/embedding/document_embedding_service.py`:** `search_similar_documents` ahora acepta `expand_context: bool = False`. Con `True`, un nuevo helper `_expand_context` rellena `expanded_text` por resultado, eligiendo automáticamente entre dos estrategias (`_expand_single_result`), igual que el `valid_docs`/`invalid_docs` de `edi-ai-analysis-ai`:
  1. **`_expand_via_source_reslice`** (chunks con `start_index`/`end_index`): re-descarga el documento original de storage (mismo `file_name`/`bucket` que ya vienen en la metadata del chunk desde que se indexó) y re-extrae texto vía `_extract_text_from_file` (misma función que se usa al indexar — garantiza texto idéntico), luego recorta `[start_index - ventana, end_index + ventana]`. Usa un cache por `(file_name, bucket)` dentro del request para no re-descargar el mismo archivo si varios resultados matchean del mismo documento. A diferencia de `edi-ai-analysis-ai` (que necesitaba una copia de texto plano aparte, `{unique_code}_storage`), acá no hizo falta ninguna copia adicional — storage y extracción de texto ya viven en este mismo servicio.
  2. **`_expand_via_adjacent_chunk_index`** (chunks sin esa metadata, legacy): en vez de extender el motor de filtros de Milvus para soportar un filtro tipo "IN"/rango (`_build_filter_expression` solo soporta igualdad), se optó por la alternativa más simple ya identificada en el análisis original: `list_records`/`query` filtrando solo por `unique_code` (igualdad, ya soportado), y filtrar/ordenar por `chunk_index` en Python. Más barato que lo que hace `edi-ai-analysis-ai` (que reusa una búsqueda vectorial completa solo para poder filtrar).
  - Cada resultado se expande de forma aislada: un fallo (ej. archivo ya no existe en el bucket) se loguea y ese resultado queda sin `expanded_text`, sin romper los demás ni la búsqueda.
- **`app/schemas/embedding.py`:** `SearchSimilarDocumentsRequest.expand_context` (default `False`, sin efecto en nadie que no lo pida) y `DocumentSummaryResponse.expanded_text` (opcional, `None` salvo que se haya pedido y podido expandir — también aparece en `list_documents`, siempre `None` ahí, ese endpoint nunca pide expansión).
- **`app/api/routes/embedding_controller.py`:** pasa `expand_context` del request al service.
- **Lado `edi-ai-operator` (documentado en detalle en `integracion-operator-rag.md` sección 3.6):** `rag_service_client.search_similar_documents` acepta `expand_context`; `rag_document_search.py` lo pide siempre (`expand_context=True`) y `_format_results` prefiere `expandedText` sobre `textPreview` (200 caracteres) — cierra también el hallazgo del punto 3 (antes el LLM nunca veía más de 200 caracteres por resultado, con o sin fusión de chunks). `RagDocumentSearchSimulationService`/`RagSearchResultSummary` (API de simulación, sección 3.5) actualizados igual, para que el preview sea representativo.
- **K_SIMILARITY:** resuelto por separado en **P-38** — `rag_document_search` ya no hardcodea `top_k`.
- **Verificación real:** ver detalle completo en `integracion-operator-rag.md` sección 3.6 — `ruff`/`mypy` limpios en ambos repos; pruebas de integración reales (clases de producción reales, solo Milvus/storage/embedding mockeados) cubriendo las 4 variantes (sin expansión, expansión nueva con tamaño de ventana exacto verificado, expansión legacy con orden/filtro correcto, fallo aislado sin romper la búsqueda); imports reales limpios del lado operator.
- **Verificación end-to-end real, 2026-08-18 (el usuario desselló Vault local):** con `ai-rag-service-manager` corriendo vía `run-local-vault.sh` (GCS y OpenAI reales), se subió un documento real (`/storage/upload`), se indexó (`/embedding/save_document_vecstore`, embeddings reales, colección `project_p37test`) y se buscó con `expandContext: true` (`/embedding/search_similar_documents`) — resultado real con `score=0.67`. **Confirmado el valor concreto de la funcionalidad:** el texto de prueba tenía la frase que respondía la query recién después del caracter 200 (rodeada de relleno); `textPreview` (200 caracteres) cortaba antes de llegar a ella, `expandedText` la trajo completa — re-descarga real de GCS, re-extracción real, recorte real por offset de caracteres, todo verificado con servicios reales, no mockeados.

### P-38 — `_DEFAULT_TOP_K`/`_PREVIEW_TOP_K` hardcodeados en `edi-ai-operator`/`rag_document_search` — no usan el mecanismo de parámetros DB-configurables ya existente

- **Estado:** Resuelto — implementado el 2026-08-18, a pedido explícito del usuario.
- **Resuelto el:** 2026-08-18.
- **Detectado:** 2026-08-13, separando de P-37 el punto de `VECTOR_K_SIMILILARITY`/top_k del lado `edi-ai-operator` en un pendiente propio y accionable.
- **Diferencia clave con el `VECTOR_K_SIMILILARITY` de P-35:** aquel está bloqueado porque depende de que Java migre `askInDocuments` a `ai-rag-service-manager` (fuera de alcance, sin fecha). **Este no depende de nada externo** — `rag_document_search` ya llama a `search_similar_documents`, que **ya acepta `top_k` por request** (confirmado en P-35); lo único que falta es dejar de hardcodear el valor que se le manda.
- **Ubicación exacta:**
  - `src/agents/deep_insight_engine/tools/rag_document_search.py:20` — `_DEFAULT_TOP_K = 5`, usado por la tool real (`search_similar_documents(index_vecstore, query, top_k=_DEFAULT_TOP_K)`, línea 39).
  - `src/service/rag_document_search/rag_document_search_simulation_service.py:30` — `_PREVIEW_TOP_K = 5`, una **constante separada** (mismo valor, pero no la misma variable) usada solo para el preview de retrieval crudo en `POST /rag-document-search/simulate` (no afecta la respuesta real del LLM, que pasa por `rag_document_search(...)` y por lo tanto por `_DEFAULT_TOP_K`).
- **El mecanismo para hacerlo configurable ya existe en este mismo repo, no hay que inventarlo:** `edi-ai-operator` tiene una tabla `parameters` (`database/entities/parameter.py`: `code`, `description`, `value`) — **estructuralmente idéntica** a la tabla `Parameters` de Java que usa `VECTOR_K_SIMILILARITY`/`VECTOR_CHUNK_SIZE`/etc. Ya hay un patrón establecido y en uso para leer estos valores: `ConfigKey` (enum en `src/utils/parameters_key_config.py`, ej. `DUCKDB_MAX_RETRIES`, `N_RELATED_MESSAGES`) + `ParameterRepositoryInterface.get_by_code`/`get_by_codes`, consumido hoy por `PromptConfigService` (`repository_parameter.get_by_codes(ConfigKey.get_all_codes())`). Agregar un código nuevo (ej. `RAG_DOCUMENT_SEARCH_TOP_K`) seguiría exactamente ese mismo patrón ya probado — no es una construcción desde cero.
- **Impacto de no resolverlo:** un admin no puede ajustar cuántos fragmentos recupera `rag_document_search` (más contexto vs. más precisión/costo) sin un deploy de código — igual que P-35 en su momento, pero en un lugar donde sí es inmediatamente accionable.
- **Relación con P-37:** si se decide implementar la expansión de "adjacent chunks" (P-37), el `top_k` que dispara esa expansión seguiría siendo este mismo valor — no son cambios independientes en la práctica, aunque son pendientes separados.
**Implementación (2026-08-18), `edi-ai-operator`:**

- **Primera versión:** se creó un parámetro nuevo, `RAG_DOCUMENT_SEARCH_TOP_K`, separado de `VECTOR_K_SIMILILARITY`.
- **Consolidado el mismo día, a pedido explícito del usuario:** `edi-ai-proyectos-backend` (Java) y `edi-ai-operator` **comparten la misma base de datos física** (mismo host `37.60.225.200`, misma DB `ediai`, misma tabla `parameters`/`Parameters`) pese a ser microservicios y repos distintos — confirmado por el usuario y verificado con una consulta `psql` real: la fila `VECTOR_K_SIMILILARITY` **ya existía**, creada para `AnalysisInfoManager.askInDocuments` (Java, ver P-35), con `value=4`. Crear `RAG_DOCUMENT_SEARCH_TOP_K` como parámetro nuevo hubiera sido una duplicación innecesaria de un valor que ya existe en la misma fila accesible desde ambos repos. Se descartó el parámetro nuevo y se reusó `VECTOR_K_SIMILILARITY` directamente.
- **`src/utils/parameters_key_config.py`:** `ConfigKey.VECTOR_K_SIMILILARITY = "VECTOR_K_SIMILILARITY"` (mismo string que usa Java, no un alias) reemplaza al `RAG_DOCUMENT_SEARCH_TOP_K` descartado. `ChatAgentConfig.rag_document_search_top_k` default ajustado de `5` a `4` (mismo default histórico que la fila real).
- **`src/service/deep_insight_engine/prompt_config_service.py`:** `load_parameters_config()` puebla `rag_document_search_top_k` desde `ConfigKey.VECTOR_K_SIMILILARITY` (antes leía la clave del parámetro descartado).
- **`src/agents/deep_insight_engine/deep_insight_utils.py`:** sin cambios — `build_parameters` sigue inyectando `parameters["rag_document_search_top_k"]` desde `parameters_config`, el nombre del campo Python no cambió (describe el rol en este repo), solo cambió de qué fila de la base de datos se llena.
- **`src/agents/deep_insight_engine/tools/rag_document_search.py`:** `_DEFAULT_TOP_K` ajustado de `5` a `4` (mismo default histórico de `VECTOR_K_SIMILILARITY`).
- **`src/service/rag_document_search/rag_document_search_simulation_service.py`:** `_PREVIEW_TOP_K` ajustado de `5` a `4`, mismo motivo.
- **Nota de diseño importante, documentada a propósito:** este parámetro ahora es compartido entre dos flujos conceptualmente similares pero funcionalmente distintos — `AnalysisInfoManager.askInDocuments` (Java → `analysis-ai-service`) y `rag_document_search` (`edi-ai-operator` → `ai-rag-service-manager`), sobre corpus y modelos de embeddings potencialmente distintos. Es una decisión deliberada del usuario (evitar duplicar un valor que ya existe en la misma base compartida), no un descubrimiento accidental — pero implica que ajustar `VECTOR_K_SIMILILARITY` pensando solo en uno de los dos flujos afecta también al otro.
- **Verificación real:** import real de los 5 módulos tocados — limpio. Consulta `psql` real (solo lectura) contra la base de datos compartida confirmando la fila real: `VECTOR_K_SIMILILARITY | 4 | número de documentos similares a recuperar en una búsqueda por similitud`. **No se pudo completar una prueba end-to-end vía SQLAlchemy** (`PromptConfigService.load_parameters_config()` con repositorios reales): mismo error preexistente y no relacionado (`InvalidRequestError: ... 'CatResources'`, ver `integracion-operator-rag.md` sección 3.6) que bloquea *cualquier* query ORM real en este repo ahora mismo (la primera consulta de cualquier tipo dispara la validación de *todos* los mappers registrados, incluyendo el de `Document`, que está roto) — no es un problema de este cambio ni específico de `Parameter`.
- **Acción sugerida:** ninguna — resuelto. Ajustar `top_k` sin deploy ahora significa editar la fila `VECTOR_K_SIMILILARITY` ya existente — mismo procedimiento que ya usa el equipo para `DUCKDB_MAX_RETRIES` u otros, sin crear nada nuevo.

### P-39 — Extracción de texto de PDF era un decode crudo de bytes, no un parseo real (`_extract_text_from_file`)

- **Estado:** Resuelto.
- **Detectado:** 2026-08-18, durante la primera prueba end-to-end real de punta a punta pedida por el usuario (Java → `ai-rag-service-manager` → `edi-ai-operator`, con un PDF real de 14 páginas — política de privacidad de un tercero, usado solo como caso de prueba).
- **Resuelto el:** 2026-08-18.
- **Ubicación:** `app/services/embedding/document_embedding_service.py` (`_extract_text_from_file`/`_extract_text_from_pdf`).
- **Descripción:** `_extract_text_from_file`, para `extension == "pdf"`, hacía `file_content.decode("latin-1", errors="ignore")` — decodificaba los **bytes crudos** del archivo PDF como si fueran texto plano, en vez de extraer el contenido real. Un PDF moderno comprime el contenido de cada página (`FlateDecode`); ese decode nunca podía producir el texto legible, solo lo que casualmente aparece sin comprimir en la estructura binaria del archivo (tabla `xref`, anotaciones de hipervínculo, títulos de marcadores en hexadecimal UTF-16).
- **Cómo se detectó (no fue una inspección de código, fue un resultado real incorrecto):** se subió el PDF real vía Java (`/storage/upload` → `/resources/25/documents/create`, resource `data_base_embedding`, proyecto 93), se vectorizó contra `ai-rag-service-manager` real (77 chunks), y se consultó vía `edi-ai-operator` (`/rag-document-search/simulate`) con una pregunta real sobre el contenido ("¿quién es el responsable...?"). La respuesta del LLM fue incorrecta/vacía en el punto clave, y los `textPreview`/`expandedText` de los resultados mostraban literalmente estructura binaria de PDF (`26 0 obj\n<</Type/Annot/Subtype/Link/Border[0 0 0]/Rect[...`) en vez de los párrafos reales del aviso de privacidad.
- **Impacto real:** **todo PDF vectorizado hasta ahora en el sistema** (incluyendo pruebas previas de esta sesión, ej. la de P-28 ronda 3) quedó indexado con contenido no representativo del documento real — cualquier búsqueda semántica o respuesta del agente basada en esos PDFs es, en el mejor caso, coincidencia (títulos de marcadores/anotaciones que sí quedan legibles) y en el peor caso, contenido irrelevante o vacío. No afecta a `.txt`/`.md`/`.json`/etc. (esos sí se decodifican correctamente como texto real).
- **Cómo lo resuelve `edi-ai-analysis-ai` (a pedido del usuario, se validó antes de implementar):** `ReadTextBase64._read_text_pdf_without_images` usa `pdfplumber` (abre el PDF real, extrae texto página por página con `page.extract_text()`, uniendo con el separador `\n*page-break*\n`). Ese mismo repo también soporta el caso de PDFs *solo-imágenes* (detectado con `fitz`/PyMuPDF) vía OCR de Google Cloud Vision, y otros formatos (`.doc` con Spire.Doc, `.ppt` con Spire.Presentation + OCR, `.xls` con pandas) — **deliberadamente no replicado aquí**, ver "Fuera de alcance" abajo.
- **Implementación:**
  - `pyproject.toml`: agregada `pdfplumber>=0.11.0,<1.0.0` (misma librería que el caso de referencia; trae `pdfminer.six`/`pypdfium2`/`pillow` como transitivas).
  - `document_embedding_service.py`: nuevo método `_extract_text_from_pdf` — abre el PDF desde bytes en memoria (`pdfplumber.open(io.BytesIO(file_content))`, sin archivos temporales, a diferencia del caso de referencia que sí los usa), extrae texto por página y une con `\n*page-break*\n` (mismo separador que `edi-ai-analysis-ai`, por consistencia). `_extract_text_from_file` delega a este método para `extension == "pdf"` en vez de decodificar bytes crudos.
- **Fuera de alcance (deliberado, no implementado):** detección de PDF-solo-imágenes + OCR vía Google Cloud Vision (requiere credenciales/config de Google nuevas, no existentes hoy en este repo) — un PDF escaneado sin capa de texto real hoy simplemente produce páginas vacías (`page.extract_text() or ""`), no un error, pero tampoco extrae nada útil. Tampoco se agregó soporte real para `.doc`/`.ppt`/`.xls` (vía Spire/pandas) — esos formatos siguen cayendo al decode UTF-8 genérico, con el mismo problema que tenía PDF antes de este fix, sin reportar como bug porque no fue lo que se probó ni lo que se pidió corregir hoy.
- **Verificación real, con `ai-rag-service-manager` real corriendo:**
  1. `ruff check .` y `mypy app` limpios tras el cambio.
  2. Extracción real contra el PDF de prueba (14 páginas, 61754 bytes): **20599 caracteres de texto real y legible** ("Políticas de privacidad... CONSORCIO ARA...") en vez de estructura binaria.
  3. **Re-vectorización real de punta a punta:** se borraron los 77 chunks viejos (`DELETE /embedding/delete_document`) y se volvió a indexar el mismo documento (`POST /embedding/save_document_vecstore`, mismo payload) — esta vez **26 chunks** (coherente con 20599 caracteres reales vs. 61754 bytes crudos de antes).
  4. **Re-consulta real vía `edi-ai-operator`** (misma pregunta, mismo endpoint `/rag-document-search/simulate`): scores de similitud subieron de 0.30–0.44 a **0.61–0.63**, y la respuesta del LLM ahora es correcta y completa: identifica a "CONSORCIO ARA, S.A.B. de C.V." como responsable, con domicilio exacto, y detalla el procedimiento completo de ejercicio de derechos ARCO (correo `arco@ara.com.mx`, datos requeridos) — todo tomado del contenido real del PDF.
- **Acción sugerida:** ninguna para el caso de texto real, que es el resuelto aquí. Si en el futuro se necesita soportar PDFs escaneados (solo imágenes) o `.doc`/`.ppt`/`.xls`, tratarlo como un pendiente nuevo — replicar OCR/Spire tiene costo de credenciales/dependencias que no se justificaba agregar solo por este hallazgo puntual.

---

## Pendiente general (2026-08-13)

Con P-24, P-28, P-31 y P-32 resueltos y verificados a nivel de servicio individual (imports reales, builds reales, y en varios casos HTTP real contra `ai-rag-service-manager`), **queda pendiente probar el flujo completo de punta a punta: frontend → backends (Java, operator, chat-backend) → `ai-rag-service-manager`**, con los servicios reales corriendo en conjunto (no cada uno aislado, que es como se validó hasta ahora). Ninguna ronda de verificación de este documento ejercitó ese camino completo todavía.

**Actualización 2026-08-18:** se ejecutó una primera prueba real de punta a punta con 3 de los 4 servicios (Java → `ai-rag-service-manager` → `edi-ai-operator`, con un PDF real subido, vectorizado y consultado con éxito — ver P-39). Sigue pendiente el frontend y `edi-ai-chat-backend` en esa misma cadena, y probar `rag_document_search` integrada al agente completo (no solo vía `/simulate`, ver checklist de P-28).

P-33 y P-34 (detectados el mismo día, 2026-08-13) ya fueron resueltos con posterioridad (ver sus entradas respectivas) — inicialmente quedaron como análisis puro a pedido explícito del usuario, hasta determinar si aplicaban.

