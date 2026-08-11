# API — ai-rag-service-manager

Documentación de contrato de **todos** los endpoints HTTP que expone el microservicio, incluyendo los que no aparecían en el README (`storage`). Generada a partir del código en `app/api/routes/` y `app/schemas/` — no de una fuente externa.

Prefijo base de todas las rutas versionadas: `settings.api_prefix`, por defecto `/api/v1`.

Documentación interactiva (Swagger/Redoc) siempre disponible en runtime:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Convenciones

- **Autenticación:** ninguno de los endpoints requiere autenticación ni autorización (ver `pendientes.md` P-13).
- **Formato de nombres de campo JSON:**
  - `rag-services`: `snake_case` (los schemas no definen alias).
  - `embedding` y `storage`: `camelCase` (los schemas usan `get_camel_case_config`, con `populate_by_name=True`, así que también aceptan `snake_case` de entrada, pero la salida serializa en `camelCase`).
  - Ver `pendientes.md` P-15.
- **Errores:** los controllers de `embedding` capturan cualquier excepción y responden `500` con `detail` descriptivo. `rag-services` propaga `HTTPException` explícitas del service (`404`, `409`). `storage` propaga `HTTPException` explícitas o `422` por campos faltantes en `/storage/chunk`.

---

## Root

### `GET /`

Sin autenticación. Metadata básica del servicio.

**Respuesta 200**

```json
{
  "service": "ai-rag-service-manager",
  "environment": "development",
  "api_prefix": "/api/v1",
  "docs": "/docs"
}
```

---

## Health — `/api/v1/health`

Archivo: `app/api/routes/health_controller.py`.

### `GET /api/v1/health/live`

Liveness simple, sin dependencias externas.

**Respuesta 200**

```json
{ "status": "alive" }
```

### `GET /api/v1/health/ready`

Readiness real: devuelve `503` si alguna integración marcada como **crítica** está habilitada pero no logró completarse en el startup. Config Server y Eureka son "críticas" por defecto (`READINESS_CRITICAL_DEPENDENCIES=config_server,eureka`), configurable vía env var — ver `pendientes.md` P-14. Una integración deshabilitada (variables ausentes) nunca cuenta como fallo, sin importar esa lista.

**Respuesta 200** (todo deshabilitado o todo lo habilitado se completó)

```json
{
  "status": "ready",
  "service": "ai-rag-service-manager",
  "environment": "development",
  "failed_dependencies": [],
  "blocking_failures": [],
  "integrations": {
    "config_server": { "enabled": false, "loaded": false },
    "eureka": { "enabled": false, "registered": false }
  }
}
```

**Respuesta 503** (ej. `EUREKA_ENABLED=true` pero el registro agotó reintentos)

```json
{
  "status": "not_ready",
  "service": "ai-rag-service-manager",
  "environment": "development",
  "failed_dependencies": ["eureka"],
  "blocking_failures": ["eureka"],
  "integrations": {
    "config_server": { "enabled": false, "loaded": false },
    "eureka": { "enabled": true, "registered": false, "error": "registration retries exhausted" }
  }
}
```

> `failed_dependencies` lista toda integración habilitada que falló, aunque no sea crítica; `blocking_failures` es el subconjunto que efectivamente causó el `503`.

---

## RAG Services — `/api/v1/rag-services`

Archivo: `app/api/routes/rag_services_controller.py`. CRUD de definiciones operativas de servicios RAG. Persistencia **en memoria** (`InMemoryRagServiceRepository`, ver `pendientes.md` P-09) — no sobrevive a un restart.

**Convención de nombres:** al igual que `embedding`/`storage`, los schemas usan `camelCase` en el JSON (alineado en `pendientes.md` P-15; antes usaban `snake_case`, inconsistente con el resto de la API). También aceptan `snake_case` de entrada por compatibilidad (`populate_by_name=True`), pero la salida siempre serializa en `camelCase`.

Entidad `RagService` (`app/domain/entities/rag_service.py`):

| Campo (JSON) | Tipo | Notas |
|---|---|---|
| `serviceId` | `string` | UUID generado por el server, solo lectura |
| `name` | `string` | 3–100 caracteres, único (case-insensitive) |
| `description` | `string \| null` | máx. 300 caracteres |
| `llmProvider` | `string` | 2–50 caracteres |
| `chatModel` | `string` | 2–100 caracteres |
| `embeddingModel` | `string` | 2–100 caracteres |
| `vectorBackend` | `string` | 2–50 caracteres |
| `baseUrl` | `string \| null` | opcional |
| `status` | `enum` | `draft` \| `active` \| `disabled` |
| `metadata` | `dict[str, str]` | libre |
| `createdAt` / `updatedAt` | `datetime` | ISO 8601, solo lectura |

