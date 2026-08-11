# ai-rag-service-manager

`ai-rag-service-manager` es un microservicio construido con FastAPI y Uvicorn para dos responsabilidades principales:

1. administrar definiciones operativas de servicios RAG;
2. exponer un flujo de embedding, indexación y retrieval sobre una base vectorial abstraída.

La solución está organizada como una arquitectura modular por capas. No busca una hexagonal pura, pero sí mantiene una separación clara entre transporte HTTP, lógica de aplicación, dominio, configuración compartida e infraestructura técnica.

## Evaluación de la arquitectura

La arquitectura actual es correcta para el alcance implementado.

Puntos fuertes:

- los controllers HTTP son delgados y delegan la lógica a servicios;
- la configuración está centralizada en `Settings` y no dispersa por módulos;
- el dominio de `RagService` tiene su entidad y su contrato de repositorio propios;
- la infraestructura externa está separada en clientes y adapters;
- el wiring de dependencias está concentrado en `app/api/dependencies/services.py`;
- el motor RAG no depende de FastAPI ni conoce detalles HTTP.

Matices importantes:

- es una arquitectura por capas con rasgos de Clean Architecture, no una implementación estricta de puertos y adaptadores;
- el backend vectorial real todavía no está integrado: hoy el servicio trabaja con un store en memoria detrás de `VectorStoreManager`;
- existen utilidades transversales en `app/core`, lo cual es razonable mientras sigan siendo técnicas y no mezclen reglas de negocio.

En su estado actual, la estructura es coherente, mantenible y adecuada para evolucionar sin reescribir la base del servicio.

## Definición funcional

El microservicio expone dos capacidades:

- gestión de configuraciones de servicios RAG (`rag-services`);
- operación documental para embeddings y retrieval (`embedding`).

Una definición de servicio RAG administra información como:

- nombre y descripción;
- proveedor LLM;
- modelo de chat;
- modelo de embeddings;
- backend vectorial deseado;
- URL base opcional;
- metadatos operativos;
- estado (`draft`, `active`, `disabled`).

La parte documental permite:

- indexar documentos desde contenido base64 o desde una URL;
- listar documentos por colección;
- recuperar chunks por `unique_code`;
- ejecutar búsqueda semántica;
- recuperar contexto para preguntas tipo RAG.

## Arquitectura del sistema (multi-servicio)

**Principio:** `ai-rag-service-manager` es el único microservicio con acceso directo a storage (Google Cloud Storage) y al vector store. Ningún otro microservicio debe tener credenciales de GCS ni un cliente propio contra la base vectorial — si necesita subir, leer, indexar o consultar documentos, lo hace a través de este servicio.

Esto no cambia dónde llegan las peticiones del frontend: `edi-ai-proyectos-backend` (Java) sigue siendo el punto de entrada de la API para el frontend. Lo que cambia es que, puertas adentro, Java deja de resolver storage y vectorización por sí mismo y enruta esas operaciones a `ai-rag-service-manager`:

```text
Frontend
   │
   ▼
edi-ai-proyectos-backend (Java) ── sigue siendo el punto de entrada de la
   │                                API para el frontend; ya no debe tener
   │                                acceso directo a GCS ni a un vector store.
   │
   ├── POST /api/v1/storage/upload         ──┐
   ├── POST /api/v1/storage/chunk           │  ai-rag-service-manager
   ├── GET  /api/v1/storage/get             ├─ (único cliente de GCS
   ├── GET  /api/v1/storage/getFileByte     │   de todo el sistema)
   ├── POST /api/v1/storage/public-upload  ─┘
   │
   └── POST /api/v1/embedding/save_document_vecstore  ──┐
       POST /api/v1/embedding/delete_index_vecstore     │  ai-rag-service-manager
       POST /api/v1/embedding/list_documents            ├─ (único cliente del
       POST /api/v1/embedding/get_embeddings_by_unique_code │  vector store de
       POST /api/v1/embedding/search_similar_documents  │   todo el sistema)
       POST /api/v1/embedding/rag_query                ─┘
```

Los embeddings siguen la misma regla que el storage: cualquier operación de indexación, borrado, listado o búsqueda semántica se consulta contra `ai-rag-service-manager` (`/api/v1/embedding/*`), no contra un motor de embeddings propio de Java ni de otro microservicio.

Estado real hoy en `edi-ai-proyectos-backend` (no es aspiracional, es lo verificado en este repo Java — ver `pendientes.md` P-10/P-11/P-20/P-21/P-22/P-23/P-24/P-25/P-26):

