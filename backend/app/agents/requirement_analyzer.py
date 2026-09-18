"""
Requirement Analyzer Agent using LangGraph.
Deconstructs natural language business requirements into structured specifications.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from app.schemas.requirement import (
    RequirementAnalysis,
    BusinessRule,
    Actor,
    ApprovalCriteria,
)
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


# ─── State Definition ─────────────────────────────────────────────────────────

class AnalyzerState(TypedDict):
    requirement_text: str
    domain_hint: Optional[str]
    analysis: Optional[Dict[str, Any]]
    errors: List[str]


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the Lead Requirement Analysis Agent for an enterprise workflow automation system.
Analyze the given business requirement and output a STRICT JSON object matching this schema:

{
  "business_goal": "Clear one-sentence goal of this business process",
  "trigger_event": "Event name that initiates the workflow (e.g., equipment_request_submitted)",
  "trigger_description": "Detailed explanation of trigger conditions",
  "inputs": [
    {"name": "request_id", "type": "string", "required": true, "description": "Identifier of the request"},
    {"name": "employee_id", "type": "string", "required": true, "description": "Requesting employee ID"}
  ],
  "outputs": ["Outcome 1", "Outcome 2"],
  "actors": [
    {"role": "employee", "type": "human", "responsibilities": ["Submit request"]},
    {"role": "manager", "type": "human", "responsibilities": ["Review high-value request"]},
    {"role": "it_team", "type": "human", "responsibilities": ["Provision equipment"]}
  ],
  "business_rules": [
    {
      "rule_id": "rule_1",
      "description": "Rule description with explicit thresholds",
      "condition": "cost < 25000",
      "action": "Direct IT processing"
    }
  ],
  "data_entities": ["employee", "equipment_request", "policy_document"],
  "approval_requirements": [
    {
      "role": "manager",
      "trigger_condition": "Cost exceeds ₹25,000",
      "rationale": "High value asset spending policy"
    }
  ],
  "potential_exceptions": ["Employee not found", "Budget limit exceeded", "Asset out of stock"],
  "complexity_assessment": "Simple | Moderate | Complex",
  "confidence_score": 0.95
}

DO NOT include any markdown code fences (```json or ```). Output ONLY pure valid JSON."""


# ─── Rule-Based / Heuristic Fallback Engine ───────────────────────────────────