> Nota funcional: estas definiciones **no se consultan** en ningún punto del flujo de `/embedding/*` o `/rag_query`. Son dos capacidades administradas por separado hoy (ver análisis general en la conversación / `pendientes.md` P-04, P-05).

### `GET /api/v1/rag-services`

Lista todos los registros.

**Respuesta 200** — `RagServiceListResponse`

```json
{ "items": [ { "serviceId": "...", "name": "...", "...": "..." } ], "total": 1 }
```

### `POST /api/v1/rag-services`

Crea una nueva definición. Falla con `409 Conflict` si ya existe un servicio con el mismo `name` (case-insensitive).

**Body** — `RagServiceCreate` (= `RagServiceBase` + `status` opcional, default `draft`)

```json
{
  "name": "soporte-interno",
  "description": "RAG para tickets de soporte",
  "llmProvider": "openai",
  "chatModel": "gpt-4o-mini",
  "embeddingModel": "text-embedding-3-small",
  "vectorBackend": "milvus",
  "baseUrl": null,
  "metadata": { "team": "cx" },
  "status": "draft"
}
```

**Respuesta 201** — `RagServiceResponse` (body anterior + `serviceId`, `createdAt`, `updatedAt`).

### `GET /api/v1/rag-services/{service_id}`

Obtiene un registro por id. `404` si no existe.

### `PUT /api/v1/rag-services/{service_id}`

Reemplazo completo del recurso. **Todos** los campos de `RagServiceUpdate` (= `RagServiceBase` + `status` requerido) son obligatorios salvo los opcionales del base. Si se cambia `name`, se vuelve a validar unicidad (`409` si colisiona).

### `PATCH /api/v1/rag-services/{service_id}/status`

Mutación parcial, solo el estado.

**Body** — `RagServiceStatusUpdate`

```json
{ "status": "active" }
```

### `DELETE /api/v1/rag-services/{service_id}`

`204 No Content` si se elimina. `404` si no existe.

---

## Embedding — `/api/v1/embedding`

Archivo: `app/api/routes/embedding_controller.py`. Todos los endpoints son `POST` con body JSON, campos en `camelCase` (salvo `list_unique_code_documents`, ver abajo). Motor subyacente: `RAGService` (`app/services/rag/rag_service.py`), con embeddings reales (`sentence-transformers`, ver `pendientes.md` P-04) sobre `VECTOR_DB_TYPE=memory|milvus` (default en memoria; Milvus real disponible, ver `pendientes.md` P-08).

### `POST /api/v1/embedding/save_document_vecstore`

Indexa un documento (texto extraído + chunking) en una colección vectorial.

**Body** — `SaveDocumentVecstoreRequest`

| Campo (camelCase) | Tipo | Requerido | Notas |
|---|---|---|---|
| `fileName` | `string` | sí | usado para inferir extensión/tipo de extracción |
| `base64` | `string \| null` | no | contenido del archivo en base64 |
| `idDocument` | `string` | sí | ID del documento; en el micro Java origen es el mismo valor que `uniqueCode`, no un ID numérico separado (ver `pendientes.md` P-20) |
| `indexVecstore` | `string` | sí | nombre de colección destino |
| `uniqueCode` | `string` | sí | código lógico del documento (para agrupar chunks) |
| `hasDocumentBase64` | `bool` | no (default `true`) | si `true`, se espera `base64` |
| `urlDownloadFile` | `string \| null` | no | alternativa a `base64`; **validado contra SSRF desde P-01** |
| `bucket` | `string \| null` | no | alternativa a `base64`/URL: descarga desde GCS |
| `listParameters` | `array<object>` | no | metadata adicional; se aplana a un dict. Cada item acepta `{"key": ..., "value": ...}` **o** `{"code": ..., "value": ...}` (esta segunda forma es la que manda el micro Java origen vía `ParametersDTO`, ver `pendientes.md` P-21); cualquier otra forma se mezcla tal cual en la metadata |

Fuente del contenido, en orden de precedencia: `base64` (si `hasDocumentBase64=true`) → `urlDownloadFile` → `bucket`. Si ninguno se provee, `500` (`ValueError: No document source was provided`).

**Respuesta 200** — `SaveDocumentVecstoreResponse`

