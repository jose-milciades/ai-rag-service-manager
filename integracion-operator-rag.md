# Integración `edi-ai-operator` ↔ `ai-rag-service-manager`

Documento de análisis y plan de integración, mismo formato que [`integracion-java-storage.md`](./integracion-java-storage.md). Cubre dos cosas independientes que se decidieron juntas en la misma conversación:

1. Agregar una tool nueva al agente de `edi-ai-operator` (`DeepinsightEngineAgent`) para que pueda hacer búsqueda semántica contra `ai-rag-service-manager`, en vez de solo lectura de documentos completos (que es lo único que existe hoy).
2. Migrar el storage propio de `edi-ai-operator` (cliente GCS directo) para que pase por `ai-rag-service-manager`, igual que ya se hizo con `edi-ai-proyectos-backend` — **`ai-rag-service-manager` es el único microservicio con acceso directo a storage en todo el ecosistema**, sin excepciones.

**Estado (actualizado 2026-08-12), ver `pendientes.md` P-28: frente 1 (tool de búsqueda) verificado end-to-end con éxito, incluyendo respuesta real del LLM** (proyecto real `93`, documento PDF real, `POST /rag-document-search/simulate` → `200` — ver `pruebas-manuales-rag-document-search.md`). Del frente 2 (storage), solo `company_document_query.py` está migrado — **el resto de consumidores de `StorageService` (GCS directo) sigue sin migrar, es el próximo paso explícito** (ver checklist sección 4). Sigue pendiente, a cargo del usuario: la fila de `cat_tools`/`tools_implemented` para integrar la tool al agente completo (la fila de `CatPrompt` ya se creó y funciona).

Guía de `curl` paso a paso para probar todo esto manualmente (subir+vectorizar un documento, confirmar el retrieval, probar `/rag-document-search/simulate`): ver [`pruebas-manuales-rag-document-search.md`](./pruebas-manuales-rag-document-search.md).

---

## 0. Contexto: esto ya se intentó una vez

`edi-ai-operator` tiene una rama divergente `embedding` (remoto `origin/embedding`, autor Troyano, commit `1dfcf78` "Refactor code structure for improved readability and maintainability", **no es ancestro de `dev`**) con:

- `src/service/rag/rag_service.py`, `vector_store_manager.py`, `rag_agent.py`
- `src/service/embedding/document_embedding_service.py`
- `src/api/embedding/doccument_embedding_controller.py` (+ `request.py`/`response.py`)
- `docs/RAG_SETUP.md` — documenta las mismas variables (`RAG_COLLECTION_NAME_PREFIX`, `RAG_DEFAULT_COLLECTION_NAME`, `RAG_AGENT_COLLECTION_NAME`, `RAG_EMBEDDING_MODEL`, `RAG_CHUNK_SIZE`, etc.) que hoy tiene `ai-rag-service-manager`, con Qdrant o Milvus como backend intercambiable.

Es, literalmente, el prototipo que evolucionó hasta convertirse en el microservicio separado que es hoy `ai-rag-service-manager`. Nunca se llegó a registrar como tool en `TOOLS_REGISTRY` (ver sección 2) — se abandonó ahí, antes de conectarlo al agente, para extraerlo a su propio servicio. Este documento retoma esa idea, pero con RAG ya extraído y consumido por HTTP en vez de embebido.

En `dev` (la rama real) no queda rastro de ese código en disco (solo `.pyc` sueltos en `__pycache__`, sin fuente) y **`edi-ai-operator` no llama a `ai-rag-service-manager` en ningún lado hoy** (verificado por grep en todo `src/`).

---

## 1. Estado actual (AS-IS)

### 1.1 El agente y sus tools

`src/agents/deep_insight_engine/deep_insight_engine_agent_core.py` (1200 líneas): moderator → planning engine → `agent_loop` → pipeline de tareas (con auto-crítica y replanning) → `_process_task` (línea 847) → `TOOLS_REGISTRY.get(name_tool)` (línea 902).

Contrato fijo de cualquier tool, `src/agents/deep_insight_engine/tools/tools_registry.py` (12 tools registradas hoy):

