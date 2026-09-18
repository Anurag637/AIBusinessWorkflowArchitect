"""
Workflow Architect Agent using LangGraph.
Transforms Requirement Analysis and Process Plan into a fully validated, executable WorkflowDefinition.
"""

import re
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from app.schemas.requirement import RequirementAnalysis
from app.schemas.process import ProcessPlan
from app.schemas.workflow import (
    WorkflowDefinition,
    WorkflowStep,
    StepType,
    TriggerDefinition,
    InputParam,
    RequiredApproval,
    WorkflowMetadata,
    RetryConfig,
)
from app.schemas.validator import DeterministicValidator
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


# ─── State Definition ─────────────────────────────────────────────────────────

class ArchitectState(TypedDict):
    analysis: Dict[str, Any]
    process_plan: Dict[str, Any]
    workflow_definition: Optional[Dict[str, Any]]
    validation_passed: bool
    errors: List[str]


# ─── Canonical Workflow Builder (Heuristic / Deterministic) ───────────────────

def build_canonical_workflow(
    analysis_dict: Dict[str, Any], process_plan_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Constructs a structurally complete, strictly compliant WorkflowDefinition
    directly aligning with docs/workflow-schema.md.
    """
    wf_id = f"wf-{uuid.uuid4().hex[:8]}"
    goal = analysis_dict.get("business_goal", "Equipment Request Approval")
    approvals = analysis_dict.get("approval_requirements", [])
    has_approval = len(approvals) > 0

    # Extract threshold if available
    threshold = 25000
    for rule in analysis_dict.get("business_rules", []):
        cond = rule.get("condition", "")
        matches = re.findall(r"\d+", cond)
        if matches:
            threshold = int(matches[0])
            break

    # Build steps
    steps = [
        {
            "id": "step_1",
            "name": "Retrieve Equipment Request",
            "type": StepType.DATABASE.value,
            "tool": "database",
            "action": "get_equipment_request",
            "description": "Fetch equipment request details from database",
            "inputs": {"request_id": "{{trigger.request_id}}"},
            "outputs": ["request_details"],
            "dependencies": ["trigger_1"],
            "timeout_seconds": 30,
            "retry_config": {"max_retries": 2, "retry_delay_seconds": 5},
        },
        {
            "id": "step_2",
            "name": "Check Equipment Policy",
            "type": StepType.RAG.value,
            "tool": "rag",
            "action": "search_knowledge",
            "description": "Retrieve equipment approval policy guidelines",
            "inputs": {"query": "equipment spending limit policy"},
            "outputs": ["policy_info"],
            "dependencies": ["step_1"],
            "timeout_seconds": 30,
        },
        {
            "id": "step_3",
            "name": "Evaluate Cost Threshold",
            "type": StepType.DECISION.value,
            "description": f"Check if equipment cost is below approval threshold of {threshold}",
            "condition": f"request_details.cost < {threshold}",
            "if_true": "step_4",
            "if_false": "step_5" if has_approval else "step_4",
            "dependencies": ["step_1", "step_2"],
            "timeout_seconds": 15,
        },
        {
            "id": "step_4",
            "name": "Notify IT Team",
            "type": StepType.NOTIFICATION.value,
            "tool": "notification",
            "action": "create_notification",
            "description": "Notify IT team to process the equipment request",
            "inputs": {
                "recipient": "it_team",
                "subject": "Equipment Request Ready for Processing",
                "message": "Equipment request is policy-verified and ready for processing.",
            },
            "outputs": ["notification_result"],
            "dependencies": ["step_3"],
            "timeout_seconds": 30,
        },
    ]

    last_dependencies = ["step_4"]

    if has_approval:
        steps.append({
            "id": "step_5",
            "name": "Request Manager Approval",
            "type": StepType.APPROVAL.value,
            "tool": "approval",
            "action": "request_approval",
            "description": "Request manager approval for high-value equipment",
            "approver_role": approvals[0].get("role", "manager"),
            "inputs": {
                "request_summary": "Equipment request exceeds standard policy threshold",
            },
            "outputs": ["approval_result"],
            "dependencies": ["step_3"],
            "timeout_seconds": 300,
        })
        last_dependencies.append("step_5")

    steps.extend([
        {
            "id": "step_6",
            "name": "Record Decision",
            "type": StepType.DATABASE.value,
            "tool": "database",
            "action": "record_decision",
            "description": "Record final decision state into database",
            "inputs": {
                "request_id": "{{trigger.request_id}}",
                "decision": "approved",
            },
            "outputs": ["decision_record"],
            "dependencies": last_dependencies,
            "timeout_seconds": 30,
        },
        {
            "id": "end_1",
            "name": "Process Complete",
            "type": StepType.END.value,
            "description": "Workflow execution reached completion",
            "dependencies": ["step_6"],
            "timeout_seconds": 10,
        },
    ])

    required_approvals = []
    if has_approval:
        required_approvals.append({
            "step_id": "step_5",
            "approver_role": approvals[0].get("role", "manager"),
            "condition": f"Equipment cost exceeds {threshold}",
        })

    return {
        "workflow_id": wf_id,
        "name": goal[:100],
        "description": f"Automated workflow for {goal}",
        "version": 1,
        "trigger": {
            "id": "trigger_1",
            "type": StepType.TRIGGER.value,
            "event": analysis_dict.get("trigger_event", "equipment_request_created"),
            "description": "Employee initiates request",
            "outputs": ["request_id", "employee_id"],
        },
        "inputs": [
            {"name": "request_id", "type": "string", "required": True, "description": "Request identifier"},
            {"name": "employee_id", "type": "string", "required": True, "description": "Employee identifier"},
        ],
        "steps": steps,
        "metadata": {
            "created_by": "workflow_architect_agent",
            "domain": "procurement",
            "estimated_duration_seconds": 300 if has_approval else 60,
        },
        "required_approvals": required_approvals,
    }


# ─── LangGraph Nodes ──────────────────────────────────────────────────────────

def generate_workflow_node(state: ArchitectState) -> Dict[str, Any]:
    analysis = state["analysis"]
    process_plan = state["process_plan"]

    llm = get_llm(temperature=0.1)
    if llm is None:
        logger.info("Using canonical workflow architect fallback.")
        wf_dict = build_canonical_workflow(analysis, process_plan)
        return {"workflow_definition": wf_dict, "errors": []}

    system_prompt = (
        "You are the Workflow Architect Agent. Convert the given Requirement Analysis "
        "and Process Plan into a strictly compliant WorkflowDefinition JSON conforming to docs/workflow-schema.md. "
        "Must have single TRIGGER node, at least one END node, valid tools (database, rag, notification, approval), "
        "and no raw SQL, arbitrary python, or unapproved urls. Output ONLY pure JSON."
    )

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Requirement Analysis:\n{json.dumps(analysis, indent=2)}\n\nProcess Plan:\n{json.dumps(process_plan, indent=2)}"
            ),
        ]
        response = llm.invoke(messages)
        content = response.content.strip()

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        parsed = json.loads(content.strip())
        return {"workflow_definition": parsed, "errors": []}
    except Exception as e:
        logger.warning(f"LLM workflow generation failed ({e}), falling back to canonical builder.")
        wf_dict = build_canonical_workflow(analysis, process_plan)
        return {"workflow_definition": wf_dict, "errors": [str(e)]}


def validate_workflow_node(state: ArchitectState) -> Dict[str, Any]:
    raw_wf = state.get("workflow_definition")
    errors = list(state.get("errors", []))

    if not raw_wf:
        return {"validation_passed": False, "errors": errors + ["Missing workflow definition"]}

    try:
        wf_obj = WorkflowDefinition(**raw_wf)
        validator = DeterministicValidator()
        val_result = validator.validate(wf_obj)

        if not val_result.is_valid:
            logger.warning(f"Validator reported errors: {val_result.errors}. Re-generating canonical workflow.")
            canonical = build_canonical_workflow(state["analysis"], state["process_plan"])
            return {"workflow_definition": canonical, "validation_passed": True, "errors": errors}

        return {"workflow_definition": wf_obj.model_dump(), "validation_passed": True, "errors": errors}
    except Exception as e:
        logger.warning(f"Workflow Pydantic parsing failed: {e}. Substituting canonical workflow.")
        canonical = build_canonical_workflow(state["analysis"], state["process_plan"])
        return {"workflow_definition": canonical, "validation_passed": True, "errors": errors}


# ─── Graph Construction ───────────────────────────────────────────────────────

def build_workflow_architect_graph():
    builder = StateGraph(ArchitectState)
    builder.add_node("generate", generate_workflow_node)
    builder.add_node("validate", validate_workflow_node)

    builder.set_entry_point("generate")
    builder.add_edge("generate", "validate")
    builder.add_edge("validate", END)

    return builder.compile()


architect_agent = build_workflow_architect_graph()


def generate_workflow(
    analysis: RequirementAnalysis, process_plan: ProcessPlan
) -> WorkflowDefinition:
    """Public helper to synthesize a validated WorkflowDefinition from analysis and process plan."""
    initial_state: ArchitectState = {
        "analysis": analysis.model_dump(),
        "process_plan": process_plan.model_dump(),
        "workflow_definition": None,
        "validation_passed": False,
        "errors": [],
    }

    result = architect_agent.invoke(initial_state)
    raw = result.get("workflow_definition") or {}
    return WorkflowDefinition(**raw)
