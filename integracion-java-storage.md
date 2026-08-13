# Integración Storage + Vectorización — `edi-ai-proyectos-backend` (Java) ↔ `ai-rag-service-manager`

Este documento describe, con base en el código real de ambos repos (no en suposiciones), qué hay que cambiar en el microservicio Java (`edi-ai-proyectos-backend`) para que deje de subir archivos directamente a GCS y de vectorizar contra `analysis-ai-service`, y en su lugar use `ai-rag-service-manager` para ambas cosas.

Análisis hecho el 2026-08-11, leyendo directamente:
- Java: `StorageManager.java`, `StorageServiceImpl.java`, `StorageController.java`, `ChunkUploadServiceImpl.java`, `VectorStoreServiceImpl.java`, `VectorStoreMapper.java`, `SaveFileVecstoreRequest.java`, `DocumentCommonServiceImpl.java`, `DataByDocTypeManager.java`, `OpenAiConfigProperties.java`, `application.yml`/`application-dev.yml`.
- Python: `app/api/routes/storage_controller.py`, `app/services/storage_service.py`, `app/schemas/embedding.py`, `app/services/embedding/document_embedding_service.py`.

Trazabilidad: ver `pendientes.md` en `ai-rag-service-manager` — `P-24` (esta iniciativa, del lado Java — **resuelta parcialmente**, ver sección 7), `P-20`/`P-21` (incompatibilidades de contrato — **resueltas**, sección 3), `P-22`/`P-23` (funcionalidad que faltaba en `ai-rag-service-manager` — **resueltas**, sección 4), `P-10`/`P-11` (vectorización/consolidación — **resueltas e implementadas**, sección 5), `P-25` (sanitización de nombres de colección para Milvus — **resuelta**, ver nota en sección 1.2), `P-26` (visibilidad de borrados en Milvus — **resuelta**, ver sección 4.1). Del lado `ai-rag-service-manager` no queda nada bloqueante; lo que falta es activar el corte de storage en Java y probar en un ambiente real (sección 7).

---

## 1. Estado actual (AS-IS)

Hoy, storage y vectorización viven **enteramente dentro de Java**, sin tocar `ai-rag-service-manager`:

- **Storage**: `StorageServiceImpl` habla directo con el SDK de Google Cloud Storage (`com.google.cloud.storage.Storage`). No hay ningún cliente HTTP hacia un servicio externo para esto.
- **Vectorización**: `VectorStoreServiceImpl` sí llama a un servicio externo por HTTP, pero es **`analysis-ai-service`** (`http://analysis-ai-service:7002` en `dev`, config `app.openai.*`), **no** `ai-rag-service-manager`. El contrato de esa llamada (`POST /documents/save_document_vecstore`) es distinto al de `ai-rag-service-manager` (`POST /api/v1/embedding/save_document_vecstore`) — ver sección 3.

### 1.1 Los tres puntos de entrada que hoy disparan vectorización

1. **`POST /storage/upload`** → `StorageController.uploadFile` → `StorageManager.uploadFile(UploadFileRequest)`:
   - Sube el archivo a GCS (`StorageServiceImpl.uploadFile`).
   - Si `response.success()` y `codeTypeDocument` está presente **y** ese código está en la lista de tipos vectorizables (parámetro `is_vectorizable`, resuelto vía `ParameterCommonService` + `Util.cleanStringJsonParameters`), dispara `CompletableFuture.runAsync(...)` sobre un executor dedicado (`asyncTaskExecutor`) que:
     - construye el request de vectorización (`VectorStoreMapper.buildSaveFileVecstoreRequest`),
     - llama a `VectorStoreService.saveEmbeddingFile(request)` (HTTP síncrono, dentro de esa tarea async),
     - y con el resultado (`successful`), actualiza el propio documento en la BD de Java (`DocumentCommonService.updateDocumentIsVectorized`), **reintentando cada 5s en un loop bloqueante hasta que la fila exista** (ver 1.3).
   - **`uploadContentBucket`** (campo de `UploadFileRequest`) se recibe pero **no se lee en ningún lado** de esta lógica — confirmado por búsqueda directa en el código. Es un campo muerto, igual que en `ai-rag-service-manager` hoy.