```python
def mi_tool(prompts, contextual_memory: ContextualMemory, parameters: dict,
            ms_id_parent: str, depth: int, **kwargs) -> ContextualMessage
```

`_process_task` arma `parameters` (dict grande, merge de `user_session` + campos de la tarea + config del worker) antes de invocar la tool. Los tres datos que hacen falta para una tool de búsqueda semántica **ya están disponibles ahí, no hay que construirlos**:

| Dato | De dónde sale hoy |
|---|---|
| Pregunta | `parameters["query"]` (línea 880, `current_parameters["query"] = query_text`) |
| Historial | `contextual_memory.messages: List[ContextualMessage]` — se acumula automático en cada paso del pipeline, todas las tools ya lo reciben como segundo argumento |
| Documentos/proyecto asociados a la tool | `parameters["code_resources"]` (línea 884, `worker_info.get("code_resource")`) |

### 1.2 La tool más parecida hoy: `company_document_query`

`src/agents/deep_insight_engine/tools/company_document_query.py`. **No hace búsqueda semántica** — descarga el/los documento(s) completo(s) asociados a `code_resource` desde storage, extrae texto (o adjunta imagen/video nativo a Gemini si aplica) y se lo pasa entero al LLM. Es fuerza bruta por documento completo, no retrieval por similitud. Sirve de plantilla de contrato/estilo para la tool nueva, no de lógica a reusar.

Flujo interno relevante:
```python
storage_service = StorageService()                     # cliente GCS propio, ver 1.3
file_content = storage_service.download_file(unique_code)
...
message = contruct_contextual_message(prompts, PromptTemplate.COMPANY_DOCUMENT_QUERY, ...)
return invoke_model(message, None, None, prompts, contextual_memory)  # LLM real aquí
```

Cada tool sintetiza su propia respuesta con `invoke_model` antes de retornar — la síntesis final NO ocurre en un paso central separado. La tool nueva debe seguir el mismo patrón: traer contexto (de `ai-rag-service-manager` en vez de storage), y sintetizar la respuesta con el LLM localmente, igual que esta.

### 1.3 Storage propio de `edi-ai-operator` (a migrar)

`src/service/util/storage_service.py` — cliente GCS directo (`google.cloud.storage`), independiente de `ai-rag-service-manager` y de `edi-ai-proyectos-backend`:

```python
class StorageService:
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(os.getenv("STORAGE_DEFAULT_BUCKET_NAME"))
    def upload_file(self, upload_file_request: UploadFileRequest) -> UploadFileResponse: ...
    def download_file(self, filename: str) -> bytes: ...
```

Consumido directamente por al menos estos módulos (grep `StorageService|storage_service` en `src/`):

- `src/agents/deep_insight_engine/tools/company_document_query.py` — descarga documentos de la empresa para leerlos completos.
- `src/service/deep_insight_engine/thought_persistence_service.py` — **sube** (`upload_file`) el blob de "thoughts"/contexto de una ejecución.
- `src/service/deep_insight_engine/chat_history_service.py`, `context_memory_service.py` — **descargan** (`download_file`) esos mismos blobs para reconstruir el historial/`ContextMemory` de una conversación.
- `src/service/comun/comun_service.py` — upload genérico.
- `src/service/report/report_service.py`, `src/chains/ia_functions.py`, `src/chains/ia_functions_cache.py`, `src/service/duck_db/common_duck_db.py` — otros consumidores, no revisados en detalle en este análisis (quedan en el checklist de migración).

Es decir: **tanto lectura de documentos de la empresa como escritura/lectura del propio contexto de conversación** pasan hoy por este cliente GCS propio. Los dos casos migran igual: HTTP a `ai-rag-service-manager` en vez de SDK de GCS directo.

---

## 2. Principio arquitectónico objetivo (TO-BE)

Mismo principio ya validado y en curso con Java, extendido a todo el ecosistema:

