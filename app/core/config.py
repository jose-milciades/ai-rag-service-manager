import os
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.vault import get_vault_client, is_vault_configured


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
        # Fallback real cuando no hay Vault (ver get_settings() y
        # pendientes.md P-17): variables ya exportadas al proceso siguen
        # teniendo prioridad sobre el archivo, y este se ignora en silencio
        # si no existe -- no es un requisito, solo un fallback local.
        env_file=".env",
        env_file_encoding="utf-8",
    )

    debug: bool = Field(default=False, validation_alias=AliasChoices("DEBUG"))
    # EUREKA_APP_NAME es tambien el nombre general de la app (titulo FastAPI,
    # logs, path de Spring Config, respuesta de "/"), no solo lo que se
    # registra en Eureka -- por eso no existe un "eureka_app_name" aparte:
    # seria un duplicado exacto (mismo alias, mismo default). EurekaRegistrar
    # usa este mismo campo.
    app_name: str = Field(
        default="ai-rag-service-manager",
        validation_alias=AliasChoices("EUREKA_APP_NAME"),
    )
    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV"))
    # Excepcion Bandit B104 aceptada (ver pendientes.md P-18): el servicio
    # corre dentro de un contenedor Docker y debe aceptar conexiones desde
    # fuera de su namespace de red; 0.0.0.0 es el bind correcto en ese caso,
    # no una exposicion accidental.
    app_host: str = Field(
        default="0.0.0.0",  # nosec B104
        validation_alias=AliasChoices("APP_HOST", "API_HOST"),
    )
    app_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("APP_PORT", "API_PORT"),
    )
    app_log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("APP_LOG_LEVEL", "LOG_LEVEL"),
    )
    api_prefix: str = Field(
        default="/api/v1",
        validation_alias=AliasChoices("APP_API_PREFIX", "API_DEV_V1_CHAT_AGENT"),
    )
    cors_allowed_origins: str = Field(
        default="*",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS"),
    )
    readiness_critical_dependencies: str = Field(
        default="config_server,eureka",
        validation_alias=AliasChoices("READINESS_CRITICAL_DEPENDENCIES"),
    )

    spring_profiles_active: str = Field(
        default="default",
        validation_alias=AliasChoices("SPRING_PROFILES_ACTIVE"),
    )
    spring_cloud_config_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SPRING_CLOUD_CONFIG_URI"),
    )
    use_spring_cloud_config: bool = Field(
        default=False,
        validation_alias=AliasChoices("USE_SPRING_CLOUD_CONFIG"),
    )

    eureka_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("EUREKA_ENABLED"),
    )
    eureka_server_url: str = Field(
        default="http://localhost:8761/eureka/",
        validation_alias=AliasChoices(
            "EUREKA_SERVER_URL", "EUREKA_SERVER", "EUREKA_CLIENT_SERVICEURL_DEFAULTZONE"
        ),
    )
    eureka_instance_host: str = Field(
        default="ai-rag-service-manager",
        validation_alias=AliasChoices("EUREKA_INSTANCE_HOST"),
    )
    eureka_instance_ip: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("EUREKA_INSTANCE_IP", "INSTANCE_IP"),
    )
    eureka_register_max_retries: int = Field(
        default=3,
        validation_alias=AliasChoices("EUREKA_REGISTER_MAX_RETRIES", "REGISTER_MAX_RETRIES"),
    )
    eureka_register_retry_delay: int = Field(
        default=2,
        validation_alias=AliasChoices("EUREKA_REGISTER_RETRY_DELAY", "REGISTER_RETRY_DELAY"),
    )

    google_creds_json: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_CREDS_JSON"),
    )
    storage_project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_PROJECT_ID", "STORAGE_PROYECT_ID"),
    )
    storage_default_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_DEFAULT_BUCKET_NAME"),
    )
    storage_public_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_PUBLIC_BUCKET_NAME"),
    )
    storage_chunk_upload_temp_dir: str = Field(
        default=".runtime/uploads",
        validation_alias=AliasChoices("STORAGE_CHUNK_UPLOAD_TEMP_DIR"),
    )

    vector_db_type: str = Field(default="memory", validation_alias=AliasChoices("VECTOR_DB_TYPE"))
    milvus_host: str = Field(default="localhost", validation_alias=AliasChoices("MILVUS_HOST"))
    milvus_port: int = Field(default=19530, validation_alias=AliasChoices("MILVUS_PORT"))
    milvus_user: str | None = Field(default=None, validation_alias=AliasChoices("MILVUS_USER"))
    milvus_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MILVUS_PASSWORD"),
    )
    milvus_db_name: str = Field(default="default", validation_alias=AliasChoices("MILVUS_DB_NAME"))
    milvus_alias: str = Field(default="default", validation_alias=AliasChoices("MILVUS_ALIAS"))
    milvus_metric_type: str = Field(
        default="COSINE",
        validation_alias=AliasChoices("MILVUS_METRIC_TYPE"),
    )
    milvus_index_type: str = Field(
        default="IVF_FLAT",
        validation_alias=AliasChoices("MILVUS_INDEX_TYPE"),
    )
    milvus_index_nlist: int = Field(
        default=128,
        validation_alias=AliasChoices("MILVUS_INDEX_NLIST"),
    )
    milvus_search_nprobe: int = Field(
        default=10,
        validation_alias=AliasChoices("MILVUS_SEARCH_NPROBE"),
    )

    # Ambiente logico (analogo al "index" de Pinecone en edi-ai-analysis-ai,
    # ver pendientes.md P-33): se usa como nombre de PARTICION Milvus dentro
    # de la coleccion de cada proyecto (coleccion = proyecto solo, sin
    # concatenar -- ej. coleccion "project_127", particion "edi_dev"). Asi
    # varios ambientes que comparten una misma instancia Milvus quedan
    # separados y administrables por separado (browsear/borrar un ambiente
    # sin tocar los demas), sin ensuciar el nombre de la coleccion.
    # Reemplaza a RAG_COLLECTION_NAME_PREFIX (antes opcional/vacio por
    # defecto, prefijo simple en el nombre): ahora es obligatorio-por-default
    # y con valores fijos.
    rag_environment: str = Field(
        default="edi-local",
        validation_alias=AliasChoices("RAG_ENVIRONMENT"),
    )
    rag_default_collection_name: str = Field(
        default="default_rag_collection",
        validation_alias=AliasChoices("RAG_DEFAULT_COLLECTION_NAME"),
    )
    # Decision de negocio (ver pendientes.md P-19): solo OpenAI, sin backend
    # local. Se mantiene como campo validado (en vez de hardcodear el string)
    # para que un typo en .env/Vault falle fuerte al arrancar en vez de
    # ignorarse en silencio (mismo criterio que RAG_ENVIRONMENT).
    rag_embedding_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("RAG_EMBEDDING_PROVIDER"),
    )
    rag_embedding_model: str = Field(
        default="text-embedding-3-large",
        validation_alias=AliasChoices("RAG_EMBEDDING_MODEL"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY"),
    )
    rag_openai_embedding_dimensions: int | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_OPENAI_EMBEDDING_DIMENSIONS"),
    )
    rag_chunk_size: int = Field(default=1000, validation_alias=AliasChoices("RAG_CHUNK_SIZE"))
    rag_chunk_overlap: int = Field(
        default=200,
        validation_alias=AliasChoices("RAG_CHUNK_OVERLAP"),
    )
    rag_default_top_k: int = Field(
        default=5,
        validation_alias=AliasChoices("RAG_DEFAULT_TOP_K"),
    )
    rag_default_list_limit: int = Field(
        default=100,
        validation_alias=AliasChoices("RAG_DEFAULT_LIST_LIMIT"),
    )
    rag_max_embeddings_per_document: int = Field(
        default=1000,
        validation_alias=AliasChoices("RAG_MAX_EMBEDDINGS_PER_DOCUMENT"),
    )
    # "Adjacent chunks" (ver pendientes.md P-37): expansion de contexto
    # opcional en search_similar_documents (expand_context=true).
    rag_adjacent_window_chars: int = Field(
        default=500,
        validation_alias=AliasChoices("RAG_ADJACENT_WINDOW_CHARS"),
    )
    rag_adjacent_chunk_count: int = Field(
        default=8,
        validation_alias=AliasChoices("RAG_ADJACENT_CHUNK_COUNT"),
    )
    rag_unique_code_list_limit: int = Field(
        default=10000,
        validation_alias=AliasChoices("RAG_UNIQUE_CODE_LIST_LIMIT"),
    )

    @field_validator("rag_openai_embedding_dimensions", mode="before")
    @classmethod
    def _blank_optional_int_as_none(cls, value: object) -> object:
        """Fuentes de config que no pueden omitir una key (ej. Vault, a
        diferencia de comentar una linea en `.env`) mandan `""` para "sin
        valor" en vez de no mandar la key -- sin esto, pydantic intenta
        parsear `""` como int y falla. Solo aplica a este campo porque es el
        unico `int | None` de Settings."""
        return None if value == "" else value

    @field_validator("rag_environment")
    @classmethod
    def _validate_rag_environment(cls, value: str) -> str:
        """RAG_ENVIRONMENT solo acepta estos 4 valores (ver pendientes.md
        P-33): un typo aca crearia silenciosamente una coleccion Milvus bajo
        un ambiente inexistente, en vez de fallar fuerte al arrancar -- mismo
        criterio que ``VaultClient`` (falla fuerte y explicito, no cae en
        silencio a un default distinto al pedido)."""
        allowed = {"edi-local", "edi-dev", "edi-stage", "edi-prod"}
        if value not in allowed:
            raise ValueError(
                f"RAG_ENVIRONMENT invalido: {value!r}. Valores permitidos: {sorted(allowed)}"
            )
        return value

    @field_validator("rag_embedding_provider")
    @classmethod
    def _validate_rag_embedding_provider(cls, value: str) -> str:
        """Decision de negocio (ver pendientes.md P-19): solo OpenAI. El
        backend local (`sentence-transformers`/`torch`) fue removido del
        todo -- un valor distinto a "openai" aca (ej. "local" por config
        vieja sin actualizar) debe fallar fuerte al arrancar, no degradar en
        silencio a un backend que ya no existe."""
        if value != "openai":
            raise ValueError(
                f"RAG_EMBEDDING_PROVIDER invalido: {value!r}. Unico valor soportado: 'openai'"
            )
        return value