- **Embeddings ya enrutados y activos, sin brechas conocidas:** los cuatro métodos de vectorización de `VectorStoreServiceImpl` (`saveEmbeddingFile`, `deleteIndexVecstore`, `deleteEmbeddingDocument`, `getListUniqueCodeDocuments`) llaman a `ai-rag-service-manager` (`app.rag-service.*`), no a `analysis-ai-service`. Los últimos dos se repuntaron una vez agregados los endpoints `delete_document`/`list_unique_code_documents` (`pendientes.md` P-22/P-23) — el campo `openaiConfig` quedó sin uso en esa clase y se eliminó.
- **Storage todavía no cortado:** existe `RagServiceStorageClient` (implementación de `StorageService` contra `ai-rag-service-manager`), pero `StorageServiceImpl` (GCS local) sigue siendo el bean `@Primary` activo — el corte se hace cambiando el `@Qualifier` una vez que se pruebe en un ambiente real (no se activó de una vez porque no había forma de probarlo end-to-end desde este entorno).

Detalle completo — mapeo de campos, incompatibilidades de contrato ya resueltas, checklist de migración de Java: ver [`integracion-java-storage.md`](./integracion-java-storage.md).

## Arquitectura

### Capas

- `app/main.py`: punto de entrada, creación de la aplicación, middleware y ciclo de vida.
- `app/api/`: capa HTTP; contiene controllers y dependencias de FastAPI.
- `app/core/`: configuración, logging y utilidades técnicas compartidas.
- `app/domain/`: entidades y contratos del dominio.
- `app/services/`: lógica de aplicación y orquestación de casos de uso.
- `app/infrastructure/`: clientes externos, repositorios concretos y vector store adapters.
- `app/schemas/`: modelos Pydantic de entrada y salida para la API.

### Estructura del proyecto

```text
ai-rag-service-manager/
├── app/
│   ├── api/
│   │   ├── dependencies/
│   │   │   └── services.py
│   │   ├── routes/
│   │   │   ├── embedding_controller.py
│   │   │   ├── health_controller.py
│   │   │   └── rag_services_controller.py
│   │   └── router_controller.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── schema.py
│   │   └── utils.py
│   ├── domain/
│   │   ├── entities/
│   │   │   └── rag_service.py
│   │   └── repositories/
│   │       └── rag_service_repository.py
│   ├── infrastructure/
│   │   ├── clients/
│   │   │   ├── config_server.py
│   │   │   ├── eureka.py
│   │   │   ├── storage_client.py
│   │   │   └── storage_config.py
│   │   ├── embeddings/
│   │   │   └── embedding_provider.py
│   │   ├── repositories/
│   │   │   └── in_memory_rag_service_repository.py
│   │   └── vector_store/
│   │       ├── milvus_vector_store.py
│   │       ├── vector_store_interface.py
│   │       └── vector_store_manager.py
│   ├── schemas/
│   │   ├── embedding.py
│   │   ├── rag_service.py
│   │   └── storage.py
│   ├── services/
│   │   ├── embedding/
│   │   │   └── document_embedding_service.py
│   │   ├── rag/
│   │   │   ├── rag_agent.py
│   │   │   └── rag_service.py
│   │   ├── rag_service.py
│   │   └── storage_service.py
│   └── main.py
├── .env.example
├── Dockerfile
├── pyproject.toml
└── README.md
```

### Flujo principal

1. `app/main.py` crea la aplicación FastAPI y orquesta startup y shutdown.
2. `app/api/router_controller.py` compone los controllers HTTP.
3. Los controllers resuelven dependencias desde `app/api/dependencies/services.py`.
4. Los servicios aplican la lógica de negocio o de aplicación.
5. La infraestructura aporta repositorios, clients tecnicos y acceso al vector store.

### Convencion de infraestructura

- `clients`: conexiones a SDKs y APIs externas
- `repositories`: implementaciones concretas de persistencia del dominio
- `vector_store`: adapters tecnicos para backends vectoriales

## Componentes clave

### API

- `health_controller.py`: endpoints de liveness y readiness.
- `rag_services_controller.py`: CRUD de definiciones de servicios RAG.
- `embedding_controller.py`: operaciones documentales y consultas RAG.

### Servicios

- `RagServiceManager`: administra el ciclo de vida de configuraciones RAG.
- `DocumentEmbeddingService`: indexa documentos, lista resultados y ejecuta búsquedas.
- `RAGService`: servicio central de chunking, embedding real e indexación/retrieval.
- `RAGAgent`: facade orientado a consultas sobre una colección de conocimiento.

### Infraestructura

- `InMemoryRagServiceRepository`: persistencia temporal de definiciones RAG.
- `EmbeddingProvider`: carga un modelo real de embeddings (`sentence-transformers`, vía `pymilvus.model`) una sola vez y lo comparte entre colecciones — ver `RAG_EMBEDDING_MODEL`/`RAG_EMBEDDING_DEVICE`/`RAG_NORMALIZE_EMBEDDINGS`.
- `VectorStoreManager`: facade para el backend vectorial configurado (`VECTOR_DB_TYPE`).
- `InMemoryVectorStore`: adapter en memoria, default para desarrollo local sin dependencias externas.
- `MilvusVectorStore`: adapter real contra Milvus (`pymilvus.MilvusClient`) cuando `VECTOR_DB_TYPE=milvus` — colección con `id` + `vector` + un campo `payload` JSON que preserva la metadata libre que ya usa el resto de la app.
- `StorageClient`: descarga archivos desde URL o GCS.
- `ConfigServerClient`: consulta Spring Config Server solo durante el startup.
- `EurekaRegistrar`: registra y detiene el servicio en Eureka como parte del ciclo de vida.