- **`ai-rag-service-manager`**: único dueño de storage (GCS) y del vector store (Milvus) en todo el sistema. No sabe qué es una conversación, un agente, ni un historial — solo recibe `query`/archivo + `indexVecstore` y responde.
- **`edi-ai-proyectos-backend` (Java)**: punto de entrada de la API para el frontend. Recibe las peticiones de carga/descarga de storage y las de vectorización, y las enruta a `ai-rag-service-manager` (ya documentado en `integracion-java-storage.md`).
- **`edi-ai-operator`**: dueño de toda la orquestación conversacional (moderator/planner/agent_loop/self-critique, selección de tools, `ContextMemory`, historial de chat, ejecución async vía RQ). No tiene acceso directo a GCS. Consume `ai-rag-service-manager` para dos cosas:
  1. **Embeddings/retrieval**: la tool nueva (sección 3) para búsqueda semántica.
  2. **Storage**: reemplaza su `StorageService` propio — tanto la descarga de documentos de la empresa (`company_document_query`) como la subida/descarga de sus propios blobs de `ContextMemory`/thoughts (`thought_persistence_service`/`chat_history_service`) pasan a llamar a `ai-rag-service-manager` (`/storage/upload`, `/storage/get`, `/storage/getFileByte`). Lo único que sigue siendo responsabilidad exclusiva de `edi-ai-operator` es la metadata relacional (`agent_execution`, `chat_ai.chat` en su propio Postgres, ver el sequence diagram de la conversación) — eso no es storage de archivos, no se toca.

```text
Frontend
   │
   ▼
edi-ai-proyectos-backend (Java) ── entrada de la API para el frontend
   │
   └──────────────► ai-rag-service-manager ──────────► GCS + Milvus
                      /api/v1/storage/*                 (único dueño)
                      /api/v1/embedding/*

edi-ai-operator (agente conversacional, WhatsApp/Channel Gateway → RQ worker → DeepinsightEngineAgent)
   │
   ├── nueva tool "rag_document_search" ──► ai-rag-service-manager /embedding/search_similar_documents
   │                                         (embeddings/retrieval)
   │
   └── StorageService propio (a eliminar) ──► ai-rag-service-manager /storage/*
         - company_document_query: descarga de documentos de la empresa
         - thought_persistence_service / chat_history_service: sube y baja
           el blob de ContextMemory/thoughts de cada ejecución

   (Postgres propio de operator: agent_execution, chat_ai.chat — sin cambios,
    no es storage de archivos)
```

---

## 3. Tool nueva: búsqueda semántica (RAG real)

### 3.1 Contrato de la tool — implementado

Mismo shape que las 12 tools existentes (sección 1.1). Implementado en `src/agents/deep_insight_engine/tools/rag_document_search.py`, con el cliente HTTP en `src/service/rag/rag_service_client.py`:

```python
def rag_document_search(prompts, contextual_memory: ContextualMemory, parameters: dict,
                         ms_id_parent: str, depth: int):
    query = parameters["query"]
    index_vecstore = _resolve_index_vecstore(parameters)          # ver 3.2
    results = search_similar_documents(index_vecstore, query, top_k=5)  # rag_service_client.py
    function_parameters = {"rag_search_results": _format_results(results)}
    message = contruct_contextual_message(
        prompts, PromptTemplate.RAG_DOCUMENT_SEARCH, function_parameters, parameters, ms_id_parent
    )
    return invoke_model(message, None, None, prompts, contextual_memory)  # mismo patron que company_document_query
```

Registrada en `TOOLS_REGISTRY` (`tools_registry.py`).

**Verificación real (dos rondas):**

1. Se levantó `ai-rag-service-manager` real (Milvus real), se indexó un documento de prueba en la colección `project_999`, y se llamó la función real `rag_service_client.search_similar_documents` y las funciones internas de la tool (`_resolve_index_vecstore`, `_format_results`) contra ese servicio — funcionó de punta a punta. Esto destapó un bug real en `ai-rag-service-manager` (`search_similar_documents` devolvía `text_preview` en `snake_case` en vez de `textPreview`, inconsistente con el resto de la API — corregido, ver `pendientes.md` P-29).
2. Con la API de simulación de la sección 3.5 ya construida, se llamó `RagDocumentSearchSimulationService.simulate(70, None)` **contra la base de datos Postgres real de `edi-ai-operator`** (proyecto real, id 70, "Event Express") y contra `ai-rag-service-manager` real: encontró el proyecto, resolvió `indexVecstore=project_70`, llamó `search_similar_documents` real, y llegó hasta adentro de `rag_document_search()` (incluyendo el log esperado de `update_cache_status_progress` sin `cache_task_id`) — se detuvo exactamente en el punto documentado en 3.4 (`KeyError` por la fila de `CatPrompt` faltante), y en el camino destapó el bug de `id_company`/`company_id` documentado arriba. Es la confirmación más fuerte posible sin las dos filas de base de datos pendientes.

