from functools import lru_cache

from pydantic import AliasChoices, Field
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

    rag_collection_name_prefix: str = Field(
        default="",
        validation_alias=AliasChoices("RAG_COLLECTION_NAME_PREFIX"),
    )
    rag_default_collection_name: str = Field(
        default="default_rag_collection",
        validation_alias=AliasChoices("RAG_DEFAULT_COLLECTION_NAME"),
    )
    rag_agent_collection_name: str = Field(
        default="company_knowledge_base",
        validation_alias=AliasChoices("RAG_AGENT_COLLECTION_NAME"),
    )
    rag_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias=AliasChoices("RAG_EMBEDDING_MODEL"),
    )
    rag_embedding_device: str = Field(
        default="cpu",
        validation_alias=AliasChoices("RAG_EMBEDDING_DEVICE"),
    )
    rag_normalize_embeddings: bool = Field(
        default=True,
        validation_alias=AliasChoices("RAG_NORMALIZE_EMBEDDINGS"),
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
    rag_unique_code_list_limit: int = Field(
        default=10000,
        validation_alias=AliasChoices("RAG_UNIQUE_CODE_LIST_LIMIT"),
    )


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
        config = vault.load_configs(["common", "ai-rag-service-manager", "storage"])
        return Settings(**config)
    return Settings()