## Alcance actual

Incluido en esta versión:

- FastAPI + Uvicorn;
- configuración con `pydantic-settings`;
- readiness con estado de Config Server y Eureka;
- logging centralizado con Correlation ID;
- CRUD de `rag-services`;
- embeddings reales (`sentence-transformers`, local, vía `pymilvus.model`) e indexación/retrieval semántico contra memoria o Milvus (`VECTOR_DB_TYPE=memory|milvus`);
- Docker listo para ejecución local, con el modelo de embeddings pre-descargado en el build.

Exclusiones intencionales:

- ORM / SQLAlchemy;
- Alembic;
- autenticación JWT/OAuth2;
- OpenTelemetry;
- colas como Kafka o RabbitMQ;
- generación de respuesta vía LLM en `rag_query` (hoy retorna el contexto recuperado, no una respuesta generada — ver `pendientes.md` P-05).

## Configuración

Las variables se centralizan en `app/core/config.py` y se documentan en `.env.example`.

Variables relevantes:

- `APP_NAME`, `APP_ENV`, `APP_HOST`, `APP_PORT`, `APP_API_PREFIX`
- `USE_SPRING_CLOUD_CONFIG`, `SPRING_CLOUD_CONFIG_URI`, `SPRING_PROFILES_ACTIVE`
- `EUREKA_ENABLED`, `EUREKA_SERVER_URL`, `EUREKA_APP_NAME`
- `VECTOR_DB_TYPE`
- `MILVUS_HOST`, `MILVUS_PORT`, `MILVUS_DB_NAME`, `MILVUS_ALIAS`
- `RAG_COLLECTION_NAME_PREFIX`, `RAG_DEFAULT_COLLECTION_NAME`
- `RAG_EMBEDDING_MODEL`, `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_DEFAULT_TOP_K`

Notas operativas:

- `SPRING_CLOUD_CONFIG_URI` se consulta solo al arrancar la aplicación;
- `VECTOR_DB_TYPE=milvus` requiere un Milvus real alcanzable en `MILVUS_HOST:MILVUS_PORT`; con `memory` (default) no hace falta nada externo;
- `RAG_EMBEDDING_MODEL` se descarga/carga una sola vez al arrancar (`EmbeddingProvider`), no por request; cambiarlo implica reconstruir la imagen Docker para no depender de red en el arranque (ver sección Docker).

## Ejecutar localmente

Con `uv`:

```bash
uv sync
uv run python -m app.main
```

Con `venv` tradicional:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m app.main
```

## Configuracion de Vault

Vault es **opcional**, controlado por `USE_VAULT_CONFIG` (mismo patron que `USE_SPRING_CLOUD_CONFIG`/`EUREKA_ENABLED`, ver `pendientes.md` P-17):

- `USE_VAULT_CONFIG=false` o ausente (default): no se intenta Vault. La configuracion sale de variables de entorno ya exportadas y, como fallback, de un archivo `.env` en la raiz del repo (ver `.env.example`). Es el modo pensado para trabajo local sin depender de infraestructura externa.
- `USE_VAULT_CONFIG=true`: se intenta Vault al arrancar. Si falta `VAULT_ADDR` o `VAULT_TOKEN`, el arranque falla fuerte con un mensaje listando exactamente que falta — no cae en silencio a `.env`.

Para trabajar 100% local sin Vault:

```bash
cp .env.example .env
# dejar USE_VAULT_CONFIG=false (default en .env.example)
uv run python -m app.main
```

Para usar Vault, define estas variables de entorno antes de ejecutar el servicio:

```bash
export USE_VAULT_CONFIG=true
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root-token
```

Si Vault expone HTTPS con un certificado firmado por una CA interna, define tambien:

```bash
export VAULT_CACERT=/ruta/al/ca.pem
```

Si el endpoint interno usa HTTPS pero el certificado no fue emitido para el hostname del contenedor, puedes desactivar la verificacion TLS para esa conexion:

```bash
export VAULT_SKIP_VERIFY=true
```

Usa `VAULT_SKIP_VERIFY` solo cuando no puedas corregir el certificado o el nombre DNS del servicio.
Cuando este valor esta activo, la aplicacion tambien silencia el `InsecureRequestWarning` de `urllib3` para evitar ruido repetitivo en logs.

Si quieres dejarlas persistentes en tu shell:

```bash
echo 'export USE_VAULT_CONFIG=true' >> ~/.bashrc
echo 'export VAULT_ADDR=http://localhost:8200' >> ~/.bashrc
echo 'export VAULT_TOKEN=root-token' >> ~/.bashrc
source ~/.bashrc
```

Si usas otro host o token, reemplaza esos valores por los de tu entorno.

Con secretos fuera del repositorio:

El proyecto puede arrancar sin `.env` dentro del repositorio si cargas las variables de entorno desde una carpeta hermana usando `run-local.sh`.

El script usa por defecto esta ruta relativa al microservicio:

```text
../company-secrets/${SERVER_DEPLOYMENT:-dev}
```

Con la estructura real local:

```text
PROYECTO/
├── ai-rag-service-manager/
└── company-secrets/
	├── dev/
	│   ├── common.env
	│   ├── storage.env
	│   └── ai-rag-service-manager.env
	├── qa/
	└── prod/
