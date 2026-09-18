"""
Knowledge / RAG API endpoints.
- POST /api/v1/knowledge/search: Semantic search across company policy docs
- POST /api/v1/knowledge/index: Trigger document re-indexing
- GET /api/v1/knowledge/documents: List all indexed documents
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.rag import get_rag_service, SearchResult

router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge"])


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Search query string")
    top_k: int = Field(default=3, ge=1, le=20)
    category: Optional[str] = None
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class KnowledgeSearchResponse(BaseModel):
    status: str = "success"
    query: str
    total_results: int
    results: List[SearchResult]


class KnowledgeIndexResponse(BaseModel):
    status: str = "success"
    indexed_chunks: int
    message: str


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic search over company policies",
)
async def search_knowledge(payload: KnowledgeSearchRequest):
    service = get_rag_service()
    results = service.search(
        query=payload.query,
        top_k=payload.top_k,
        category=payload.category,
        score_threshold=payload.score_threshold,
    )
    return KnowledgeSearchResponse(
        status="success",
        query=payload.query,
        total_results=len(results),
        results=results,
    )


@router.post(
    "/index",
    response_model=KnowledgeIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-index company policies",
)
async def trigger_reindex():
    service = get_rag_service()
    knowledge_path = Path(__file__).resolve().parents[3] / "knowledge" / "policies"
    count = service.index_directory(knowledge_path)
    return KnowledgeIndexResponse(
        status="success",
        indexed_chunks=count,
        message=f"Successfully indexed {count} chunks from {knowledge_path.name}",
    )
