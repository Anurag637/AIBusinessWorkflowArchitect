"""
Requirement Analysis API endpoint.
POST /api/v1/analyze-requirement
"""

from fastapi import APIRouter, HTTPException, status
from app.schemas.requirement import (
    AnalyzeRequirementRequest,
    AnalyzeRequirementResponse,
)
from app.agents.requirement_analyzer import analyze_requirement
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Requirements"])


@router.post(
    "/analyze-requirement",
    response_model=AnalyzeRequirementResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze natural language business requirement",
    description="Takes natural language text and returns structured business goal, actors, rules, and approval criteria.",
)
async def analyze_business_requirement(payload: AnalyzeRequirementRequest):
    try:
        analysis = analyze_requirement(
            requirement_text=payload.requirement_text,
            domain_hint=payload.domain_hint,
        )
        return AnalyzeRequirementResponse(
            status="success",
            analysis=analysis,
            warnings=[],
        )
    except Exception as e:
        logger.error(f"Error during requirement analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Requirement analysis failed: {str(e)}",
        )