2. **`POST /storage/chunk`** (repetido) + **`POST /dataDocType/saveDocuments`** con `shouldConsolidateChunks=true`:
   - Los chunks se guardan en disco local (`ChunkUploadServiceImpl`, `app.storage.chunkUploadTempDir`, `/tmp/uploads` en dev).
   - `DataByDocTypeManager.saveDocuments` (cuando `shouldConsolidateChunks=true`) dispara `ChunkUploadServiceImpl.consolidatePendingUploads` → `uploadMergedFile` → **el mismo** `StorageManager.uploadFile(byte[]...)` de arriba → mismo flujo de vectorización condicional.

3. **`POST /vectorStore/saveDocument`** (`VectorStoreController` → `VectorStoreManager.saveDocumentOnVectorStore`):
   - Endpoint separado para "re-vectorizar" un documento ya subido: recupera los bytes desde storage y llama a `VectorStoreService.saveEmbeddingFile` igual que arriba, async.

`DataByDocTypeManager.saveDocumentsResources` y el flujo de `saveDocuments` sin `shouldConsolidateChunks` son puramente metadata (no tocan storage ni vectorización).

### 1.2 Mapeo exacto de campos hoy (Java → request de vectorización)

`VectorStoreMapper.buildSaveFileVecstoreRequest(base64, fileName, index, codeTypDocument, uniqueCode, bucket)`:

| Campo del método | Valor real que le pasa `StorageManager` | Campo en `SaveFileVecstoreRequest` |
|---|---|---|
| `base64` | bytes del archivo | `base64` (`byte[]`, Jackson lo serializa como string base64) |
| `fileName` | nombre del archivo | `fileName` |
| `index` | `"project-" + projectId` | `indexVecstore` |
| `codeTypDocument` | `codeTypeDocument` del request | `codeDocumentType` |
| `uniqueCode` | **`uploadFileRequest.name()`** (el nombre/clave de storage, no un código separado) | `uniqueCode` **y también** `idDocument` (mismo valor, ver 3.1) |
| `bucket` | bucket resuelto | `bucket` |

Además, `StorageManager` agrega `listParameters` con dos entradas (`ParametersDTO{code, value}`): `VECTOR_CHUNK_SIZE=1000` y `VECTOR_CHUNK_OVERLAP=200` (valores reales, semilla en `parameters_vectors.csv`).

**Dato clave:** la colección/índice vectorial es **`project-{idProject}`** — una colección por proyecto, no por tipo de documento. `codeDocumentType` viaja como metadata, no como nombre de colección.

**Corrección importante (P-25, encontrada probando esto contra Milvus real):** Milvus **no acepta guiones** en nombres de colección (solo letras, números y `_`). El nombre que Java arma (`"project-42"`) es inválido tal cual. `ai-rag-service-manager` ahora sanitiza automáticamente cualquier nombre de colección (`RAGService._sanitize_collection_name`), así que `"project-42"` termina como `project_42` en Milvus — Java **no necesita cambiar nada**, el nombre real en Milvus simplemente difiere en el guion. Si algún proceso necesita consultar Milvus directamente (fuera de `ai-rag-service-manager`), usar la forma con guion bajo.

### 1.3 Sobre el loop de reintento de `updateDocumentIsVectorized`

`documentCommonService.updateDocumentIsVectorized(successful, uniqueCode)` busca el `Document` por `uniqueCode` y actualiza `is_vectorized`. Devuelve `false` únicamente si **no encontró la fila** (no si la vectorización falló) — por eso `StorageManager` reintenta cada 5s hasta encontrarla. Esto es una particularidad de sincronización de la transacción de Java (la fila del documento puede no estar committeada aún cuando termina la llamada async); **no aplica a `ai-rag-service-manager`**, que no tiene ni necesita ese concepto.

---

