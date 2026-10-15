"""OCR adapter sobre Google Cloud Vision.

Migra al RAG la responsabilidad que hoy tiene ``edi-ai-analysis-ai``
(``ReadTextBase64._read_text_pdf_with_images`` / ``_read_text_with_ocr``):
``DOCUMENT_TEXT_DETECTION`` sobre PDF por lotes de paginas, con el mismo
separador ``*page-break*``. Reusa las credenciales de la service account que el
RAG ya tiene para storage (``GOOGLE_CREDS_JSON``); la cuenta necesita la API
Cloud Vision habilitada en su proyecto.

El cliente se crea de forma perezosa: sin OCR en uso no se toca Vision.
"""

import logging
from typing import Any

from app.infrastructure.clients.storage_config import StorageConfig

logger = logging.getLogger(__name__)

PAGE_BREAK = "\n*page-break*\n"
# Limite de la API de Vision: maximo 5 paginas por solicitud en batch_annotate_files.
_PAGES_PER_REQUEST = 5


class OcrUnavailableError(RuntimeError):
    """El OCR no esta habilitado o no hay credenciales para usarlo."""


class VisionOcr:
    """Extrae texto de PDF e imagenes via Google Cloud Vision."""

    def __init__(self, config: StorageConfig, enabled: bool = True) -> None:
        self._config = config
        self._enabled = enabled
        self._client: Any = None

    @property
    def enabled(self) -> bool:
        return self._enabled and self._config.has_credentials_info()

    def _get_client(self) -> Any:
        if not self.enabled:
            raise OcrUnavailableError("OCR deshabilitado o sin credenciales de Google")
        if self._client is None:
            from google.cloud import vision
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_info(
                self._config.credentials_info
            )
            self._client = vision.ImageAnnotatorClient(credentials=credentials)
        return self._client

    def ocr_pdf_pages(self, pdf_bytes: bytes, pages: list[int]) -> dict[int, str]:
        """OCR de paginas concretas (base 1) de un PDF. Devuelve ``{pagina: texto}``."""
        from google.cloud import vision

        client = self._get_client()
        input_config = {"mime_type": "application/pdf", "content": pdf_bytes}
        features = [{"type_": vision.Feature.Type.DOCUMENT_TEXT_DETECTION}]
        result: dict[int, str] = {}
        for start in range(0, len(pages), _PAGES_PER_REQUEST):
            batch = pages[start : start + _PAGES_PER_REQUEST]
            response = client.batch_annotate_files(
                requests=[{"input_config": input_config, "features": features, "pages": batch}]
            )
            for page_number, page_response in zip(batch, response.responses[0].responses):
                result[page_number] = page_response.full_text_annotation.text or ""
        logger.info("ocr vision: %s paginas procesadas", len(result))
        return result

    def ocr_image(self, image_bytes: bytes) -> str:
        """OCR de una imagen (png, jpg, ...)."""
        from google.cloud import vision

        client = self._get_client()
        response = client.document_text_detection(image=vision.Image(content=image_bytes))
        if response.error.message:
            raise RuntimeError(f"Vision OCR fallo: {response.error.message}")
        return response.full_text_annotation.text or ""