```json
{
  "success": true,
  "message": "Document indexed successfully",
  "uniqueCode": "abc123",
  "chunksCreated": 4,
  "indexName": "soporte-interno"
}
```

### `POST /api/v1/embedding/delete_index_vecstore`

Elimina una colección completa. **Se ejecuta como `BackgroundTask`** — la respuesta 200 no garantiza que el borrado ya haya terminado.

**Body** — `DeleteIndexVecstoreRequest`: `{ "indexVecstore": "string" }`

**Respuesta 200** — `OperationStatusResponse`

```json
{ "mensaje": "Index deletion started: soporte-interno", "codigo": 200 }
```

### `POST /api/v1/embedding/delete_document`

Elimina un único documento (todos sus chunks, filtrando por `idDocument`) sin afectar el resto de la colección. A diferencia de `delete_index_vecstore`, se ejecuta **síncrono** — la respuesta ya refleja el borrado. Agregado para cubrir `pendientes.md` P-22 (Java lo usa vía `deleteEmbeddingDocument`).

**Body** — `DeleteDocumentVecstoreRequest`: `{ "indexVecstore": "string", "idDocument": "string" }`

**Respuesta 200** — `DeleteDocumentVecstoreResponse`

```json
{
  "success": true,
  "message": "Document 'doc-a-001' deleted from index 'soporte-interno'",
  "indexName": "soporte-interno",
  "idDocument": "doc-a-001",
  "deletedCount": 3
}
```

### `POST /api/v1/embedding/list_unique_code_documents`

Listado liviano (5 campos) de documentos únicos de una colección, pensado como reemplazo directo del contrato histórico `getListUniqueCodeDocuments` del micro Java origen (ver `pendientes.md` P-23). Complementa a `list_documents`, que ya cubre el mismo caso de uso con una forma de request/response más rica.

**Diferencias deliberadas con el resto de `embedding`:**

- El **body es un string JSON plano**, no un objeto: `"soporte-interno"` (no `{ "namespace": "soporte-interno" }`). Así el micro Java origen puede apuntar la URL a este servicio sin cambiar cómo arma el request (hoy manda el namespace como `HttpEntity<String>`).
- La **respuesta es un array JSON plano** (`Metadata[]`), no un objeto envolvente con `success`/`message`.

**Respuesta 200** — `UniqueCodeDocumentResponse[]`

```json
[
  {
    "namespace": "soporte-interno",
    "codigo": "doc-a-001",
    "fileName": "doc-a.txt",
    "id": "e1ff38a7-ca13-4dce-a104-bf38b76605fb",
    "nombreDocumento": "doc-a.txt"
  }
]
```

`nombreDocumento` hoy siempre repite el valor de `fileName` — no existe en la metadata actual un concepto de "nombre de documento" distinto del nombre físico del archivo.

### `POST /api/v1/embedding/list_documents`

Lista documentos lógicos (deduplicados por `unique_code`/`id_document`) de una colección.

**Body** — `ListDocumentsRequest`

| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `indexVecstore` | `string` | sí | |
| `limit` | `int` | no | 1–1000, default `settings.rag_default_list_limit` (100) |
| `metadataFilter` | `object \| null` | no | filtro exacto por igualdad de campos de payload |

**Respuesta 200** — `ListDocumentsResponse`: `{ success, indexName, totalResults, documents: [{ id, score, metadata, textPreview }], message? }`

### `POST /api/v1/embedding/get_embeddings_by_unique_code`

Recupera todos los chunks indexados de un documento, ordenados por `chunkIndex`.

**Body** — `GetEmbeddingsByUniqueCodeRequest`: `{ "indexVecstore": "string", "uniqueCode": "string" }`

**Respuesta 200** — `GetEmbeddingsByUniqueCodeResponse`: `{ success, uniqueCode, indexName, totalChunks, embeddings: [{ chunkId, score, text, chunkIndex, metadata }], message? }`

Límite interno de chunks retornados: `settings.rag_max_embeddings_per_document` (1000 por defecto).

### `POST /api/v1/embedding/search_similar_documents`

Búsqueda semántica (hoy: similitud coseno sobre embeddings hash) sobre una colección.

**Body** — `SearchSimilarDocumentsRequest`

| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `indexVecstore` | `string` | sí | |
| `query` | `string` | sí | |
| `topK` | `int` | no | 1–100, default `settings.rag_default_top_k` (5) |
| `metadataFilter` | `object \| null` | no | |