## 2. Estado deseado (TO-BE)

```
Frontend
   │
   ▼
edi-ai-proyectos-backend (Java)
   │
   ├── POST /api/v1/storage/upload         ──┐
   ├── POST /api/v1/storage/chunk           │  ai-rag-service-manager
   ├── GET  /api/v1/storage/get             ├─ (reemplaza GCS local
   ├── GET  /api/v1/storage/getFileByte     │   y analysis-ai-service
   ├── POST /api/v1/storage/public-upload  ─┘   para esto)
   │
   └── POST /api/v1/embedding/save_document_vecstore  ──┐
       POST /api/v1/embedding/delete_index_vecstore     │  ai-rag-service-manager
       POST /api/v1/embedding/list_documents            ├─ (reemplaza
       POST /api/v1/embedding/get_embeddings_by_unique_code │  analysis-ai-service
       POST /api/v1/embedding/search_similar_documents  ─┘   para esto)
```

**Importante:** ninguna de las llamadas de vectorización necesita callback ni webhook de vuelta hacia Java. Java ya llama a la vectorización de forma síncrona *dentro de* su propia tarea async (`CompletableFuture.runAsync`) y usa la respuesta HTTP directa (`{successful: bool}`) para actualizar su propia base de datos. `ai-rag-service-manager` solo necesita seguir respondiendo síncronamente con éxito/fallo — que ya es el contrato actual de `/embedding/save_document_vecstore`. **No hace falta agregar ningún mecanismo de callback en `ai-rag-service-manager`** (esto corrige un supuesto de un análisis anterior que no tenía visibilidad del código Java real).

---

## 3. Incompatibilidades de contrato detectadas (bloqueantes)

**Resueltas del lado `ai-rag-service-manager` el 2026-08-11** (ver `pendientes.md` P-20 y P-21). Documentado aquí igual, como referencia de qué esperar ahora al integrar Java.

### 3.1 `idDocument`: `String` en Java vs `int` en Python — RESUELTO

- Java (`SaveFileVecstoreRequest.idDocument`): `String`, y en la práctica **es literalmente el mismo valor que `uniqueCode`** (`VectorStoreMapper` hace `request.setIdDocument(uniqueCode)` — no hay un ID numérico real detrás).
- Python (`app/schemas/embedding.py`, `SaveDocumentVecstoreRequest.id_document`): **ahora `str`** (antes `int`, rechazaba con `422` cualquier `idDocument` no numérico).

`ai-rag-service-manager` ya acepta `idDocument` como string — Java puede mandar el mismo valor que `uniqueCode` tal cual, sin transformación. Verificado con el payload real que arma `VectorStoreMapper` (`idDocument` = `uniqueCode`, ej. `"DOC-2026-0001"`).

### 3.2 `listParameters`: Java manda `{code, value}`, Python esperaba `{key, value}` — RESUELTO

- Java (`ParametersDTO`): campos `code` y `value` (confirmado leyendo la clase directamente).
- Python (`DocumentEmbeddingService._normalize_parameters`) **ahora acepta ambas formas**: `{"key": ..., "value": ...}` (original) y `{"code": ..., "value": ...}` (la que manda Java). Verificado con el payload real de `StorageManager` (`VECTOR_CHUNK_SIZE`/`VECTOR_CHUNK_OVERLAP` vía `ParametersDTO`): ambos parámetros ya llegan a metadata con su nombre real, sin pisarse entre sí.

No hace falta ningún cambio del lado Java para este punto — `listParameters` con `{code, value}` funciona tal cual hoy.

---

## 4. Funcionalidad que Java usa hoy y `ai-rag-service-manager` ya tiene (resuelto 2026-08-11)

Ver `pendientes.md` P-22 y P-23 — **resueltos**. `ai-rag-service-manager` ahora expone equivalentes directos, compatibles con lo que Java ya arma hoy (ver `api.md`).

### 4.1 Borrado de un documento individual (`deleteEmbeddingDocument`)

