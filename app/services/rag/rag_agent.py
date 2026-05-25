"""Agent-oriented facade for RAG retrieval.

Este modulo envuelve ``RAGService`` con una interfaz mas cercana a un agente.
No administra HTTP ni almacenamiento; su trabajo es preparar consultas,
aplicar filtros logicos y devolver una respuesta orientada al consumo de un
componente conversacional o de orquestacion.
"""

from typing import Any

from app.core.config import get_settings
from app.infrastructure.vector_store.vector_store_manager import VectorStoreManager
from app.services.rag.rag_service import RAGService


class RAGAgent:
    """Facade de alto nivel para preguntas respondidas con contexto recuperado."""

    def __init__(
        self,
        collection_name: str,
        embedding_model: str,
        vector_store_manager: VectorStoreManager,
    ) -> None:
        self.name = "rag"
        self.description = (
            "Responsible for retrieving and analyzing relevant internal documentation "
            "to answer user queries accurately."
        )
        self._settings = get_settings()
        self.rag_service = RAGService(
            settings=self._settings,
            collection_name=collection_name,
            embedding_model=embedding_model,
            vector_store_manager=vector_store_manager,
        )

    def index_company_documents(
        self,
        documents: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        """Indexa documentos usando el servicio RAG subyacente."""
        return self.rag_service.index_documents(documents=documents, metadata=metadata, chunk=True)

    def retrieve_context(
        self,
        query: str,
        top_k: int,
        department: str | None = None,
    ) -> str:
        """Recupera contexto relevante con un filtro opcional de departamento."""
        filter_conditions = {"department": department} if department else None
        return self.rag_service.retrieve_context(query=query, top_k=top_k, filter_conditions=filter_conditions)

    def answer_with_context(
        self,
        question: str,
        top_k: int,
        department: str | None = None,
    ) -> dict[str, Any]:
        """Construye una respuesta basica con contexto y fuentes recuperadas.

        Hoy no invoca un LLM. Deja listo el contrato para integrar uno despues.
        """
        context = self.retrieve_context(query=question, top_k=top_k, department=department)
        system_prompt = (
            "You are a knowledgeable assistant with access to indexed internal documentation. "
            "Use the retrieved context to answer accurately."
        )
        return {
            "agent": self.name,
            "question": question,
            "context": context,
            "sources": self.rag_service.search(
                query=question,
                top_k=top_k,
                filter_conditions={"department": department} if department else None,
            ),
            "answer": "LLM integration pending. Retrieved context returned.",
            "system_prompt": system_prompt,
        }
