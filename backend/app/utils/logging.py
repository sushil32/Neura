"""Structured logging configuration."""
import logging
import sys
from typing import Any, Dict

import structlog

from app.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.debug:
        # Development: colored console output
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # Production: JSON output
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )
    
    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )


def get_request_context(request: Any) -> Dict[str, Any]:
    """Extract logging context from a request."""
    return {
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
    }