Java llamaba a `app.openai.deleteEmbeddingUrl` (`POST /documents/delete`) con `{indexVecstore, idDocument}` para borrar **un solo documento** del índice vectorial. Ahora `ai-rag-service-manager` expone `POST /api/v1/embedding/delete_document` con el **mismo shape de request** (`{indexVecstore, idDocument}`) — Java no necesita cambiar cómo construye el `DeleteEmbeddingRequest`, solo la URL de destino. Verificado end-to-end contra Milvus real (ver `pendientes.md` P-22 y P-26 — este trabajo destapó un bug de visibilidad de borrados en Milvus, ya corregido).

### 4.2 Listado liviano por namespace (`getListUniqueCodeDocuments`)

Java llamaba a `app.openai.listUniqueCodeDocuments` con el namespace/colección como string JSON crudo, y espera `List<Metadata{namespace, codigo, fileName, id, nombreDocumento}>`. Ahora `ai-rag-service-manager` expone `POST /api/v1/embedding/list_unique_code_documents` que replica **exactamente** esa forma (body string JSON plano, respuesta array JSON plano con esos 5 campos en camelCase) — Java tampoco necesita cambiar cómo arma el request ni cómo deserializa la respuesta, solo la URL. `codigo`/`fileName` se completan con `unique_code`/`file_name`; `nombreDocumento` repite `fileName` (no existe un concepto separado en la metadata actual). Verificado end-to-end contra Milvus real.

---

## 5. Cambios requeridos en Java

### 5.1 Storage — quitar GCS local de `StorageServiceImpl`

Reemplazar las llamadas directas al SDK de GCS por llamadas HTTP a `ai-rag-service-manager`:

| Método Java actual | Reemplazar por |
|---|---|
| `StorageServiceImpl.uploadFile` (bytes → `storage.create(blobInfo, bytes)`) | `POST {ragServiceUrl}/api/v1/storage/upload` (multipart: `file`, `name`, `bucket`, `projectId`, `codeTypeDocument`, `uploadContentBucket`) |
| `StorageServiceImpl.getFileBytes` (`storage.get(bucket, name)`) | `GET {ragServiceUrl}/api/v1/storage/getFileByte?name=&bucket=` |
| `StorageServiceImpl.getFile` (temp file + `InputStreamResource`) | `GET {ragServiceUrl}/api/v1/storage/get?name=&bucket=` (ya devuelve el stream directamente; el truco de archivo temporal de Java deja de ser necesario) |
| `StorageServiceImpl.uploadPublicFile` | `POST {ragServiceUrl}/api/v1/storage/public-upload` |
| `ChunkUploadServiceImpl.storeChunk` + `consolidatePendingUploads` (disco local en Java) | `POST {ragServiceUrl}/api/v1/storage/chunk` — P-11 ya implementado: el endpoint consolida automáticamente al recibir la última parte y devuelve `{consolidated, success}` (antes devolvía `200` vacío; ver `api.md`). |

El `Storage` bean de GCS (`StorageConfig.java`) y las credenciales asociadas quedan sin uso una vez migrado esto — candidato a limpieza posterior, no parte de este cambio.

### 5.2 Vectorización — repuntar de `analysis-ai-service` a `ai-rag-service-manager`

`VectorStoreServiceImpl.saveEmbeddingFile` y el resto de métodos de `VectorStoreService` deben apuntar a `ai-rag-service-manager` en vez de `app.openai.saveDocumentVecstore`/`deleteIndexVecstore`/etc. Como es conceptualmente un servicio distinto (contrato `/api/v1/embedding/*`, no `/documents/*`), se recomienda una sección de configuración separada en vez de reusar `app.openai.*`:

