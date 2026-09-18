"""
Process Decomposer API endpoint.
POST /api/v1/decompose-process
"""

from fastapi import APIRouter, HTTPException, status
from app.schemas.process import (
    DecomposeProcessRequest,
    DecomposeProcessResponse,
)
from app.agents.process_decomposer import decompose_process
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Process"])


@router.post(
    "/decompose-process",
    response_model=DecomposeProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Decompose requirement analysis into a multi-stage process plan",
    description="Takes requirement analysis and returns structured stages, planned steps, dependencies, and tool requirements.",
)
async def decompose_business_process(payload: DecomposeProcessRequest):
    try:
        plan = decompose_process(
            analysis=payload.analysis,
            max_stages=payload.max_stages or 6,
        )
        return DecomposeProcessResponse(
            status="success",
            plan=plan,
            warnings=[],
        )
    except Exception as e:
        logger.error(f"Error during process decomposition: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Process decomposition failed: {str(e)}",
        )