```

En `dev`, por ejemplo, el script intentara leer:

- `../company-secrets/dev/common.env`
- `../company-secrets/dev/storage.env`
- `../company-secrets/dev/ai-rag-service-manager.env`

Arranque local por defecto:

```bash
chmod +x run-local.sh
export USE_VAULT_CONFIG=true
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root-token
./run-local.sh
```

El script hace esto:

- carga `common.env`, `storage.env` y `ai-rag-service-manager.env` desde `../company-secrets/${SERVER_DEPLOYMENT:-dev}`;
- exporta las variables al proceso antes de arrancar el microservicio;
- espera que `GOOGLE_CREDS_JSON` ya venga definido como JSON inline en alguno de esos archivos o desde Vault;
- arranca el servicio con `uv run python -m app.main`.

Cambiar el ambiente sin tocar el script:

```bash
SERVER_DEPLOYMENT=qa ./run-local.sh
```

```bash
SERVER_DEPLOYMENT=prod ./run-local.sh
```

Usar una ruta completamente distinta para secretos:

```bash
SECRETS_DIR=/ruta/a/tus/envs ./run-local.sh
```

Ejecutar otro comando con las variables ya cargadas:

```bash
./run-local.sh env | grep '^APP_'
```

```bash
./run-local.sh uv run python -m app.main
```

Nota de precedencia:

- las variables exportadas por el shell y por `run-local.sh` son las que toma la aplicacion al arrancar;
- el archivo `.env` definido en `Settings` queda como fallback, no como requisito;
- si defines `SECRETS_DIR`, esa ruta tiene prioridad sobre `SERVER_DEPLOYMENT`.

Documentación automática:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Análisis con SonarQube

La configuración de Sonar para este repositorio vive en `sonar-project.properties` y está ajustada para analizar solo el código del microservicio en `app/`.

Qué evita esta configuración:

- directorios ocultos y de tooling como `.venv`, `.history`, `.github`, `.vscode`, `.idea`;
- caches de Python y herramientas como `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`;
- archivos de entorno como `.env` y `.env.*`;
- documentación Markdown y carpetas auxiliares como `docs/` y `logs/`.

Importante:

- no se debe guardar `sonar.token` en `sonar-project.properties`;
- usa una variable de entorno o pásalo por línea de comandos.

Ejemplo de ejecución local:

```bash
export SONAR_TOKEN="tu_token_de_sonar"
sonar-scanner -Dsonar.token="$SONAR_TOKEN"
```

Si usas el entorno virtual del proyecto:

```bash
source .venv/bin/activate
export SONAR_TOKEN="tu_token_de_sonar"
sonar-scanner -Dsonar.token="$SONAR_TOKEN"
```

Recomendaciones para mantener el análisis limpio:

- mantén `sonar.sources=app` para que Sonar no indexe la raíz completa del repositorio;
- agrega nuevas exclusiones solo si un archivo técnico termina dentro de `app/` o si en el futuro cambias `sonar.sources`;
- si agregas pruebas en `tests/`, puedes declarar `sonar.tests=tests` y reportar cobertura desde `pytest`.

## Estándar de calidad, seguridad y arquitectura

Resumen operativo del estándar corporativo mínimo que este proyecto sigue como referencia para microservicios Python. Originalmente vivía como archivo aparte (`ESTANDAR_MICROSERVICIO_PYTHON.md`); se migró aquí para no mantener dos documentos, y el archivo se eliminó del repo. Los números de sección (`§N`) se conservan tal cual porque `pendientes.md` los usa para trazabilidad de cumplimiento — no renumerar si se edita esta sección.

**Objetivo:** calidad y mantenibilidad del código, seguridad de la aplicación y de la API, trazabilidad y observabilidad, pruebas automatizadas, control de vulnerabilidades, consistencia arquitectónica, seguridad de imágenes Docker, integración con CI/CD.

**Alcance:** aplica a microservicios Python, típicamente con FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Redis, Docker, Keycloak/OAuth2/OIDC. Las herramientas concretas pueden cambiar; los controles de calidad y seguridad deben mantenerse. *(En `ai-rag-service-manager` no hay hoy DB relacional, Redis ni auth federada — ver "Alcance actual" más arriba; esas partes del estándar no aplican mientras eso no cambie.)*

### §3 — Estándar tecnológico mínimo

| Categoría | Estándar / herramienta | Requisito |
|---|---|---|
| Lenguaje | Python 3.12+ | Obligatorio |
| Framework API | FastAPI | Cuando corresponda |
| Validación | Pydantic | Obligatorio para contratos API |
| Lint / formato | Ruff | Obligatorio |
| Tipado | mypy | Obligatorio |
| Tests | pytest | Obligatorio |
| Cobertura | pytest-cov | Obligatorio |
| Calidad | SonarQube | Obligatorio |
| Seguridad Python | Bandit | Obligatorio |
| Dependencias | pip-audit | Obligatorio |
| Secretos | Gitleaks | Obligatorio |
| Container security | Trivy | Obligatorio |
| API | OpenAPI | Obligatorio |
| Observabilidad | OpenTelemetry | Recomendado / obligatorio en producción |
| Autenticación | OAuth2/OIDC / Keycloak | Según arquitectura |
| Contenedores | Docker | Según despliegue |

### §4-5 — Calidad de código y tipado estático

- `ruff format --check .` y `ruff check .` deben pasar con 0 errores; excepciones justificadas y documentadas (`# noqa`/`# nosec` con motivo, no a secas).
- `mypy` con `disallow_untyped_defs`, `check_untyped_defs`, `no_implicit_optional`, `warn_unused_ignores`, `warn_redundant_casts` en 0 errores. Toda función nueva debe llevar anotaciones de tipo.

