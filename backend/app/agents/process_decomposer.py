"""
Process Decomposer Agent using LangGraph.
Decomposes structured requirement analyses into stage-based process execution plans.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from app.schemas.requirement import RequirementAnalysis
from app.schemas.process import (
    ProcessPlan,
    ProcessStage,
    PlannedStep,
    ToolRequirement,
)
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


# ─── State Definition ─────────────────────────────────────────────────────────

class DecomposerState(TypedDict):
    analysis: Dict[str, Any]
    max_stages: int
    plan: Optional[Dict[str, Any]]
    errors: List[str]


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the Lead Process Decomposer Agent.
Decompose the given requirement analysis into an enterprise multi-stage process plan.
Output STRICT JSON matching this schema:

{
  "process_name": "Concise process name",
  "summary": "High level workflow lifecycle summary",
  "stages": [
    {"name": "Intake", "order": 1, "description": "Request reception and validation", "step_ids": ["trigger_1", "step_1"]},
    {"name": "Verification", "order": 2, "description": "Policy check and data enrichment", "step_ids": ["step_2"]},
    {"name": "Evaluation", "order": 3, "description": "Threshold and condition branch", "step_ids": ["step_3"]},
    {"name": "Approval", "order": 4, "description": "Human review if required", "step_ids": ["step_5"]},
    {"name": "Fulfillment", "order": 5, "description": "Notification and DB record", "step_ids": ["step_4", "step_6"]},
    {"name": "Completion", "order": 6, "description": "Terminal end state", "step_ids": ["end_1"]}
  ],
  "steps": [
    {
      "id": "step_1",
      "name": "Retrieve Request Details",
      "description": "Fetch request details from database",
      "stage": "Intake",
      "category": "database",
      "dependencies": ["trigger_1"],
      "expected_inputs": ["request_id"],
      "expected_outputs": ["request_details"],
      "requires_human": false,
      "is_critical": true
    }
  ],
  "tool_requirements": [
    {"tool_name": "database", "action": "get_equipment_request", "purpose": "Fetch request record"},
    {"tool_name": "rag", "action": "search_knowledge", "purpose": "Search policy guidelines"},
    {"tool_name": "notification", "action": "create_notification", "purpose": "Notify teams"},
    {"tool_name": "approval", "action": "request_approval", "purpose": "Handle human approval"}
  ],
  "data_flow_summary": {"step_1": ["trigger_1"], "step_2": ["step_1"]},
  "estimated_duration_seconds": 180
}

DO NOT include markdown code fences (```json or ```). Output ONLY pure valid JSON."""


# ─── Heuristic Fallback Decomposition ─────────────────────────────────────────

