"""
Autonomous Multi-Agent Dynamic Orchestrator API.
Exposes endpoints for natural language goal execution, live thought tracing,
and Human-in-the-Loop approval workflows.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
import logging

from app.schemas.orchestrator import (
    OrchestrateRequest,
    OrchestrateResponse,
    ResumeSessionRequest,
    ResumeSessionResponse,
    OrchestrationSession,
)
from app.agents.manager_agent import get_manager_agent, ACTIVE_SESSIONS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Autonomous Orchestrator"])


@router.post(
    "/orchestrate",
    response_model=OrchestrateResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute goal via Dynamic Manager-Specialist Orchestration",
    description="Manager Agent autonomously reasons, delegates sub-tasks to specialists, and iterates until goal completion or approval pause.",
)
async def orchestrate_goal(payload: OrchestrateRequest):
    try:
        manager = get_manager_agent()
        session = manager.orchestrate(
            goal=payload.goal,
            initial_context=payload.initial_context,
            domain_hint=payload.domain_hint,
            max_steps=payload.max_steps or 8,
        )
        return OrchestrateResponse(status="success", session=session)
    except Exception as e:
        logger.error(f"Error during agent orchestration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent orchestration failed: {str(e)}",
        )


@router.post(
    "/orchestrate/resume",
    response_model=ResumeSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume paused workflow with Human Reviewer Decision",
    description="Submits approval or rejection to an awaiting-approval session and resumes autonomous execution.",
)
async def resume_session(payload: ResumeSessionRequest):
    try:
        manager = get_manager_agent()
        session = manager.resume(
            session_id=payload.session_id,
            approval_decision=payload.approval_decision,
            approver_comments=payload.approver_comments,
            reviewer_role=payload.reviewer_role or "manager",
        )
        return ResumeSessionResponse(status="success", session=session)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error resuming session {payload.session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume session: {str(e)}",
        )


@router.get(
    "/orchestrate/sessions",
    response_model=List[Dict[str, Any]],
    summary="List all active orchestration sessions",
)
async def list_orchestration_sessions():
    return [
        {
            "session_id": s.session_id,
            "goal": s.goal,
            "status": s.status,
            "steps_count": len(s.steps),
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in ACTIVE_SESSIONS.values()
    ]


@router.get(
    "/orchestrate/{session_id}",
    response_model=OrchestrationSession,
    summary="Retrieve session state and reasoning trace",
)
async def get_orchestration_session(session_id: str):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session