### §6 — Arquitectura del microservicio

Separación mínima: `HTTP/API → Application/Services → Domain → Repositories → Infrastructure`. Ningún endpoint debe concentrar validación, lógica de negocio, acceso a datos, llamadas a otros servicios, manejo de errores y construcción de la respuesta completa a la vez — eso vive en el router delegando a un service/use case, que delega a un repository.

### §7 — API REST

Contrato documentado vía OpenAPI: endpoints, métodos, parámetros, headers, request/response body, códigos HTTP, errores, autenticación, ejemplos. Cambios incompatibles requieren nueva versión (`/api/v1` → `/api/v2`), no romper el contrato existente.

### §8 — Validación de datos

Toda entrada (HTTP, query/path params, headers, body, respuestas de servicios externos) se valida con Pydantic/FastAPI. Nunca confiar directamente en datos del cliente.

### §9 — Manejo de errores

Prohibido `except Exception: pass` o solo `print(e)`. Usar excepciones específicas y handlers globales cuando corresponda. Mapeo esperado: `NotFoundException→404`, `ValidationError→400/422`, `Unauthorized→401`, `Forbidden→403`, `Conflict→409`, error inesperado→500. Los errores internos no deben exponer stack traces, contraseñas, tokens, credenciales ni detalles de infraestructura.

### §10 — Seguridad (OWASP)

Considerar como mínimo OWASP Top 10 y OWASP API Security Top 10, con atención especial a: Broken Object/Function Level Authorization, Broken Authentication, Unrestricted Resource Consumption, SSRF, Security Misconfiguration, Improper Inventory Management, Unsafe Consumption of APIs.

### §11 — Autenticación y autorización

Cuando se usa Keycloak/OIDC: validar firma del token, issuer, audience, expiración, roles, scopes y permisos. No confundir autenticación (`401` = no autenticado/token inválido) con autorización (`403` = autenticado sin permisos).

### §12 — Gestión de secretos

Prohibido hardcodear passwords, API keys, client secrets, JWT secrets, tokens, private keys o connection strings con credenciales en el código fuente. Usar Vault, Secret Manager, Kubernetes Secrets o variables protegidas de CI/CD.

### §13 — Bandit

`bandit -r app/` — objetivo mínimo `High: 0`. Hallazgos Medium deben revisarse y, si se aceptan, documentarse.

### §14 — Dependencias

Dependencias de producción controladas y versionadas, sin depender de versiones flotantes sin límite. Usar un mecanismo de lock cuando la herramienta lo soporte.

### §15 — Auditoría de dependencias

`pip-audit` — objetivo: 0 vulnerabilidades conocidas críticas/altas explotables. Excepciones justificadas y con seguimiento. Se recomienda Dependabot/Renovate para mantener dependencias actualizadas.

### §16 — Detección de secretos (Gitleaks)

`gitleaks detect` sobre el repositorio (incluyendo historial) y en el pipeline de CI/CD — objetivo: 0 secretos detectados.

### §17 — SonarQube