### 3.2 Resolución de `indexVecstore` — resuelto por evidencia de código, pendiente de confirmar con el equipo

`ai-rag-service-manager` sanea nombres de colección con la convención `project_{idProject}` (P-25), usada hoy por Java al disparar vectorización desde `/storage/upload`. La tool implementada resuelve `indexVecstore = f"project_{parameters['company_id']}"`.

**Evidencia encontrada de que esto es correcto** (no es una suposición a ciegas):
- `parameters["company_id"]` se construye en `build_parameters` (`deep_insight_utils.py:730`) como `planning_input.project.id`, y ese `project` viene de `request.id_project` — el mismo campo `projectId` (requerido) del request que crea la ejecución (`src/api/deep_insight_engine/request.py`).
- El schema de `edi-ai-operator` (`database/entities/document.py`) tiene una entidad `Document` con `unique_code`, `id_project`, `is_vectorized` — mismos campos, mismos nombres, que la entidad `Document` de `edi-ai-proyectos-backend` (Java) usada en todo este documento y en `integracion-java-storage.md`.

**Sigue sin confirmarse**: que ambos sistemas usen literalmente el mismo valor numérico para el mismo proyecto real (los `.env` revisados de `edi-ai-operator` y Java apuntan a hosts de Postgres distintos, así que no se pudo verificar consultando ambas bases). La implementación asume que sí; si el equipo confirma que no, `_resolve_index_vecstore` en `rag_document_search.py` es el único lugar a ajustar.

### 3.3 Quién indexa — sin cambios, ver decisión original

Se confirmó (grep completo de `dev`) que `edi-ai-operator` no tiene ningún pipeline de indexación activo. La tool implementada solo busca — asume que Java ya indexó vía P-10. No se implementó indexación nueva en `edi-ai-operator`.

### 3.4 Bloqueantes de contenido/base de datos — no completados, no son trabajo de código

Dos piezas que la tool necesita para funcionar en runtime, y que **no se pueden resolver desde este repo ni desde código**:

1. **Prompt template**: `invoke_model` resuelve el LLM y el texto del prompt desde una tabla `CatPrompt` en la base de datos, por `(nombre, id_project)` (`prompt_config_service.get_prompt_by_type`, consumido vía `build_placeholders`). Se agregó el enum `PromptTemplate.RAG_DOCUMENT_SEARCH = "rag_document_search"` en código, pero **no existe la fila correspondiente en `CatPrompt`** — sin ella, la tool falla al construir el mensaje. Escribir ese prompt es trabajo de contenido/prompt-engineering, no de este análisis.
2. **Catálogo de tools/workers**: qué tool puede ejecutar cada "worker" (`name_tool_implemented`) también es configuración en base de datos (`cat_tools`/`tools_implemented`, resuelta vía `team_members_by_area`). Sin una fila nueva ahí, el selector de tools del agente nunca va a poder elegir `rag_document_search` — el código existe pero es inalcanzable en runtime hasta que se configure.

**Hallazgo importante para cuando se cree la fila de `CatPrompt` (punto 1):** `build_placeholders` (`src/agents/deep_insight_engine/prompt_utils.py:38`) busca el prompt como `prompts[id_prompt, parameters.get("id_company", None)]` — pero la clave real que se puebla en `parameters` en todo el sistema es `company_id` (`deep_insight_utils.py:730`, `prompt_utils.py:114,138`), nunca `id_company`. `parameters.get("id_company", None)` **siempre devuelve `None`**, para las 13 tools del registry, no solo para esta. Confirmado en la verificación real de la sección 3.1: el lookup falló con `KeyError: (PromptTemplate.RAG_DOCUMENT_SEARCH, None)`, con `id_project=None` pese a que se pasó `company_id=70` real.

