from functools import lru_cache

from app.core.config import get_settings
from app.domain.repositories.rag_service_repository import RagServiceRepository
from app.infrastructure.clients.storage_client import StorageClient
from app.infrastructure.clients.storage_config import StorageConfig
from app.infrastructure.embeddings.embedding_provider import EmbeddingProvider
from app.infrastructure.repositories.in_memory_rag_service_repository import (
    InMemoryRagServiceRepository,
)
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager
from app.services.embedding.document_embedding_service import DocumentEmbeddingService
from app.services.rag.rag_agent import RAGAgent
from app.services.rag_service import RagServiceManager
from app.services.storage_service import StorageService


@lru_cache
def get_rag_service_repository() -> RagServiceRepository:
    return InMemoryRagServiceRepository()


@lru_cache
def get_rag_service_manager() -> RagServiceManager:
    return RagServiceManager(repository=get_rag_service_repository())


@lru_cache
def get_vector_store_manager() -> VectorStoreManager:
    return VectorStoreManager(settings=get_settings())


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """Instancia unica: cargar el modelo de embeddings es costoso, no se
    debe repetir por request ni por coleccion."""
    return EmbeddingProvider(settings=get_settings())


@lru_cache
def get_storage_config() -> StorageConfig:
    return StorageConfig(settings=get_settings())


@lru_cache
def get_storage_client() -> StorageClient:
    return StorageClient(config=get_storage_config())


@lru_cache
def get_document_embedding_service() -> DocumentEmbeddingService:
    return DocumentEmbeddingService(
        settings=get_settings(),
        storage_client=get_storage_client(),
        vector_store_manager=get_vector_store_manager(),
        embedding_provider=get_embedding_provider(),
    )


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService(
        config=get_storage_config(),
        storage_client=get_storage_client(),
        document_embedding_service=get_document_embedding_service(),
        settings=get_settings(),
    )


@lru_cache
def get_rag_agent() -> RAGAgent:
    settings = get_settings()
    return RAGAgent(
        collection_name=settings.rag_agent_collection_name,
        vector_store_manager=get_vector_store_manager(),
        embedding_provider=get_embedding_provider(),
    )