Quality Gate mínimo: `Blocker Issues=0`, `Critical Bugs=0`, `Critical Vulnerabilities=0`, `Security Hotspots=100% revisados`, `Code Coverage>=80%`, `Duplicación<3%` (recomendado), `Quality Gate=PASS`. El pipeline no debe permitir promoción si el Quality Gate falla.

### §18 — Pruebas automatizadas

Unitarias, integración, API, validaciones, manejo de errores y casos límite. `pytest --cov=app --cov-report=term-missing` — objetivo `Coverage >= 80%`. La cobertura por sí sola no garantiza calidad: deben probarse escenarios funcionalmente relevantes.

### §19 — HTTP Status Codes

Mínimo: `200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503`, usados correctamente. Nunca `200 OK` para representar un error funcional.

### §20-21 — Timeouts y Retries

Toda llamada a servicios externos debe tener timeout explícito (nunca una llamada bloqueante sin límite). Retries solo cuando tenga sentido, con backoff exponencial y, si aplica, circuit breaker; nunca reintentar automáticamente una operación no idempotente sin analizar el riesgo de duplicación.

### §22 — Logging

Nunca `print()` como logging de producción; usar `logging` con logs estructurados, trazables y consistentes entre microservicios. Nunca loguear passwords, tokens, headers de autorización, API keys, client secrets, private keys, ni información personal innecesaria.

### §23 — Correlation ID

Cada petición debe poder relacionarse entre microservicios mediante un identificador de correlación/traza (ej. `X-Correlation-ID`) propagado de extremo a extremo.

### §24 — Health Checks

Mínimo `GET /health`; preferible `GET /health/live` (liveness: el proceso está vivo) y `GET /health/ready` (readiness: el servicio puede recibir tráfico, validando dependencias críticas).

### §25 — OpenTelemetry

Para producción: instrumentar traces, metrics, logs y correlation/trace IDs, de forma que una petición se pueda visualizar de extremo a extremo entre servicios.

### §26 — Docker

Imágenes base oficiales, preferir `slim`, sin herramientas innecesarias, sin secretos en la imagen, sin correr como root, con `.dockerignore`, imagen actualizada.

### §27 — Trivy

`trivy image <imagen>` antes de desplegar — objetivo `CRITICAL: 0`, `HIGH: 0`. Excepciones justificadas y documentadas.

### §28 — Variables de entorno

Configuración separada del código (`DATABASE_HOST`, `REDIS_HOST`, `KEYCLOAK_URL`, `LOG_LEVEL`, etc.), sin valores sensibles en el repositorio. Separar código / configuración / secretos.

### §29-30 — Base de datos y Redis

Acceso a BD mediante una capa definida (`Service → Repository → SQLAlchemy → PostgreSQL`), sin SQL directo en routers, con migraciones versionadas (Alembic/Liquibase u otra herramienta institucional). Redis: definir TTL, evitar datos sensibles innecesarios, controlar tamaño de claves/valores, timeout y comportamiento ante indisponibilidad. *(No aplica hoy a este proyecto: sin DB relacional ni Redis — ver "Alcance actual".)*

### §31-32 — CI/CD

Pipeline mínimo: `checkout → deps → Ruff → mypy → pytest+coverage → Bandit → pip-audit → Gitleaks → SonarQube → Docker build → Trivy → Quality Gates → Deploy`. El despliegue debe bloquearse si falla un control crítico.

### §33 — Checklist mínimo antes de producción

**Código:** Ruff sin errores · formateado · mypy sin errores · sin `print()` de producción · sin TODO críticos · sin código muerto · sin excepciones silenciosas · sin credenciales en código.

**Tests:** unit tests · integration tests cuando corresponda · API tests · coverage ≥ 80% · casos de error probados.

**Seguridad:** OWASP Top 10 y API Top 10 revisados · Bandit ejecutado · pip-audit ejecutado · Gitleaks ejecutado · SonarQube Quality Gate aprobado · autenticación y autorización validadas · secrets fuera del código.

**Docker:** imagen actualizada · usuario no-root · `.dockerignore` · sin secretos en la imagen · Trivy ejecutado con Critical=0 y High=0.

**API:** OpenAPI actualizado · códigos HTTP correctos · validaciones implementadas · errores estandarizados · versionamiento definido · timeouts configurados.

**Operación:** `/health` implementado · liveness · readiness · logging estructurado · Correlation ID · métricas · trazabilidad · OpenTelemetry cuando corresponda.

### §34 — Quality Gate corporativo recomendado

Un microservicio **no debe pasar a producción** si no cumple:

```text
SonarQube Quality Gate        = PASS
Ruff                          = PASS
mypy                          = PASS
pytest                        = PASS
Coverage                      >= 80%
Bandit High                   = 0
Dependencias vulnerables      = 0 críticas/altas
Gitleaks                      = 0 secretos
Trivy Critical                = 0
Trivy High                    = 0
Documentación OpenAPI         = OK
Health checks                 = OK
Autenticación/autorización    = OK
Secrets fuera del código      = OK
```