**Consecuencia práctica:** hoy, cualquier fila de `CatPrompt` con un `id_project` específico **nunca se va a encontrar**, para ninguna tool del sistema — solo resuelven las filas con `id_project` nulo/global. Para que `rag_document_search` funcione tal como está el código hoy, la fila nueva debe crearse con `id_project = NULL` (global), no scoped a un proyecto. Esto es un bug preexistente y transversal (no introducido por esta integración, no se corrigió aquí porque afecta a las 13 tools y tiene alcance fuera de lo pedido) — si se quiere soportar prompts por proyecto en el futuro, hay que corregir esa línea para leer `company_id` en vez de `id_company`.

### 3.5 API de simulación — para probar la tool aislada antes de integrarla al agente completo

Mismo patrón que ya existe para `company_document_query` (`POST /company-document-query/simulate`, `src/api/company_document_query/`): un endpoint que llama a la tool real (no una reimplementación) con `parameters` armados a mano, sin pasar por moderator/planner/selector de tools del agente completo. Implementado y verificado (sección 3.1, ronda 2):

- `POST {API_DEV_V1_CHAT_AGENT}/rag-document-search/simulate`
- **Body:** `{ companyId: int, query?: string }` (`RagDocumentSearchSimulateRequest`, `src/api/rag_document_search/request.py`). `query` opcional, usa una pregunta de validación por defecto si se omite.
- **Response 200** (`RagDocumentSearchSimulateResponse`, `src/api/rag_document_search/response.py`): `{ projectId, indexVecstore, query, searchResults: [{id, score, textPreview}], answer, llm, llmCode, provider, responseTime }`. `searchResults` es el retrieval crudo (llamada directa a `search_similar_documents`, independiente de la que hace la tool internamente) — permite distinguir "no encontró contexto relevante" de "encontró contexto pero el LLM respondió mal". `searchResults` vacío no es un error.
- **400**: `project` inválido/inactivo (mismo `ValueError` que ya usa `ProjectRepositoryInterface.get_project_by_id` en el resto de la API).
- **Servicio:** `RagDocumentSearchSimulationService` (`src/service/rag_document_search/rag_document_search_simulation_service.py`), inyectado vía `src/api/dependencies.py` (`get_rag_document_search_simulation_service`, `RagDocumentSearchSimulationServiceDep`). Registrado en `src/api/routes.py`.
- **Ya no bloqueado — verificado end-to-end el 2026-08-12**: el usuario creó la fila de `CatPrompt` (`id_project = NULL`) y corrió la guía completa de `pruebas-manuales-rag-document-search.md` contra los 3 servicios reales: `200` con respuesta real del LLM basada en un documento PDF real indexado en el proyecto `93`. En el camino se resolvió también P-30 (`RAG_OPENAI_EMBEDDING_DIMENSIONS=""` rompía `Settings` leyendo desde Vault, ver `pendientes.md`).

---

## 4. Cambios requeridos en `edi-ai-operator` — checklist actualizado

