"""
Workflow API endpoints.
- POST /api/v1/generate-workflow: Generates a WorkflowDefinition from analysis and process plan
- POST /api/v1/validate-workflow: Validates any WorkflowDefinition using DeterministicValidator
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.schemas.requirement import RequirementAnalysis
from app.schemas.process import ProcessPlan
from app.schemas.workflow import WorkflowDefinition
from app.schemas.validator import DeterministicValidator, ValidationResult
from app.agents.workflow_architect import generate_workflow
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Workflows"])


class GenerateWorkflowRequest(BaseModel):
    analysis: RequirementAnalysis
    process_plan: ProcessPlan
    name: Optional[str] = None


class GenerateWorkflowResponse(BaseModel):
    status: str = "success"
    workflow: WorkflowDefinition
    validation_result: ValidationResult


class ValidateWorkflowRequest(BaseModel):
    workflow: WorkflowDefinition


class ValidateWorkflowResponse(BaseModel):
    status: str = "success"
    validation_result: ValidationResult


@router.post(
    "/generate-workflow",
    response_model=GenerateWorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize a valid WorkflowDefinition",
    description="Transforms RequirementAnalysis and ProcessPlan into an executable WorkflowDefinition.",
)
async def generate_workflow_endpoint(payload: GenerateWorkflowRequest):
    try:
        wf = generate_workflow(
            analysis=payload.analysis,
            process_plan=payload.process_plan,
        )
        if payload.name:
            wf.name = payload.name

        validator = DeterministicValidator()
        val_result = validator.validate(wf)

        return GenerateWorkflowResponse(
            status="success",
            workflow=wf,
            validation_result=val_result,
        )
    except Exception as e:
        logger.error(f"Error during workflow generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow generation failed: {str(e)}",
        )


from app.services.validator import get_validator, ComprehensiveValidationReport


class ComprehensiveValidateRequest(BaseModel):
    workflow: WorkflowDefinition
    requirement_text: Optional[str] = None


class ComprehensiveValidateResponse(BaseModel):
    status: str = "success"
    report: ComprehensiveValidationReport


@router.post(
    "/validate-workflow",
    response_model=ValidateWorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate workflow definition against 14 rules",
    description="Runs DeterministicValidator against the given workflow definition.",
)
async def validate_workflow_endpoint(payload: ValidateWorkflowRequest):
    validator = DeterministicValidator()
    val_result = validator.validate(payload.workflow)
    return ValidateWorkflowResponse(
        status="success",
        validation_result=val_result,
    )


from app.services.simulation import SimulationEngine, SimulationResult


class SimulateWorkflowRequest(BaseModel):
    workflow: WorkflowDefinition
    initial_inputs: Optional[Dict[str, Any]] = None


class SimulateWorkflowResponse(BaseModel):
    status: str = "success"
    simulation: SimulationResult


@router.post(
    "/comprehensive-validate",
    response_model=ComprehensiveValidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Multi-stage deterministic + semantic validation",
    description="Evaluates deterministic rules and semantic fidelity against business requirements.",
)
async def comprehensive_validate_endpoint(payload: ComprehensiveValidateRequest):
    validator = get_validator()
    report = validator.validate(payload.workflow, requirement_text=payload.requirement_text)
    return ComprehensiveValidateResponse(
        status="success",
        report=report,
    )


@router.post(
    "/simulate",
    response_model=SimulateWorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Dry-run simulate workflow execution",
    description="Simulates step-by-step execution with mock tools and traces outputs without side effects.",
)
async def simulate_workflow_endpoint(payload: SimulateWorkflowRequest):
    engine = SimulationEngine()
    result = engine.simulate(payload.workflow, initial_inputs=payload.initial_inputs)
    return SimulateWorkflowResponse(
        status="success",
        simulation=result,
    )