### §35 — Excepciones

Cuando un microservicio no pueda cumplir temporalmente un requisito: la excepción debe quedar documentada, indicar el motivo, identificar el riesgo, definir una fecha o condición de corrección, y contar con aprobación del responsable técnico cuando corresponda. No usar excepciones permanentes para ignorar los controles. Este proyecto sigue este proceso en [`pendientes.md`](./pendientes.md): cada `P-XX` es una excepción o brecha trazada con esa misma estructura (motivo, riesgo, estado, resolución).

### §36 — Resultado esperado

Un microservicio se considera apto para producción cuando demuestra, con código y CI/CD, sus tres pilares — **Calidad** (Ruff, mypy, pytest, SonarQube), **Seguridad** (OWASP, Bandit, pip-audit, Gitleaks, Trivy) y **Operabilidad** (Logging, Metrics, Health, Tracing) — y el pipeline obtiene todos los Quality Gates requeridos.

## Calidad y seguridad

El detalle de qué tanto cumple hoy `ai-rag-service-manager` con el estándar de arriba, sección por sección y con evidencia real de cada herramienta, vive en [`pendientes.md`](./pendientes.md) (`P-18`) — esta sección solo documenta **qué está instalado y cómo correrlo**.

### Instalar las herramientas de desarrollo

Todas las herramientas de calidad/seguridad son dependencias `dev` declaradas en `pyproject.toml`:

```bash
uv sync --extra dev
```

Con `venv` tradicional: `pip install -e .[dev]`.

### Ruff (lint + formato)

```bash
uv run ruff check .          # lint
uv run ruff format --check . # verifica formato sin modificar archivos
uv run ruff format .         # aplica formato
```

Config en `[tool.ruff]` (`pyproject.toml`). Los `.md` de la raíz quedan excluidos: Ruff ≥ 0.16 también formatea bloques de código Python embebidos en Markdown, y no queremos que toque este mismo README u otra documentación. `File(...)`/`Form(...)`/`Query(...)` como default de parámetro (patrón estándar de inyección de dependencias de FastAPI) está explícitamente permitido vía `[tool.ruff.lint.flake8-bugbear].extend-immutable-calls`.

### mypy (tipado estático)

```bash
uv run mypy
```

Config en `[tool.mypy]`. Dos notas relevantes si tocas esa sección:

- `python_version` sigue `requires-python` y el Dockerfile (hoy `3.11`), no la versión del intérprete local del `venv`.
- `explicit_package_bases = true` es necesario porque la mayoría de los paquetes bajo `app/` no tiene `__init__.py` (namespace packages implícitos) y hay varios módulos que comparten nombre de archivo en carpetas distintas.

### Bandit (seguridad estática)

```bash
uv run bandit -r app/
```

Excepciones aceptadas se documentan inline con `# nosec <regla>` y su justificación en un comentario aparte (no se usa `# nosec` a secas).

### pip-audit (vulnerabilidades de dependencias)

```bash
uv run pip-audit
```

Corre contra las versiones realmente resueltas en `uv.lock`. Si aparece algo nuevo, primero probar `uv lock --upgrade` (respeta los rangos ya declarados en `pyproject.toml`) antes de subir el límite superior de una dependencia.

### pytest + cobertura

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Hoy no hay tests (`tests/` no existe, ver `pendientes.md` P-07): el comando corre pero reporta "no tests collected". El pipeline de CI lo ejecuta con `continue-on-error` hasta que exista una suite real.

### Gitleaks y Trivy (sin instalación local)

No son paquetes Python; se corren vía sus imágenes Docker oficiales, sin instalar nada en el host:

```bash
# Secretos en el historial de git
docker run --rm -v "$PWD":/repo -w /repo zricethezav/gitleaks:latest detect --source /repo -v

# Vulnerabilidades en la imagen ya construida
docker build -t ai-rag-service-manager:local .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
  image --severity CRITICAL,HIGH ai-rag-service-manager:local
```

También están declarados como jobs del pipeline de CI (`.github/workflows/ci.yml`), usando las actions oficiales `gitleaks/gitleaks-action` y `aquasecurity/trivy-action`.

### CI/CD

Pipeline mínimo en [`.github/workflows/ci.yml`](./.github/workflows/ci.yml): Ruff, mypy, Bandit, pip-audit, pytest (no bloqueante hasta que exista una suite real), build de Docker + Trivy, y Gitleaks. El job de SonarQube existe pero está deshabilitado (`if: false`) hasta confirmar que el runner tiene red hacia el `sonar.host.url` interno definido en `sonar-project.properties`.

### Otros controles del estándar ya cubiertos en el código