_DEFAULT_VAULT_CONFIG_PATHS = "common,ai-rag-service-manager,storage,llm_apis"


def _vault_config_paths() -> list[str]:
    """Paths KV v2 a mezclar desde Vault, mismo patron que
    ``VAULT_CONFIG_PATHS`` en edi-ai-scheduled-worker/edi-ai-operator:
    override explicito por env var, con el default historico de este
    servicio si no se define."""
    raw = os.getenv("VAULT_CONFIG_PATHS", _DEFAULT_VAULT_CONFIG_PATHS)
    return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Construye ``Settings`` usando Vault solo si ``USE_VAULT_CONFIG=true``.

    Mismo patron que ``USE_SPRING_CLOUD_CONFIG``/``EUREKA_ENABLED``: una
    variable explicita decide, no se infiere nada por presencia de otras
    variables. Con ``USE_VAULT_CONFIG=true`` pero sin
    ``VAULT_ADDR``/``VAULT_TOKEN``, falla fuerte via ``VaultClient``. Con
    ``USE_VAULT_CONFIG`` en false/ausente (default), la config sale de
    variables ya exportadas al proceso y, como fallback, de un archivo
    ``.env`` si existe (ver ``Settings.model_config``).
    """
    if is_vault_configured():
        vault = get_vault_client()
        config = vault.load_configs(_vault_config_paths())
        return Settings(**config)
    return Settings()