**Respuesta 200** — `SearchSimilarDocumentsResponse`: `{ success, query, indexName, totalResults, results: [...], message? }`

### `POST /api/v1/embedding/rag_query`

Recupera contexto relevante y lo devuelve junto con una respuesta placeholder. **No invoca ningún LLM** (ver `pendientes.md` P-05).

**Body** — `RagQueryRequest`

| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `question` | `string` | sí | |
| `topK` | `int` | no | 1–100, default `settings.rag_default_top_k` |
| `department` | `string \| null` | no | filtro lógico por `payload.department` |

**Respuesta 200** — `RagQueryResponse`

```json
{
  "agent": "rag",
  "question": "¿cómo se resetea la contraseña?",
  "context": "[Document 1] (relevance: 0.812)\n...",
  "sources": [ { "id": "...", "score": 0.812, "payload": { "...": "..." } } ],
  "answer": "LLM integration pending. Retrieved context returned.",
  "systemPrompt": "You are a knowledgeable assistant..."
}
```

---

## Storage — `/api/v1/storage`

Archivo: `app/api/routes/storage_controller.py`. **No documentado en el README hasta la revisión que lo detectó** (ver `pendientes.md` P-03). Replica la superficie pública de un microservicio Java de storage. Desde P-10/P-11, un upload exitoso puede disparar vectorización en background — ver la nota de cada endpoint y `pendientes.md` P-10/P-11/P-25.

### `POST /api/v1/storage/upload`

`multipart/form-data`. Sube un archivo a un bucket privado de GCS y, opcionalmente, dispara vectorización en background.

| Campo (form) | Tipo | Requerido | Notas |
|---|---|---|---|
| `file` | binario | sí | |
| `name` | `string` | sí | nombre/clave de almacenamiento en GCS |
| `bucket` | `string` | no | usa `storage_default_bucket_name` si se omite |
| `projectId` | `string` | no | si llega, determina la colección vectorial (ver abajo) |
| `codeTypeDocument` | `string` | no | viaja como metadata del vector, no como nombre de colección |
| `uploadContentBucket` | `bool` | no | `true` = disparar vectorización tras el upload (junto con `uniqueCode`) |
| `uniqueCode` | `string` | no* | *requerido para que se dispare vectorización; sin él, `uploadContentBucket=true` no hace nada |
| `idDocument` | `string` | no | si se omite, se usa el mismo valor que `uniqueCode` (igual que en el micro Java origen) |

**Respuesta 200** — `UploadFileResponse`: `{ "success": true }` — refleja solo el resultado del upload a GCS; la vectorización (si se disparó) corre en background y no bloquea ni se refleja en esta respuesta (best-effort, sin callback — ver `integracion-java-storage.md` sección 2 sobre por qué no hace falta).

**Colección vectorial resuelta** (`StorageService._resolve_vectorization_index`, replica la convención real del micro Java origen): si llega `projectId`, la colección es `project_{projectId}` (guiones se normalizan a `_`, Milvus no acepta guiones en nombres de colección — ver P-25); si no, cae a `codeTypeDocument`; si tampoco llega, usa `rag_default_collection_name`.

### `POST /api/v1/storage/chunk`

`multipart/form-data`. Persiste cada parte en disco local bajo `storage_chunk_upload_temp_dir`. Cuando la parte recibida completa `totalChunks`, consolida automáticamente: arma el archivo final, lo sube a GCS, limpia el directorio temporal y (igual que `/upload`) puede disparar vectorización en background.

| Campo (form) | Tipo | Requerido | Notas |
|---|---|---|---|
| `file` | binario | sí | |
| `uploadId` | `string` | sí | agrupa las partes de una misma subida |
| `chunkIndex` | `int` | sí | índice de la parte (0-based) |
| `totalChunks` | `int` | sí | total esperado de partes |
| `fileName` | `string` | sí | |
| `name` | `string` | sí | |
| `bucket` | `string` | sí | |
| `projectId` | `string` | sí | también determina la colección vectorial, igual que en `/upload` |
| `idArea` | `string` | no | |
| `codeTypeDocument` | `string` | no | mismo rol que en `/upload` |
| `uploadContentBucket` | `bool` | no | mismo rol que en `/upload` — se evalúa recién en el chunk que completa la subida |
| `uniqueCode` | `string` | no | mismo rol que en `/upload` |
| `idDocument` | `string` | no | mismo rol que en `/upload` |

Campo faltante o `chunkIndex`/`totalChunks` no numérico: `422` (validación automática de FastAPI/Pydantic).