- **Usuario no-root en Docker** y `.dockerignore`: ver sección Docker más abajo.
- **Correlation ID**: `CorrelationIdMiddleware` (`app/core/middleware.py`) lee `X-Correlation-ID` del request entrante (o genera uno) y lo devuelve en la respuesta; `CorrelationIdFilter` (`app/core/logging.py`) lo inyecta en cada línea de log de esa request.
- **Excepciones documentadas**: excepciones genéricas (`except Exception`) en fronteras de integración externa (Spring Config, Eureka, GCS) llevan `# noqa: BLE001` con la razón inline, en vez de silenciarse.

## Endpoints principales

- `GET /`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `GET /api/v1/rag-services`
- `POST /api/v1/rag-services`
- `GET /api/v1/rag-services/{service_id}`
- `PUT /api/v1/rag-services/{service_id}`
- `PATCH /api/v1/rag-services/{service_id}/status`
- `DELETE /api/v1/rag-services/{service_id}`
- `POST /api/v1/embedding/save_document_vecstore`
- `POST /api/v1/embedding/delete_index_vecstore`
- `POST /api/v1/embedding/list_documents`
- `POST /api/v1/embedding/get_embeddings_by_unique_code`
- `POST /api/v1/embedding/search_similar_documents`
- `POST /api/v1/embedding/rag_query`
- `POST /api/v1/storage/upload`
- `POST /api/v1/storage/chunk`
- `GET /api/v1/storage/get`
- `GET /api/v1/storage/getFileByte`
- `POST /api/v1/storage/public-upload`

Contrato completo de request/response de cada endpoint (incluyendo `storage`, que replica la superficie pública de un microservicio Java de storage): ver [`api.md`](./api.md).

Brechas conocidas, deuda técnica y su trazabilidad de resolución: ver [`pendientes.md`](./pendientes.md).

Plan de migración del microservicio Java (`edi-ai-proyectos-backend`) para que consuma `storage`/`embedding` de este servicio en vez de GCS local + `analysis-ai-service`, con el mapeo de campos exacto y las incompatibilidades de contrato detectadas: ver [`integracion-java-storage.md`](./integracion-java-storage.md).

## Docker

La imagen corre como usuario no-root (`appuser`, uid 1000) y aplica `apt-get upgrade` en el build para tomar parches de seguridad del SO disponibles al momento de construir (ver §26/§27 arriba y `pendientes.md` P-18 para el detalle de vulnerabilidades de imagen aún pendientes de resolver). El build usa `.dockerignore` para no copiar `.venv`, `.git`, secretos locales ni documentación interna al contexto.

El build también pre-descarga el modelo de embeddings por defecto (`sentence-transformers/all-MiniLM-L6-v2`) y fija `HF_HUB_OFFLINE=1` para el runtime, para que el contenedor arranque sin depender de red ni pagar el costo de descarga en el primer request. Si cambias `RAG_EMBEDDING_MODEL` a otro modelo sin reconstruir la imagen, el arranque va a intentar descargarlo igual — falla si no hay salida a internet, porque `HF_HUB_OFFLINE=1` bloquea el fallback online. Esto agrega ~1.6GB al `.venv` (torch CPU-only + sentence-transformers + pymilvus) — ver `pendientes.md` P-19 si el tamaño de imagen es una preocupación.

`appuser` se crea con `--no-create-home`, así que `HOME`, `UV_CACHE_DIR` y `HF_HOME` se fijan explícitamente dentro de `/app` (que sí queda con permisos de escritura para ese usuario); sin esto, `uv run` falla al no poder crear su cache en un `$HOME` inexistente.

Sin Vault (usa `.env`, `USE_VAULT_CONFIG=false` como en el default de `.env.example`):

```bash
docker build -t ai-rag-service-manager .
docker run --rm -p 8000:8000 --env-file .env ai-rag-service-manager
```

Con Vault:

```bash
docker build -t ai-rag-service-manager .
docker run --rm -p 8000:8000 --env-file .env \
	-e USE_VAULT_CONFIG=true \
	-e VAULT_ADDR=http://localhost:8200 \
	-e VAULT_TOKEN=root-token \
	ai-rag-service-manager
```

Nota: en `docker run` el mapeo `-p` no se ajusta automaticamente leyendo `.env`; si cambias `API_PORT`, ajusta tambien el `-p host:container`.

Para storage, define `GOOGLE_CREDS_JSON` en el `.env` o en la configuracion cargada desde Vault con el contenido completo del service account JSON en una sola variable.

Con Compose:

```bash
export SERVER_DEPLOYMENT=dev
export USE_VAULT_CONFIG=true
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root-token
docker compose up --build
```

Compose lee los secretos desde `../company-secrets/${SERVER_DEPLOYMENT}` relativos al proyecto. Con la estructura:

```text
PROYECTO/
├── ai-rag-service-manager/
└── company-secrets/
	└── dev/
		├── common.env
		├── storage.env
		└── ai-rag-service-manager.env
```

Si `SERVER_DEPLOYMENT` no esta definido, Compose usa `dev` por defecto.
