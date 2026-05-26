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
│   │   ├── repositories/
│   │   │   └── in_memory_rag_service_repository.py
│   │   └── vector_store/
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
- `RAGService`: servicio central de chunking, embedding determinista e indexación/retrieval.
- `RAGAgent`: facade orientado a consultas sobre una colección de conocimiento.

### Infraestructura

- `InMemoryRagServiceRepository`: persistencia temporal de definiciones RAG.
- `VectorStoreManager`: facade para el backend vectorial configurado.
- `StorageClient`: descarga archivos desde URL o GCS.
- `ConfigServerClient`: consulta Spring Config Server solo durante el startup.
- `EurekaRegistrar`: registra y detiene el servicio en Eureka como parte del ciclo de vida.

## Alcance actual

Incluido en esta versión:

- FastAPI + Uvicorn;
- configuración con `pydantic-settings`;
- readiness con estado de Config Server y Eureka;
- logging centralizado;
- CRUD de `rag-services`;
- embeddings y retrieval básicos;
- Docker listo para ejecución local.

Exclusiones intencionales:

- ORM / SQLAlchemy;
- Alembic;
- autenticación JWT/OAuth2;
- OpenTelemetry;
- colas como Kafka o RabbitMQ;
- integración real con Milvus; actualmente el adapter activo es en memoria.

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
- `VECTOR_DB_TYPE` hoy debe considerarse preparado para evolución, pero el backend efectivo actual sigue siendo en memoria.

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
	│   ├── ai-rag-service-manager.env
	│   └── edward-creds.json
	├── qa/
	└── prod/
```

En `dev`, por ejemplo, el script intentara leer:

- `../company-secrets/dev/common.env`
- `../company-secrets/dev/storage.env`
- `../company-secrets/dev/ai-rag-service-manager.env`
- `../company-secrets/dev/edward-creds.json`

Arranque local por defecto:

```bash
chmod +x run-local.sh
./run-local.sh
```

El script hace esto:

- carga `common.env`, `storage.env` y `ai-rag-service-manager.env` desde `../company-secrets/${SERVER_DEPLOYMENT:-dev}`;
- exporta las variables al proceso antes de arrancar el microservicio;
- si existe `edward-creds.json` y no definiste `GOOGLE_APPLICATION_CREDENTIALS`, lo configura automaticamente;
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

## Docker

```bash
docker build -t ai-rag-service-manager .
docker run --rm -p 8000:8000 --env-file .env \
	-v "$(pwd)/edward-creds.json:/app/edward-creds.json:ro" \
	ai-rag-service-manager
```

Nota: en `docker run` el mapeo `-p` no se ajusta automaticamente leyendo `.env`; si cambias `API_PORT`, ajusta tambien el `-p host:container`.

Con Compose:

```bash
export SERVER_DEPLOYMENT=dev
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
		├── ai-rag-service-manager.env
		└── edward-creds.json
```

Si `SERVER_DEPLOYMENT` no esta definido, Compose usa `dev` por defecto.