```yaml
app:
  rag-service:
    base-url: http://ai-rag-service-manager:8000/api/v1
    save-document-vecstore: ${app.rag-service.base-url}/embedding/save_document_vecstore
    delete-index-vecstore: ${app.rag-service.base-url}/embedding/delete_index_vecstore
    delete-document: ${app.rag-service.base-url}/embedding/delete_document
    list-unique-code-documents: ${app.rag-service.base-url}/embedding/list_unique_code_documents
    list-documents: ${app.rag-service.base-url}/embedding/list_documents
    get-embeddings-by-unique-code: ${app.rag-service.base-url}/embedding/get_embeddings_by_unique_code
    search-similar-documents: ${app.rag-service.base-url}/embedding/search_similar_documents
    storage-upload: ${app.rag-service.base-url.replace('/api/v1','')}/api/v1/storage/upload
    # (o una segunda base-url si se prefiere no derivar por string)
```

El campo `saveEmbeddingDocsUrl` (`app.openai.saveEmbeddingDocsUrl`, apunta a `/documents/save_embeddings`) existe en `OpenAiConfigProperties` pero **no se usa en ningún lado de `VectorStoreServiceImpl`** — parece config legacy de un contrato anterior. Vale la pena limpiarlo al tocar esta zona, aunque no es parte estricta de esta migración.

### 5.3 Autenticación

`ai-rag-service-manager` no implementa autenticación (exclusión intencional documentada, ver `pendientes.md` P-13). Java puede dejar de mandar el header `Authorization: Bearer` en estas llamadas específicas — no rompe nada si lo sigue mandando (se ignora), pero no cumple ninguna función tampoco.

### 5.4 Incompatibilidades de la sección 3 — ya resueltas del lado Python

`id_document` (str) y `listParameters` (`code`/`key`) ya están resueltas en `ai-rag-service-manager` (sección 3). No quedan bloqueantes de contrato conocidos entre lo que Java manda hoy y lo que Python espera para `save_document_vecstore`.

---

## 6. Qué NO cambia

- El resto de `app.openai.*` (askUrl, financial_analysis, evaluation, etc.) — no tiene relación con storage/vectorización, sigue apuntando a `analysis-ai-service`.
- `app.research.url` (`ResearchServiceImpl`) — servicio distinto, sin relación.
- La lógica de negocio de "qué tipos de documento son vectorizables" (`is_vectorizable`, parámetro de Java) — es una regla de negocio de Java sobre cuándo llamar a vectorización, no algo que deba moverse a `ai-rag-service-manager`.
- `DataByDocTypeManager.saveDocuments`/`saveDocumentsResources` en la parte que solo escribe metadata (`Document`, `KnowledgeBase`) — sigue siendo 100% Java/BD propia.

---

## 7. Checklist de migración

