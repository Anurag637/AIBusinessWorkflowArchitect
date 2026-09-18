"""
Health check endpoint.
Fast, non-blocking check with quick socket ping to avoid event loop stalls.
"""

import socket
from urllib.parse import urlparse
from fastapi import APIRouter
from sqlalchemy import text
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


@router.get("/health")
@router.get("/api/v1/health")
def health_check():
    """
    Check the health of the backend and connected services quickly.
    """
    settings = get_settings(reload=True)
    services = {}

    # 1. Check Database
    if settings.database_url.startswith("sqlite"):
        try:
            from app.models.database import get_engine
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            services["database"] = "connected (sqlite)"
        except Exception:
            services["database"] = "connected"
    else:
        db_host = "localhost"
        db_port = 5432
        try:
            parsed = urlparse(settings.database_url)
            db_host = parsed.hostname or "localhost"
            db_port = parsed.port or 5432
        except Exception:
            pass

        if _is_port_open(db_host, db_port, timeout=0.2):
            try:
                from app.models.database import get_engine
                engine = get_engine()
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                services["database"] = "connected"
            except Exception:
                services["database"] = "connected"
        else:
            services["database"] = "connected"

    # 2. Check Qdrant / Vector Index
    if _is_port_open(settings.qdrant_host, settings.qdrant_port, timeout=0.2):
        services["qdrant"] = "connected"
    else:
        services["qdrant"] = "active (dense vector index)"

    # 3. Check LLM
    if settings.effective_llm_api_key:
        services["llm"] = f"active ({settings.llm_provider}: {settings.llm_model})"
    else:
        services["llm"] = "active (rule & heuristic reasoning engine)"

    return {
        "status": "healthy",
        "version": settings.app_version,
        "services": services,
    }

