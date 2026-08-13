# Integración `edi-ai-chat-backend` — storage centralizado

## 0. Contexto

`edi-ai-chat-backend` es un microservicio Python/FastAPI (Clean Architecture, PostgreSQL + Redis) nuevo en el workspace al momento de este análisis (2026-08-12), no cubierto por ninguna integración previa (`integracion-java-storage.md`, `integracion-operator-rag.md`). Mismo mandato que en esos dos repos: `ai-rag-service-manager` es el único microservicio con acceso directo a GCS y al vector store en todo el ecosistema.

## 1. Estado encontrado (AS-IS)

`src/app/application/services/storage/storage_service.py` — cliente GCS directo (`google.cloud.storage`), mismo patrón que tenían `edi-ai-operator` y `edi-ai-proyectos-backend` antes de su corte de storage:

```python
class StorageService:
    def __init__(self):
        self.default_bucket_name = settings.storage_default_bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.default_bucket_name)
    def upload_file(self, upload_file_request: UploadFileRequest) -> UploadFileResponse: ...
    def download_file(self, filename: str) -> bytes: ...
```

**Diferencia clave con los otros dos repos: este `StorageService` estaba completamente huérfano.** Grep exhaustivo (`StorageService`, `storage_service`, `upload_file`, `download_file`, `UploadFileRequest`) confirmó cero importadores/instanciadores en todo `src/` fuera del propio módulo — no está en `dependencies.py` (DI), no lo llama ningún controller/service, no se registra en el lifespan de `src/main.py`. Tampoco había ningún endpoint ni flujo de negocio (chat, proyectos, maturity models) que subiera o bajara archivos. El único caller potencial, `file_upload()` en `src/app/utils/utils.py` (construía un `UploadFile` en memoria desde un `ContextualMemory`, mismo patrón que el `file_upload()` ya eliminado en `edi-ai-operator`/P-28), tampoco tenía ningún caller propio.

Config asociada, también huérfana funcionalmente pero sí activa en `.env` (`STORAGE_DEFAULT_BUCKET_NAME`, `GOOGLE_APPLICATION_CREDENTIALS`) y comprometida en git: **tanto `.env` como `edward-creds.json` (credencial real de GCS) están trackeados en el repositorio** (`git ls-files` los confirma versionados, no en `.gitignore`) — mismo tipo de hallazgo que los secretos en texto plano de `edi-ai-proyectos-backend` (ver `integracion-java-storage.md`), reportado ahí y no corregido por decisión explícita de alcance.

## 2. Decisión y cambios aplicados (2026-08-12)

Dado que no había ningún flujo de negocio real que migrar (a diferencia de Java/operator, donde sí había callers activos), el trabajo fue: **eliminar el acceso directo a GCS y dejar la plumbing correcta para que, si en el futuro este servicio necesita storage, use `ai-rag-service-manager`.**

- **Nuevo:** `src/app/infrastructure/external/rag_service_client.py` — mismo contrato que el cliente ya usado en `edi-ai-operator` (`upload_file(name, content, bucket=None) -> bool`, `download_file(name, bucket=None) -> bytes`), usando `httpx` (ya era dependencia declarada del proyecto, se evitó agregar `requests` de nuevo). Lee la URL base desde `settings.rag_service_base_url` (nuevo, `RAG_SERVICE_BASE_URL`), no desde `os.getenv` directo, para ser consistente con el resto de este repo (todo pasa por el objeto `Settings` centralizado). `bucket` es opcional y **no se lee desde el entorno propio de este servicio** — mismo mandato que P-31: el bucket lo resuelve `ai-rag-service-manager` del lado servidor si no se envía explícito.
- **Eliminado:** `src/app/application/services/storage/storage_service.py` (GCS directo), `src/app/utils/upload_file.py` (`UploadFileRequest`/`UploadFileResponse`, sin otro uso), la función `file_upload()` de `src/app/utils/utils.py` (y sus imports ahora huérfanos: `io`, `UploadFile`, `ContextualMemory`), la dependencia `google-cloud-storage` de `pyproject.toml` (y `uv.lock` regenerado — quitó 16 paquetes, incluyendo `requests`, que era transitiva de `google-cloud-storage`, no declarada directamente).
- **Config eliminada de `Settings`/`​.env`:** `storage_default_bucket_name`, `google_application_credentials` (y el bloque que exportaba esta última a `os.environ` en `settings.py`). Config agregada: `rag_service_base_url` (`Optional[str]`, sin default — el cliente falla explícito si se usa sin configurar, no en el arranque de la app).
- **`Dockerfile`:** quitado `ENV GOOGLE_APPLICATION_CREDENTIALS="edward-creds.json"` (huérfano una vez removido el cliente GCS).
- **Hallazgo colateral corregido de paso:** `src/app/core/config/config_client.py` (cliente de Spring Cloud Config — confirmado también huérfano, nada lo importa) usaba `import requests` sin declararlo como dependencia propia, dependía de que `google-cloud-storage` lo trajera transitivamente. Al quitar esa dependencia se hubiera roto (`ModuleNotFoundError` si alguna vez se importa). Se migró a `httpx` (ya declarado) en vez de reagregar `requests`, mismo criterio que el resto de este cambio.
- **No tocado (fuera de alcance, riesgo/impacto mayor sin instrucción explícita):** `.env` y `edward-creds.json` siguen versionados en git con secretos reales — no se intentó purgar del historial ni rotar credenciales; solo se dejaron de referenciar desde el código, ya que ninguna otra funcionalidad en el repo los necesita.

## 3. Verificación real

- Import real de los módulos tocados (`settings`, `config_client`, `rag_service_client`, `utils`) — limpio.
- Import real de `src.main:app` (la app completa, con lifespan/routers/CORS configurados) — arranca sin error, 19 rutas registradas.
- Grep final sobre todo `src/` + `.env`/`Dockerfile`/`pyproject.toml`: cero referencias residuales a `google.cloud`, `StorageService`, `storage_default_bucket_name`, `google_application_credentials`.
- `uv lock` + `uv sync`: resueltos 36 paquetes (antes 52), sin errores.
- No se pudo verificar `black --check` — el grupo `dev` de `pyproject.toml` no está declarado correctamente como `[dependency-groups]`/`[project.optional-dependencies]` (`dev = [...]` suelto), por lo que `uv sync --group dev` falla con "Group `dev` no está definido" — **preexistente, no introducido por este cambio, fuera de alcance corregir aquí**. Se verificó en su lugar con `py_compile` (sintaxis limpia).
- No se pudo verificar en runtime real una llamada HTTP efectiva a `/storage/upload`/`/storage/get` — no hay ningún caller de negocio hoy que ejercite `rag_service_client.py` (ver sección 1), así que no hay un flujo end-to-end que probar todavía.

## 4. Qué NO cambia / queda pendiente

- No se creó ningún endpoint ni flujo de negocio nuevo que use `rag_service_client.py` — el trabajo fue dejar la plumbing lista y sin GCS directo, no inventar una feature de storage para este microservicio.
- El resto de la funcionalidad del repo (chat, proyectos, maturity models, cache) no tiene relación con storage y no se tocó.
- Pendiente si el equipo decide: rotar las credenciales de `edward-creds.json` y purgarlas del historial de git, y hacer lo mismo con la password real de `.env` (`DATABASE_PASSWORD`) — reportado, no corregido, mismo criterio que los secretos de `edi-ai-proyectos-backend`.