**Respuesta 200** — `ChunkUploadResponse`: `{ "consolidated": bool, "success": bool }`. `consolidated=false` en cada parte intermedia (`success` siempre `true` en ese caso — solo indica que la parte se guardó). En la parte que completa la subida, `consolidated=true` y `success` refleja si la subida del archivo consolidado a GCS tuvo éxito.

> Limitación conocida (P-11): si la última parte se reintenta después de una consolidación ya exitosa, queda un directorio temporal residual con una sola parte huérfana — no rompe nada, pero no se autolimpia.

> Nota de compatibilidad: la versión anterior de este endpoint también aceptaba estos valores como query params. Se eliminó ese soporte al fijar el contrato en P-16 porque no había evidencia de que el cliente real lo usara (los demás endpoints de storage nunca lo soportaron); si algún consumidor dependía de enviarlos por query, hay que restaurarlo explícitamente.

### `GET /api/v1/storage/get`

Descarga un archivo como stream binario (`Content-Disposition: attachment`).

**Query params:** `name` (requerido), `bucket` (requerido).

**Respuesta 200:** `StreamingResponse` con el contenido binario; `404` si el archivo no existe en el bucket.

### `GET /api/v1/storage/getFileByte`

Igual que `/get`, pero devuelve el contenido codificado en base64 dentro de un JSON en vez de un stream binario.

**Query params:** `name` (requerido), `bucket` (requerido).

**Respuesta 200** — `FileResponse`

```json
{
  "arrayBytes": null,
  "application": "application/pdf",
  "extension": null,
  "name": null,
  "base64": "JVBERi0xLjQK..."
}
```

> Nota: `arrayBytes`, `extension` y `name` están definidos en el schema pero el service actual nunca los completa (siempre `null`).

### `POST /api/v1/storage/public-upload`

`multipart/form-data`. Sube un archivo al bucket **público** configurado y retorna su URL pública.

| Campo (form) | Tipo | Requerido |
|---|---|---|
| `file` | binario | sí |
| `name` | `string` | sí (recibido pero no usado por el service actual: el nombre del blob público se genera como UUID) |
| `bucket` | `string` | no (no usado; el bucket público se resuelve por configuración) |
| `projectId` | `string` | no |
| `codeTypeDocument` | `string` | no |
| `uploadContentBucket` | `bool` | no |

**Respuesta 200** — `UploadPublicFileResponse`: `{ "success": true, "url": "https://storage.googleapis.com/<bucket>/<uuid>" }`

Requiere que `STORAGE_PUBLIC_BUCKET_NAME` esté configurado (ver `pendientes.md` P-02); si no lo está, `success: false, url: null`.

---

## Endpoints por controller (resumen)

| Método | Ruta | Controller | Tag |
|---|---|---|---|
| GET | `/` | `app/main.py` | root |
| GET | `/api/v1/health/live` | `health_controller.py` | health |
| GET | `/api/v1/health/ready` | `health_controller.py` | health |
| GET | `/api/v1/rag-services` | `rag_services_controller.py` | rag-services |
| POST | `/api/v1/rag-services` | `rag_services_controller.py` | rag-services |
| GET | `/api/v1/rag-services/{service_id}` | `rag_services_controller.py` | rag-services |
| PUT | `/api/v1/rag-services/{service_id}` | `rag_services_controller.py` | rag-services |
| PATCH | `/api/v1/rag-services/{service_id}/status` | `rag_services_controller.py` | rag-services |
| DELETE | `/api/v1/rag-services/{service_id}` | `rag_services_controller.py` | rag-services |
| POST | `/api/v1/embedding/save_document_vecstore` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/delete_index_vecstore` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/delete_document` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/list_unique_code_documents` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/list_documents` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/get_embeddings_by_unique_code` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/search_similar_documents` | `embedding_controller.py` | embedding |
| POST | `/api/v1/embedding/rag_query` | `embedding_controller.py` | embedding |
| POST | `/api/v1/storage/upload` | `storage_controller.py` | storage |
| POST | `/api/v1/storage/chunk` | `storage_controller.py` | storage |
| GET | `/api/v1/storage/get` | `storage_controller.py` | storage |
| GET | `/api/v1/storage/getFileByte` | `storage_controller.py` | storage |
| POST | `/api/v1/storage/public-upload` | `storage_controller.py` | storage |

Ver `pendientes.md` para el detalle de brechas y riesgos asociados a estos endpoints.
