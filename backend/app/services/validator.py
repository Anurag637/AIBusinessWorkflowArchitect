"""
Comprehensive Multi-Stage Workflow Validator.
Combines fast deterministic rule enforcement (14 rules) with semantic intent verification.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

from app.schemas.workflow import WorkflowDefinition, StepType
from app.schemas.validator import DeterministicValidator, ValidationIssue, ValidationResult
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


class ComprehensiveValidationReport(BaseModel):
    is_valid: bool
    deterministic_passed: bool
    semantic_passed: bool
    fidelity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ComprehensiveValidator:
    """Multi-stage validator combining deterministic security gates and semantic alignment."""

    def __init__(self):
        self.deterministic_validator = DeterministicValidator()

    def validate(
        self,
        workflow: WorkflowDefinition,
        requirement_text: Optional[str] = None,
    ) -> ComprehensiveValidationReport:
        # Stage 1: Deterministic check
        det_result: ValidationResult = self.deterministic_validator.validate(workflow)

        errors = list(det_result.errors)
        warnings = list(det_result.warnings)
        recommendations: List[str] = []

        if not det_result.is_valid:
            # Short-circuit if deterministic security rules failed
            return ComprehensiveValidationReport(
                is_valid=False,
                deterministic_passed=False,
                semantic_passed=False,
                fidelity_score=0.0,
                errors=errors,
                warnings=warnings,
                recommendations=["Fix all deterministic errors before semantic evaluation."],
            )

        # Stage 2: Semantic Intent Verification
        semantic_passed = True
        fidelity_score = 1.0

        if requirement_text:
            lower_req = requirement_text.lower()
            step_types = [s.type for s in workflow.steps]

            # Rule check: approval in text requires APPROVAL step
            if any(w in lower_req for w in ["approval", "approve", "manager approval"]):
                if StepType.APPROVAL not in step_types:
                    semantic_passed = False
                    fidelity_score -= 0.3
                    warnings.append(
                        ValidationIssue(
                            rule_number=101,
                            rule_name="Semantic Approval Omission",
                            severity="WARNING",
                            message="Requirement specifies manager approval, but no APPROVAL step was found in workflow.",
                        )
                    )
                    recommendations.append("Add an APPROVAL step for requests exceeding threshold.")

            # Rule check: policy check requires RAG step
            if any(w in lower_req for w in ["policy", "guidelines", "compliance"]):
                if StepType.RAG not in step_types:
                    fidelity_score -= 0.2
                    warnings.append(
                        ValidationIssue(
                            rule_number=102,
                            rule_name="Semantic Policy Check Omission",
                            severity="WARNING",
                            message="Requirement references company policy, but no RAG knowledge retrieval step exists.",
                        )
                    )
                    recommendations.append("Integrate a RAG search step to verify policy guidelines.")

            # Rule check: notification in text requires NOTIFICATION step
            if any(w in lower_req for w in ["notify", "notification", "email", "it team", "it can process"]):
                if StepType.NOTIFICATION not in step_types:
                    fidelity_score -= 0.15
                    recommendations.append("Consider adding a NOTIFICATION step to alert the fulfilling team.")

        fidelity_score = max(0.0, min(1.0, fidelity_score))

        return ComprehensiveValidationReport(
            is_valid=len(errors) == 0,
            deterministic_passed=True,
            semantic_passed=semantic_passed,
            fidelity_score=round(fidelity_score, 2),
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
        )


_comprehensive_validator: Optional[ComprehensiveValidator] = None


def get_validator() -> ComprehensiveValidator:
    global _comprehensive_validator
    if _comprehensive_validator is None:
        _comprehensive_validator = ComprehensiveValidator()
    return _comprehensive_validator