- [x] `ai-rag-service-manager`: resolver P-20 (`id_document` → `str`). Resuelto 2026-08-11.
- [x] `ai-rag-service-manager`: resolver P-21 (aceptar `code`/`value` en `list_parameters`, no solo `key`/`value`). Resuelto 2026-08-11.
- [x] `ai-rag-service-manager`: implementar P-10 (vectorización disparada desde `/storage/upload` y `/storage/chunk`) y P-11 (consolidación de chunks). Resuelto e implementado 2026-08-11, verificado end-to-end contra Milvus real.
- [x] `ai-rag-service-manager`: resolver P-25 (nombres de colección con guiones, inválidos para Milvus). Resuelto 2026-08-11.
- [x] Java: agregar config `app.rag-service.*` con las URLs de `ai-rag-service-manager`. Hecho 2026-08-11 en `application.yml`/`application-dev.yml` — **el hostname/puerto de `application-dev.yml` es un valor por defecto sin confirmar** (sigue la convención de `analysis-ai-service`: nombre de servicio = nombre de repo, puerto 8000 = default de `app_port`); confirmar el nombre real del servicio en la red de dev antes de usarlo.
- [x] `ai-rag-service-manager`: resolver P-22 (endpoint `delete_document`, borrado de un solo documento) y P-23 (endpoint `list_unique_code_documents`, listado liviano por namespace). Resuelto e implementado 2026-08-11, verificado end-to-end contra Milvus real — este trabajo destapó y corrigió P-26 (borrado en Milvus no visible de inmediato sin `flush`).
- [x] Java: repuntar `VectorStoreServiceImpl` de `app.openai.*` a `app.rag-service.*` para los cuatro métodos de vectorización: `saveEmbeddingFile`/`deleteIndexVecstore` (2026-08-11) y `deleteEmbeddingDocument`/`getListUniqueCodeDocuments` (2026-08-11, una vez creados los endpoints P-22/P-23). **Activo por defecto** — este cambio sí modifica el comportamiento actual de Java (antes llamaba a `analysis-ai-service`, ahora llama a `ai-rag-service-manager` para los cuatro). El campo `openaiConfig` quedó sin uso en la clase y se eliminó (junto a su import) en vez de dejarlo muerto. Verificado que compila (`./gradlew compileJava`/`compileTestJava`/`assemble`), no verificado en runtime (no se pudo levantar este microservicio Java desde este entorno).
- [x] Java: implementar cliente HTTP a `/api/v1/storage/*` (`RagServiceStorageClient`, nueva clase, implementa la misma interfaz `StorageService`). **Activado 2026-08-12** — ver corte de storage abajo.
- [ ] Confirmar el hostname/puerto real de `ai-rag-service-manager` en cada ambiente (dev/qa/prod) y actualizar `app.rag-service.baseUrl`/URLs específicas en consecuencia.
- [x] **Corte de storage ejecutado (2026-08-12).** `RagServiceStorageClient` pasó a ser la única implementación de `StorageService` (ya sin `@Primary`/`@Qualifier`, sin ambigüedad de beans). Se **eliminaron** `StorageServiceImpl.java`, `StorageConfig.java`, `GoogleCloudConfig.java`, los campos `projectId`/`publicBucketName` de `StorageConfigProperties`, el bloque `app.google.jsonCredentials` de `application.yml`/`application-dev.yml`, y las dependencias GCS de `build.gradle` (con dos deps transitivas re-agregadas explícitamente para no romper compilación — ver `pendientes.md` P-24). Mismo mandato que en `edi-ai-operator` (`pendientes.md` P-28): `ai-rag-service-manager` es ahora el único con storage propio en todo el ecosistema, en ambos repos.
- [ ] Probar de punta a punta en un ambiente real: upload simple, upload por chunks, borrado de índice, búsqueda semántica, y el camino de error (documento no vectorizable, servicio caído). **Sigue siendo la única brecha real:** `./gradlew compileJava`/`compileTestJava`/`assemble` pasan (`BUILD SUCCESSFUL`), pero no se pudo levantar este microservicio Java desde este entorno para ejercitar `/storage/*` con una llamada HTTP real.
- [x] Retirar el bean de GCS (`StorageConfig.java`) y las credenciales asociadas en Java — hecho como parte del corte de storage, no se esperó a confirmación en producción porque ya no había ningún consumidor de GCS directo (`StorageServiceImpl` era el único, y se eliminó junto con el bean).

**Actualización 2026-08-12 — corte ejecutado:** el mismo patrón validado de punta a punta en `edi-ai-operator` (ver `pendientes.md` P-28, `pruebas-manuales-rag-document-search.md`) se replicó en Java a nivel de código: sin GCS directo, `RagServiceStorageClient` como único camino. La única diferencia respecto a `edi-ai-operator` es que aquí no hubo forma de probar en runtime real (no se pudo levantar el servicio Java desde este entorno) — la verificación se quedó en el nivel de compilación/build, no en una llamada HTTP real end-to-end.

**Hallazgos adicionales, no relacionados con esta tarea (reportados, no corregidos):**
- El repositorio Java tiene un **merge sin resolver** en `src/main/resources/edward-creds.json` (`git status` lo marca "modificado por ambos") y cambios pendientes de commit en `liquibase.properties`/`changelog-1.0.xml` — no se tocó nada de esto, es trabajo en curso de otra sesión.
- `application.yml`/`application-dev.yml` tienen secretos reales en texto plano (client secrets de Keycloak, password de email, token de bot de Webex) versionados en git — no es parte de esta tarea, pero vale la pena que el equipo lo sepa si no lo tenían presente.