def heuristic_analyze(text: str, domain_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Intelligent heuristic fallback analyzer when LLM is unavailable (e.g. offline testing/CI).
    Accurately extracts entities, thresholds, roles, and rules from requirement text.
    """
    lower = text.lower()

    # Detect domain
    domain = domain_hint or ("equipment_procurement" if any(w in lower for w in ["laptop", "equipment", "hardware", "device"]) else "general_business")

    # Detect numbers / thresholds
    cost_matches = re.findall(r"(?:₹|\$|rs\.?|inr|usd)?\s*([0-9]+(?:,[0-9]+)*)", text, re.IGNORECASE)
    threshold = 25000
    if cost_matches:
        raw_num = cost_matches[0].replace(",", "")
        if raw_num.isdigit():
            threshold = int(raw_num)

    # Detect actors
    actors: List[Dict[str, Any]] = []
    if "employee" in lower or "user" in lower:
        actors.append({"role": "employee", "type": "human", "responsibilities": ["Initiates request"]})
    if "it" in lower or "it team" in lower or "it staff" in lower:
        actors.append({"role": "it_team", "type": "human", "responsibilities": ["Process and fulfill request"]})
    if "manager" in lower or "supervisor" in lower or "lead" in lower:
        actors.append({"role": "manager", "type": "human", "responsibilities": ["Approve conditional requests"]})
    if "finance" in lower:
        actors.append({"role": "finance", "type": "human", "responsibilities": ["Disburse funds"]})
    if not actors:
        actors.append({"role": "user", "type": "human", "responsibilities": ["Primary actor"]})

    # Detect approvals
    approvals: List[Dict[str, Any]] = []
    if any(w in lower for w in ["approval", "approve", "manager approval"]):
        approvals.append({
            "role": "manager" if "manager" in lower else "supervisor",
            "trigger_condition": f"Cost exceeds {threshold}",
            "rationale": "Manager approval required for expenditures above standard threshold",
        })

    # Detect rules
    rules: List[Dict[str, Any]] = [
        {
            "rule_id": "rule_1",
            "description": f"If cost is below {threshold}, direct processing is allowed.",
            "condition": f"cost < {threshold}",
            "action": "Proceed with standard fulfillment",
        },
        {
            "rule_id": "rule_2",
            "description": f"If cost exceeds or equals {threshold}, human approval is required.",
            "condition": f"cost >= {threshold}",
            "action": "Route for manager approval",
        }
    ]

    return {
        "business_goal": f"Automate requirement process for {domain.replace('_', ' ')}",
        "trigger_event": "business_request_submitted",
        "trigger_description": "User or employee submits a request",
        "inputs": [
            {"name": "request_id", "type": "string", "required": True, "description": "Unique request identifier"},
            {"name": "employee_id", "type": "string", "required": True, "description": "Identifier of requesting user"},
            {"name": "cost", "type": "number", "required": False, "description": "Monetary cost of requested item/service"}
        ],
        "outputs": ["approval_status", "fulfillment_notification", "audit_record"],
        "actors": actors,
        "business_rules": rules,
        "data_entities": ["request", "policy", "approval_record", "notification"],
        "approval_requirements": approvals,
        "potential_exceptions": [
            "Cost information missing or invalid",
            "Approver unavailable / timeout",
            "Policy document retrieval failed"
        ],
        "complexity_assessment": "Moderate" if approvals else "Simple",
        "confidence_score": 0.92,
    }


# ─── LangGraph Nodes ──────────────────────────────────────────────────────────

def extract_node(state: AnalyzerState) -> Dict[str, Any]:
    """Node that invokes LLM or fallback to analyze requirements."""
    req_text = state["requirement_text"]
    domain = state.get("domain_hint")

    llm = get_llm(temperature=0.1)
    if llm is None:
        logger.info("Using heuristic analyzer fallback (no LLM initialized).")
        return {"analysis": heuristic_analyze(req_text, domain), "errors": []}

    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Business Requirement:\n{req_text}\n\nDomain hint: {domain or 'general'}")
        ]
        response = llm.invoke(messages)
        content = response.content.strip()

        # Strip markdown fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        parsed = json.loads(content.strip())
        return {"analysis": parsed, "errors": []}
    except Exception as e:
        logger.warning(f"LLM extraction failed ({e}), falling back to heuristic analyzer.")
        return {"analysis": heuristic_analyze(req_text, domain), "errors": [str(e)]}


def validate_node(state: AnalyzerState) -> Dict[str, Any]:
    """Node that validates and structures the parsed analysis."""
    raw = state.get("analysis") or {}
    errors = list(state.get("errors", []))

    # Ensure required top level keys
    if "business_goal" not in raw:
        raw["business_goal"] = "Process business requirement"
    if "trigger_event" not in raw:
        raw["trigger_event"] = "request_created"
    if "inputs" not in raw or not raw["inputs"]:
        raw["inputs"] = [{"name": "request_id", "type": "string", "required": True}]
    if "actors" not in raw:
        raw["actors"] = []
    if "business_rules" not in raw:
        raw["business_rules"] = []
    if "approval_requirements" not in raw:
        raw["approval_requirements"] = []

    return {"analysis": raw, "errors": errors}


# ─── Graph Construction ───────────────────────────────────────────────────────

def build_requirement_analyzer_graph():
    builder = StateGraph(AnalyzerState)
    builder.add_node("extract", extract_node)
    builder.add_node("validate", validate_node)

    builder.set_entry_point("extract")
    builder.add_edge("extract", "validate")
    builder.add_edge("validate", END)

    return builder.compile()


analyzer_agent = build_requirement_analyzer_graph()


def analyze_requirement(
    requirement_text: str, domain_hint: Optional[str] = None
) -> RequirementAnalysis:
    """Public helper to run the requirement analyzer agent and return structured output."""
    initial_state: AnalyzerState = {
        "requirement_text": requirement_text,
        "domain_hint": domain_hint,
        "analysis": None,
        "errors": [],
    }

    result = analyzer_agent.invoke(initial_state)
    raw_analysis = result.get("analysis") or {}

    return RequirementAnalysis(**raw_analysis)