def heuristic_decompose(analysis_dict: Dict[str, Any], max_stages: int = 6) -> Dict[str, Any]:
    """Fallback generator that constructs a canonical enterprise process plan from analysis."""
    goal = analysis_dict.get("business_goal", "Business Process")
    approvals = analysis_dict.get("approval_requirements", [])
    has_approval = len(approvals) > 0

    stages = [
        ProcessStage(name="Intake", order=1, description="Process trigger and intake", step_ids=["trigger_1", "step_1"]),
        ProcessStage(name="Policy Verification", order=2, description="Retrieve policy criteria via RAG", step_ids=["step_2"]),
        ProcessStage(name="Condition Evaluation", order=3, description="Branch on business rules & thresholds", step_ids=["step_3"]),
    ]

    steps = [
        PlannedStep(
            id="step_1",
            name="Retrieve Business Request",
            description="Fetch submitted request record from database",
            stage="Intake",
            category="database",
            dependencies=["trigger_1"],
            expected_inputs=["request_id"],
            expected_outputs=["request_details"],
            requires_human=False,
            is_critical=True,
        ),
        PlannedStep(
            id="step_2",
            name="Check Policy & Guidelines",
            description="Query enterprise knowledge base for policy limits",
            stage="Policy Verification",
            category="rag",
            dependencies=["step_1"],
            expected_inputs=["query"],
            expected_outputs=["policy_info"],
            requires_human=False,
            is_critical=True,
        ),
        PlannedStep(
            id="step_3",
            name="Evaluate Cost Threshold",
            description="Evaluate if cost requires managerial approval",
            stage="Condition Evaluation",
            category="decision",
            dependencies=["step_1", "step_2"],
            expected_inputs=["request_details", "policy_info"],
            expected_outputs=["decision_outcome"],
            requires_human=False,
            is_critical=True,
        ),
    ]

    current_order = 4
    if has_approval:
        stages.append(
            ProcessStage(name="Manager Approval", order=current_order, description="Human review for threshold violation", step_ids=["step_5"])
        )
        current_order += 1
        steps.append(
            PlannedStep(
                id="step_5",
                name="Request Manager Approval",
                description="Prompt manager for discretionary sign-off",
                stage="Manager Approval",
                category="approval",
                dependencies=["step_3"],
                expected_inputs=["request_details", "policy_info"],
                expected_outputs=["approval_result"],
                requires_human=True,
                is_critical=True,
            )
        )

    # Fulfillment stage
    fulfillment_step_ids = ["step_4", "step_6"]
    stages.append(
        ProcessStage(name="Fulfillment & Recording", order=current_order, description="Notify team and record final state", step_ids=fulfillment_step_ids)
    )
    current_order += 1

    steps.extend([
        PlannedStep(
            id="step_4",
            name="Notify Operational Team",
            description="Send action item notification to fulfilling department",
            stage="Fulfillment & Recording",
            category="notification",
            dependencies=["step_3"],
            expected_inputs=["request_details"],
            expected_outputs=["notification_result"],
            requires_human=False,
            is_critical=False,
        ),
        PlannedStep(
            id="step_6",
            name="Record Decision",
            description="Persist finalized decision into database",
            stage="Fulfillment & Recording",
            category="database",
            dependencies=["step_4", "step_5"] if has_approval else ["step_4"],
            expected_inputs=["request_id", "decision_outcome"],
            expected_outputs=["decision_record"],
            requires_human=False,
            is_critical=True,
        ),
        PlannedStep(
            id="end_1",
            name="Process Completed",
            description="Terminal step representing workflow completion",
            stage="Completion",
            category="end",
            dependencies=["step_6"],
            expected_inputs=["decision_record"],
            expected_outputs=["final_status"],
            requires_human=False,
            is_critical=True,
        )
    ])

    stages.append(
        ProcessStage(name="Completion", order=current_order, description="Final workflow state reached", step_ids=["end_1"])
    )

    tools = [
        ToolRequirement(tool_name="database", action="get_equipment_request", purpose="Fetch request information"),
        ToolRequirement(tool_name="rag", action="search_knowledge", purpose="Search policy guidelines"),
        ToolRequirement(tool_name="notification", action="create_notification", purpose="Dispatch operational alerts"),
        ToolRequirement(tool_name="database", action="record_decision", purpose="Save audit and decision records"),
    ]
    if has_approval:
        tools.append(ToolRequirement(tool_name="approval", action="request_approval", purpose="Request human approval"))

    data_flow = {
        "step_1": ["trigger_1"],
        "step_2": ["step_1"],
        "step_3": ["step_1", "step_2"],
        "step_4": ["step_3"],
        "step_6": ["step_4"] + (["step_5"] if has_approval else []),
        "end_1": ["step_6"],
    }
    if has_approval:
        data_flow["step_5"] = ["step_3"]

    return {
        "process_name": f"{goal} - Process Plan",
        "summary": f"Automated execution plan for {goal} with {len(steps)} planned operations.",
        "stages": [s.model_dump() for s in stages],
        "steps": [s.model_dump() for s in steps],
        "tool_requirements": [t.model_dump() for t in tools],
        "data_flow_summary": data_flow,
        "estimated_duration_seconds": 180 if has_approval else 30,
    }


# ─── LangGraph Nodes ──────────────────────────────────────────────────────────

def decompose_node(state: DecomposerState) -> Dict[str, Any]:
    analysis = state["analysis"]
    max_stages = state.get("max_stages", 6)

    llm = get_llm(temperature=0.1)
    if llm is None:
        logger.info("Using heuristic process decomposer fallback.")
        return {"plan": heuristic_decompose(analysis, max_stages), "errors": []}

    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Requirement Analysis:\n{json.dumps(analysis, indent=2)}\n\nMax stages: {max_stages}")
        ]
        response = llm.invoke(messages)
        content = response.content.strip()

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        parsed = json.loads(content.strip())
        return {"plan": parsed, "errors": []}
    except Exception as e:
        logger.warning(f"LLM decomposition failed ({e}), falling back to heuristic decomposer.")
        return {"plan": heuristic_decompose(analysis, max_stages), "errors": [str(e)]}


def validate_plan_node(state: DecomposerState) -> Dict[str, Any]:
    plan = state.get("plan") or {}
    errors = list(state.get("errors", []))

    if "process_name" not in plan:
        plan["process_name"] = "Automated Business Process"
    if "stages" not in plan or not plan["stages"]:
        plan["stages"] = []
    if "steps" not in plan or not plan["steps"]:
        plan["steps"] = []

    return {"plan": plan, "errors": errors}


# ─── Graph Construction ───────────────────────────────────────────────────────

def build_process_decomposer_graph():
    builder = StateGraph(DecomposerState)
    builder.add_node("decompose", decompose_node)
    builder.add_node("validate_plan", validate_plan_node)

    builder.set_entry_point("decompose")
    builder.add_edge("decompose", "validate_plan")
    builder.add_edge("validate_plan", END)

    return builder.compile()


decomposer_agent = build_process_decomposer_graph()


def decompose_process(
    analysis: RequirementAnalysis, max_stages: int = 6
) -> ProcessPlan:
    """Public helper to run the process decomposer agent and return structured ProcessPlan."""
    initial_state: DecomposerState = {
        "analysis": analysis.model_dump(),
        "max_stages": max_stages,
        "plan": None,
        "errors": [],
    }

    result = decomposer_agent.invoke(initial_state)
    raw_plan = result.get("plan") or {}
    return ProcessPlan(**raw_plan)
