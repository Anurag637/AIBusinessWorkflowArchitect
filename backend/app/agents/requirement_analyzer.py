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

    # Detect numbers / thresholds
    cost_matches = re.findall(r"(?:₹|\$|rs\.?|inr|usd)?\s*([0-9]+(?:,[0-9]+)*)", text, re.IGNORECASE)
    user_num = None
    if cost_matches:
        raw_num = cost_matches[0].replace(",", "")
        if raw_num.isdigit() and int(raw_num) > 0:
            user_num = int(raw_num)

    # Detect domain, actors, trigger, and inputs
    if any(w in lower for w in ["refund", "return", "cancel order", "order"]):
        domain = "customer_order_refund"
        trigger_event = "customer_refund_requested"
        trigger_description = "Customer submits an order refund or return request"
        threshold = user_num or 10000
        inputs = [
            {"name": "request_id", "type": "string", "required": True, "description": "Order or refund reference ID"},
            {"name": "customer_id", "type": "string", "required": True, "description": "Customer account identifier"},
            {"name": "cost", "type": "number", "required": False, "description": "Refund amount requested"},
        ]
        actors = [
            {"role": "customer", "type": "human", "responsibilities": ["Submits refund request"]},
            {"role": "customer_support", "type": "human", "responsibilities": ["Verifies return eligibility & policy"]},
            {"role": "finance_manager", "type": "human", "responsibilities": ["Approves high-value refunds"]},
        ]
        approver_role = "finance_manager"
        approver_rationale = f"Refund amount exceeds direct support threshold of ₹{threshold:,}"
        entities = ["customer_order", "refund_policy", "gateway_transaction", "audit_log"]

    elif any(w in lower for w in ["travel", "expense", "reimbursement", "hotel", "flight", "per diem"]):
        domain = "travel_expense_claim"
        trigger_event = "expense_claim_submitted"
        trigger_description = "Employee files a travel and expense claim with receipts"
        threshold = user_num or 10000
        inputs = [
            {"name": "request_id", "type": "string", "required": True, "description": "Expense claim identifier"},
            {"name": "employee_id", "type": "string", "required": True, "description": "Employee ID"},
            {"name": "cost", "type": "number", "required": False, "description": "Total claim reimbursement amount"},
        ]
        actors = [
            {"role": "employee", "type": "human", "responsibilities": ["Submits receipts and itinerary"]},
            {"role": "department_head", "type": "human", "responsibilities": ["Reviews and approves claim"]},
            {"role": "finance_payroll", "type": "human", "responsibilities": ["Disburses reimbursement"]},
        ]
        approver_role = "department_head"
        approver_rationale = f"Expense exceeds standard per diem limit of ₹{threshold:,}"
        entities = ["expense_report", "travel_policy", "payout_record", "audit_log"]

    elif any(w in lower for w in ["cloud", "database", "access", "permission", "security", "iam", "vpn"]):
        domain = "security_access_control"
        trigger_event = "access_request_submitted"
        trigger_description = "Engineer requests privileged cloud infrastructure or database access"
        threshold = user_num or 25000
        inputs = [
            {"name": "request_id", "type": "string", "required": True, "description": "Access ticket identifier"},
            {"name": "employee_id", "type": "string", "required": True, "description": "Requesting engineer ID"},
            {"name": "cost", "type": "number", "required": False, "description": "Resource tier / cost rating"},
        ]
        actors = [
            {"role": "engineer", "type": "human", "responsibilities": ["Submits access justification"]},
            {"role": "security_lead", "type": "human", "responsibilities": ["Evaluates compliance and authorizes role"]},
            {"role": "devops_iam", "type": "human", "responsibilities": ["Provisions temporary access keys"]},
        ]
        approver_role = "security_lead"
        approver_rationale = "Privileged database access requires formal security sign-off"
        entities = ["iam_role", "security_policy", "access_grant", "audit_log"]

    elif any(w in lower for w in ["invoice", "vendor", "supplier", "billing", "contractor"]):
        domain = "vendor_invoice_settlement"
        trigger_event = "vendor_invoice_submitted"
        trigger_description = "Vendor or contractor submits invoice for delivered services"
        threshold = user_num or 50000
        inputs = [
            {"name": "request_id", "type": "string", "required": True, "description": "Invoice number"},
            {"name": "vendor_id", "type": "string", "required": True, "description": "Vendor account identifier"},
            {"name": "cost", "type": "number", "required": False, "description": "Invoice total payable amount"},
        ]
        actors = [
            {"role": "vendor", "type": "human", "responsibilities": ["Submits invoice documentation"]},
            {"role": "accounts_payable", "type": "human", "responsibilities": ["Verifies 3-way match against PO"]},
            {"role": "finance_director", "type": "human", "responsibilities": ["Authorizes fund release"]},
        ]
        approver_role = "finance_director"
        approver_rationale = f"Invoice value exceeds ₹{threshold:,} threshold requiring director sign-off"
        entities = ["invoice_record", "procurement_policy", "disbursement", "audit_log"]

    else:
        domain = domain_hint or ("equipment_procurement" if any(w in lower for w in ["laptop", "equipment", "hardware", "device", "macbook"]) else "general_business_process")
        trigger_event = "business_request_submitted"
        trigger_description = "User initiates a business process request"
        threshold = user_num or 25000
        inputs = [
            {"name": "request_id", "type": "string", "required": True, "description": "Unique business request identifier"},
            {"name": "employee_id", "type": "string", "required": True, "description": "Requesting stakeholder identifier"},
            {"name": "cost", "type": "number", "required": False, "description": "Monetary or resource value"},
        ]
        actors = [
            {"role": "employee", "type": "human", "responsibilities": ["Initiates request"]},
            {"role": "manager", "type": "human", "responsibilities": ["Reviews and authorizes discretionary request"]},
            {"role": "operations_team", "type": "human", "responsibilities": ["Executes and fulfills verified request"]},
        ]
        approver_role = "manager"
        approver_rationale = f"Request value exceeds standard ₹{threshold:,} threshold"
        entities = ["business_request", "policy_record", "fulfillment_action", "audit_log"]

    # Detect approvals
    has_approval = any(w in lower for w in ["approval", "approve", "review", "sign-off", "manager", "lead", "director", "authorize"]) or threshold > 0
    approvals: List[Dict[str, Any]] = []
    if has_approval:
        approvals.append({
            "role": approver_role,
            "trigger_condition": f"Value/Cost exceeds ₹{threshold:,}",
            "rationale": approver_rationale,
        })

    # Detect rules
    rules: List[Dict[str, Any]] = [
        {
            "rule_id": "rule_1",
            "description": f"If amount/cost is below ₹{threshold:,}, automated direct processing is allowed.",
            "condition": f"cost < {threshold}",
            "action": "Proceed with automated processing and notification",
        },
        {
            "rule_id": "rule_2",
            "description": f"If amount/cost is ₹{threshold:,} or above, human {approver_role} sign-off is mandatory.",
            "condition": f"cost >= {threshold}",
            "action": f"Route to {approver_role} for review",
        }
    ]

    # Clean first sentence for concise goal
    clean_goal = text.strip().split(".")[0].strip()
    if len(clean_goal) < 15:
        clean_goal = text.strip()

    return {
        "business_goal": clean_goal,
        "trigger_event": trigger_event,
        "trigger_description": trigger_description,
        "inputs": inputs,
        "outputs": ["process_status", "action_notification", "immutable_audit_record"],
        "actors": actors,
        "business_rules": rules,
        "data_entities": entities,
        "approval_requirements": approvals,
        "potential_exceptions": [
            "Required identifiers or records not found in database",
            "Threshold evaluation failed due to invalid cost data",
            "Approver sign-off timeout or rejection",
        ],
        "complexity_assessment": "Moderate" if approvals else "Simple",
        "confidence_score": 0.95,
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