- [x] Config de conexión a `ai-rag-service-manager` (`RAG_SERVICE_BASE_URL`, agregada a `.env`; el repo usa `os.getenv` directo en el punto de uso, no un módulo de config centralizado, así que no hizo falta tocar `src/config/env.py`).
- [x] Implementar la tool nueva (3.1) y registrarla en `TOOLS_REGISTRY`.
- [x] Migrar `company_document_query.py` de `StorageService.download_file` a `rag_service_client.download_file` (`GET /api/v1/storage/get` de `ai-rag-service-manager`).
- [x] API de simulación para probar la tool aislada (3.5), `POST /rag-document-search/simulate` — verificada contra Postgres real y `ai-rag-service-manager` real.
- [x] Fila de `CatPrompt` con `id_project = NULL` — creada por el usuario 2026-08-12, confirmado `200` con respuesta real del LLM (`pruebas-manuales-rag-document-search.md`).
- [x] Confirmar 3.2 en la práctica (mismo espacio de `id_project` entre `edi-ai-operator` y Java) — validado con el proyecto real `93` end-to-end; sin cruce formal contra la base de Java, riesgo residual bajo.
- [ ] Fila de `cat_tools`/`tools_implemented` para que el selector de tools del agente pueda elegir `rag_document_search` — a cargo del usuario, sigue pendiente (no bloquea `/simulate`, sí bloquea la integración al agente completo). **Único ítem no-código que queda pendiente de este checklist.**
- [ ] Evaluar si corregir el bug preexistente `id_company`/`company_id` en `build_placeholders` (sección 3.4) — fuera de alcance de esta integración, afecta a las 13 tools, no solo a `rag_document_search`.
- [x] **Corte de storage completado (2026-08-12).** Se agregó `upload_file` a `rag_service_client.py` (no existía hasta ahora, junto a `download_file`/`search_similar_documents`) y se migraron los 7 consumidores restantes de `StorageService`: `thought_persistence_service.py`, `chat_history_service.py`, `context_memory_service.py`, `comun_service.py`, `report_service.py`, `ia_functions.py`, `ia_functions_cache.py`, `common_duck_db.py` — todos usan ahora `rag_service_client.upload_file`/`download_file` directamente. Se eliminó de paso el helper `file_upload()` de `comun_service.py`, que quedó sin ningún caller.
- [x] `src/service/util/storage_service.py` y `src/service/util/storage_config.py` (este último ya estaba huérfano) **eliminados**; dependencia `google-cloud-storage` **quitada** de `pyproject.toml`. `edi-ai-operator` queda sin ningún acceso directo a GCS — confirmado por grep (cero referencias a `StorageService`/`storage_service` en `src/`, fuera de docstrings de `rag_service_client.py`).
- [x] Verificación real del corte: import-check (no solo sintaxis) de los 10 módulos tocados —incluida `company_document_query.py`— contra la base de datos real de `edi-ai-operator`; los 10 importan limpio. `black` reformateó los 7 archivos con cambios sustanciales (se dejó `report_service.py` sin reformatear completo, su diff de `black` es deuda preexistente no relacionada a las 2 líneas tocadas). **No probado:** una llamada HTTP real a `/storage/upload`/`/storage/download` desde estos 8 archivos — el import-check confirma que el cableado es correcto, pero no ejercita el HTTP real contra `ai-rag-service-manager` (a diferencia de `rag_document_search`, que sí se probó de punta a punta, ver ronda 3 en `pendientes.md` P-28).
- [ ] Probar `rag_document_search` integrada al agente completo (moderator/planner/selector de tools), una vez resuelta la fila de `cat_tools`.
- [ ] Ejercitar en runtime real al menos un flujo de `upload_file`/`download_file` migrado (por ejemplo `save_thought` → `comun_service.py`) contra `ai-rag-service-manager` real.

## 5. Cambios requeridos en `ai-rag-service-manager`

Ninguno estructural — los endpoints que esta integración necesita ya existían: `/storage/get`, `/embedding/search_similar_documents`. Un fix chico sí salió de esta integración: `search_similar_documents` devolvía `results[].text_preview` en snake_case en vez de `textPreview` (inconsistente con el resto de la API) — corregido, ver `pendientes.md` P-29. Si el resto del checklist de la sección 4 revela otro caso de uso no cubierto, se agrega como pendiente nuevo en su momento.

## 6. Qué NO cambia

- Postgres propio de `edi-ai-operator` (`agent_execution`, `chat_ai.chat`) — metadata relacional, no archivos, sigue igual.
- Redis/RQ (cola de jobs, progreso de ejecución vía SSE) — sin relación con storage/RAG.
- El resto de las 11 tools existentes (`structured_data_queries`, `get_web_context`, `competing_projects`, etc.) — fuera de alcance de esta integración.
- `edi-ai-proyectos-backend` — sin cambios adicionales a los ya documentados en `integracion-java-storage.md`.
