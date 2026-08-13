# Pruebas manuales — `rag_document_search` (`edi-ai-operator` ↔ `ai-rag-service-manager`)

**✅ Verificada end-to-end el 2026-08-12** contra los 3 servicios reales (`ai-rag-service-manager` puerto `7006`, `edi-ai-operator` puerto `7004`), con un documento PDF real (política de privacidad) y un proyecto real (`93`): upload+vectorización, retrieval confirmado, y `POST /rag-document-search/simulate` respondiendo `200` con una respuesta real del LLM basada en el contenido del documento. Ver `pendientes.md` P-28 (ronda 3 de verificación) y P-30 (bug encontrado y corregido en el camino).

Guía paso a paso con `curl` para probar la integración de punta a punta: subir y vectorizar un documento en `ai-rag-service-manager`, y luego consultarlo vía la API de simulación de `edi-ai-operator` (`POST /rag-document-search/simulate`, ver `integracion-operator-rag.md` sección 3.5).

**Ninguna llamada de esta guía necesita header `Authorization`** — ni `ai-rag-service-manager` ni el endpoint de simulación de `edi-ai-operator` implementan autenticación (ver `pendientes.md` P-13 en `ai-rag-service-manager`).

Puertos usados abajo (confirmar contra el ambiente real antes de correr, ver nota en `integracion-operator-rag.md` sobre 8080/nginx vs 7006):

| Servicio | Puerto |
|---|---|
| `ai-rag-service-manager` | `7006` |
| `edi-ai-operator` | `7004` |

---

## 0. Prerrequisitos

- `ai-rag-service-manager` arriba, con:
  - `RAG_EMBEDDING_PROVIDER=local` (sin key) **o** `openai` con una `OPENAI_API_KEY` real configurada — sin esto, `/storage/upload` falla con `500` aunque no se pida vectorizar (ver `pendientes.md` P-27).
  - Credenciales de GCS configuradas (`GOOGLE_CREDS_JSON` o `GOOGLE_APPLICATION_CREDENTIALS` apuntando a un service account válido) y `STORAGE_DEFAULT_BUCKET_NAME` con un bucket real.
- `edi-ai-operator` arriba, con `RAG_SERVICE_BASE_URL` apuntando al `ai-rag-service-manager` de arriba.
- La fila de `CatPrompt` para `rag_document_search` ya creada en la base de datos de `edi-ai-operator`, **con `id_project = NULL`** (global) — ver el hallazgo del bug `id_company`/`company_id` en `integracion-operator-rag.md` sección 3.4. Sin esto, el paso 4 responde `500`.
- La fila de `cat_tools`/`tools_implemented` para `rag_document_search` (solo hace falta si además se va a probar integrada al agente completo, no para esta guía).
- Un `project_id` real y activo en la base de `edi-ai-operator` (los ejemplos usan `93`).

---

## 1. Health checks

```bash
curl -s http://localhost:7006/api/v1/health/live; echo
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:7004/docs
```

Esperado: `{"status":"alive"}` y `200`.

---

## 2. Subir y vectorizar un documento

`uploadContentBucket=true` + `uniqueCode` disparan vectorización en background contra la colección `project_{projectId}` (ver `api.md` sección `/storage/upload`, y `pendientes.md` P-10/P-25).

```bash
curl -s -X POST http://localhost:7006/api/v1/storage/upload \
  -F "file=@/ruta/al/documento.pdf;type=application/pdf" \
  -F "name=politica_de_privacidad-1.pdf" \
  -F "bucket=dev-documentos" \
  -F "projectId=93" \
  -F "uploadContentBucket=true" \
  -F "uniqueCode=politica-privacidad-ara-93" \
  -F "codeTypeDocument=PRIVACY_POLICY"
echo
```

**Respuesta esperada:** `{"success": true}`. Solo confirma el upload a GCS — la vectorización corre en background, best-effort, sin callback (ver `integracion-java-storage.md` sección 2 sobre por qué no hace falta uno). Esperar unos segundos antes del paso 3.

---

## 3. Confirmar que el documento quedó indexado (directo contra `ai-rag-service-manager`)

```bash
curl -s -X POST http://localhost:7006/api/v1/embedding/search_similar_documents \
  -H "Content-Type: application/json" \
  -d '{
    "indexVecstore": "project_93",
    "query": "derechos ARCO",
    "topK": 3
  }'
echo
```

**Esperado:** `results` con al menos un fragmento del documento subido, `textPreview` mencionando el tema buscado.

Listado liviano de documentos únicos del proyecto (opcional, body es un string JSON plano, no un objeto — ver `api.md`):

```bash
curl -s -X POST http://localhost:7006/api/v1/embedding/list_unique_code_documents \
  -H "Content-Type: application/json" \
  -d '"project_93"'
echo
```

---

## 4. Probar `rag_document_search` aislada, desde `edi-ai-operator` (sin pasar por el agente completo)

```bash
curl -s -X POST http://localhost:7004/api/operator/v1/rag-document-search/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "companyId": 93,
    "query": "¿Cuáles son los medios para ejercer los derechos ARCO?"
  }'
echo
```

**Respuesta 200 esperada** (`RagDocumentSearchSimulateResponse`, ver `integracion-operator-rag.md` sección 3.5):

```json
{
  "projectId": 93,
  "indexVecstore": "project_93",
  "query": "¿Cuáles son los medios para ejercer los derechos ARCO?",
  "searchResults": [ { "id": "...", "score": 0.xx, "textPreview": "..." } ],
  "answer": "...",
  "llm": "...",
  "llmCode": "...",
  "provider": "...",
  "responseTime": 0.xx
}
```

`query` es opcional — si se omite, usa una pregunta de validación por defecto (solo para confirmar que la tool corre de punta a punta).

**Errores esperados y su causa:**

| Código | Causa |
|---|---|
| `400` | El `companyId` no existe o no está activo en la base de `edi-ai-operator`. |
| `500` | Falta la fila de `CatPrompt` para `rag_document_search` (o tiene `id_project` distinto de `NULL`, ver prerrequisitos). |
| `500` (en el paso 2, no en este) | Falta `OPENAI_API_KEY` (si `RAG_EMBEDDING_PROVIDER=openai`) o credenciales de GCS en `ai-rag-service-manager`. |

---

## 5. Limpieza (opcional)

```bash
curl -s -X POST http://localhost:7006/api/v1/embedding/delete_index_vecstore \
  -H "Content-Type: application/json" \
  -d '{"indexVecstore": "project_93"}'
echo
```

⚠️ Esto borra **toda** la colección vectorial del proyecto 93, no solo el documento de prueba — no correr si el proyecto tiene otros documentos reales ya indexados.
