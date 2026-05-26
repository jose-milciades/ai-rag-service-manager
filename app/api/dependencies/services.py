from functools import lru_cache

from app.core.config import get_settings
from app.domain.repositories.rag_service_repository import RagServiceRepository
from app.infrastructure.clients.storage_client import StorageClient
from app.infrastructure.clients.storage_config import StorageConfig
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
def get_storage_config() -> StorageConfig:
    return StorageConfig(settings=get_settings())


@lru_cache
def get_storage_client() -> StorageClient:
    return StorageClient(config=get_storage_config())


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService(config=get_storage_config(), storage_client=get_storage_client())


@lru_cache
def get_document_embedding_service() -> DocumentEmbeddingService:
    return DocumentEmbeddingService(
        settings=get_settings(),
        storage_client=get_storage_client(),
        vector_store_manager=get_vector_store_manager(),
    )


@lru_cache
def get_rag_agent() -> RAGAgent:
    settings = get_settings()
    return RAGAgent(
        collection_name=settings.rag_agent_collection_name,
        embedding_model=settings.rag_embedding_model,
        vector_store_manager=get_vector_store_manager(),
    )
