import logging
import os
from logging.config import dictConfig

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    os.makedirs("logs", exist_ok=True)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": "colorlog.ColoredFormatter",
                    "format": "%(log_color)s%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
                    "log_colors": {
                        "DEBUG": "cyan",
                        "INFO": "green",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "bold_red",
                    },
                },
                "file": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": settings.app_log_level.upper(),
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "file",
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
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
