import logging
import os
from contextvars import ContextVar
from logging.config import dictConfig

from app.core.config import get_settings

# Correlation id activo para la request en curso (ver CorrelationIdMiddleware
# en app.main). "-" fuera de una request (p.ej. logs de startup/shutdown).
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationIdFilter(logging.Filter):
    """Inyecta el correlation id activo en cada log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    os.makedirs("logs", exist_ok=True)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "correlation_id": {
                    "()": CorrelationIdFilter,
                },
            },
            "formatters": {
                "default": {
                    "()": "colorlog.ColoredFormatter",
                    "format": "%(log_color)s%(asctime)s | %(name)-25s | %(levelname)-8s | [%(correlation_id)s] | %(message)s",
                    "log_colors": {
                        "DEBUG": "cyan",
                        "INFO": "green",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "bold_red",
                    },
                },
                "file": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s [%(correlation_id)s]: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["correlation_id"],
                    "level": settings.app_log_level.upper(),
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "file",
                    "filters": ["correlation_id"],
                    "filename": "logs/app.log",
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                    "level": settings.app_log_level.upper(),
                },
            },
            "root": {
                "level": settings.app_log_level.upper(),
                "handlers": ["console", "file"],
            },
            "loggers": {
                "uvicorn": {
                    "level": settings.app_log_level.upper(),
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": settings.app_log_level.upper(),
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                # Loggers HTTP de las libs cliente (GCS, config server, OpenAI,
                # Milvus). Se fijan en DEBUG independientemente del nivel
                # general de la app para poder ver el request/response
                # completo (incluye status code, p.ej. 401) sin necesitar
                # APP_LOG_LEVEL=DEBUG global, que tambien vuelve verboso el
                # resto de la app.
                "httpx": {
                    "level": "DEBUG",
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "httpcore": {
                    "level": "DEBUG",
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "urllib3": {
                    "level": "DEBUG",
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "google.auth.transport.requests": {
                    "level": "DEBUG",
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "openai": {
                    "level": "DEBUG",
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
