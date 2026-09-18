"""
FastAPI application entry point.
Configured with Hugging Face LLM integration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import AppError, app_error_handler, generic_error_handler
from app.api.health import router as health_router
from app.api.analyze import router as analyze_router
from app.api.process import router as process_router
from app.api.workflows import router as workflows_router
from app.api.knowledge import router as knowledge_router
from app.api.approvals import router as approvals_router
from app.api.executions import router as executions_router
from app.api.audit import router as audit_router
from app.api.orchestrate import router as orchestrate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown."""
    logger = get_logger(__name__)
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"LLM Provider: {settings.llm_provider} / Model: {settings.llm_model}")
    logger.info(f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")
    logger.info(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    try:
        from app.services.rag import get_rag_service

        knowledge_candidates = (
            Path("/knowledge/policies"),
            Path(__file__).resolve().parents[2] / "knowledge" / "policies",
        )
        knowledge_path = next((path for path in knowledge_candidates if path.exists()), None)
        if knowledge_path:
            indexed_chunks = get_rag_service().index_directory(knowledge_path)
            logger.info("Knowledge base ready: %s chunks indexed from %s", indexed_chunks, knowledge_path)
        else:
            logger.warning("Knowledge base directory was not found; semantic search will be empty until indexed.")
    except Exception:
        logger.exception("Knowledge base initialization failed")
    yield
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Setup logging first
    setup_logging()

    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="An agentic AI system that converts natural-language business requirements into validated, simulated, and executable business workflows.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Error handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # Routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(analyze_router)
    app.include_router(process_router)
    app.include_router(workflows_router)
    app.include_router(knowledge_router)
    app.include_router(approvals_router)
    app.include_router(executions_router)
    app.include_router(audit_router)
    app.include_router(orchestrate_router)
    # app.include_router(process_router, prefix="/api/v1", tags=["Process"])
    # app.include_router(workflows_router, prefix="/api/v1", tags=["Workflows"])
    # app.include_router(knowledge_router, prefix="/api/v1", tags=["Knowledge"])
    # app.include_router(executions_router, prefix="/api/v1", tags=["Executions"])
    # app.include_router(approvals_router, prefix="/api/v1", tags=["Approvals"])
    # app.include_router(audit_router, prefix="/api/v1", tags=["Audit"])

    return app


# Create the app instance
app = create_app()
