"""
Dynamic Manager (Supervisor) Agent using LangGraph ReAct / Supervisor pattern.
Decides next specialist action, coordinates observations, evaluates completion,
and handles Human-in-the-Loop interrupts gracefully.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from langchain_core.messages import SystemMessage, HumanMessage

from app.schemas.orchestrator import (
    AgentAction,
    AgentObservation,
    AgentThoughtStep,
    OrchestrationSession,
)
from app.agents.specialists import (
    PolicySpecialist,
    DataSpecialist,
    ApprovalSpecialist,
    ActionSpecialist,
)
from app.core.llm import get_llm

logger = logging.getLogger(__name__)

# ─── Manager Agent System Prompt ─────────────────────────────────────────────

SUPERVISOR_PROMPT = """You are the Lead Business Workflow Orchestration Manager.
Your role is to achieve the user's business goal by coordinating 4 specialized agents:

1. 'data': Fetch employee details ('get_employee'), request items ('get_request_details').
2. 'policy': Search company policies via RAG ('search_policy'), evaluate spending/compliance limits ('evaluate_compliance').
3. 'approval': Request human manager sign-off ('request_human_approval'), check sign-off status ('check_approval_status').
4. 'action': Send team alerts/emails ('send_notification'), persist final state ('record_decision').
5. 'complete': All necessary steps have been performed. Business goal is fulfilled.

Current State Context:
{accumulated_context}

Previous Steps Taken:
{steps_summary}

Goal:
{goal}

Determine the NEXT best step. Output STRICT JSON matching this schema:
{{
  "thought": "Your clear reasoning why this next step is necessary",
  "specialist": "data | policy | approval | action | manager",
  "action": "action_name or 'finish_goal'",
  "parameters": {{}},
  "is_finished": false,
  "final_summary": null
}}

If all required checks, approvals, and fulfillments are complete, set is_finished: true, specialist: 'manager', action: 'finish_goal', and provide a clear final_summary.
DO NOT include markdown fences. Output ONLY valid JSON."""


# ─── In-Memory Sessions Registry ─────────────────────────────────────────────

ACTIVE_SESSIONS: Dict[str, OrchestrationSession] = {}


class ManagerAgent:
    """Central Supervisor Agent orchestrating business workflows dynamically."""

    def __init__(self):
        self.policy_specialist = PolicySpecialist()
        self.data_specialist = DataSpecialist()
        self.approval_specialist = ApprovalSpecialist()
        self.action_specialist = ActionSpecialist()

    def _format_steps_summary(self, steps: List[AgentThoughtStep]) -> str:
        if not steps:
            return "No previous steps taken yet."
        summary_lines = []
        for s in steps:
            action_desc = f"{s.action_taken.specialist}.{s.action_taken.action}" if s.action_taken else "reasoning"
            obs_desc = s.observation.summary if s.observation else "None"
            summary_lines.append(f"Step {s.step_number} [{s.agent_role}]: Thought: {s.thought} | Action: {action_desc} | Obs: {obs_desc}")
        return "\n".join(summary_lines)

    def _heuristic_decide_next_step(self, session: OrchestrationSession) -> Dict[str, Any]:
        """
        Intelligent heuristic supervisor ensuring seamless autonomous loop
        even when running offline or without an active LLM provider.
        """
        ctx = session.accumulated_context
        goal_lower = session.goal.lower()
        steps = session.steps
        completed_actions = {
            f"{s.action_taken.specialist}.{s.action_taken.action}"
            for s in steps if s.action_taken
        }

        # Step 1: Request & Employee details needed?
        if "data.get_request_details" not in completed_actions and ("laptop" in goal_lower or "request" in goal_lower or "purchase" in goal_lower or "item" in goal_lower):
            req_id = ctx.get("request_id", "req_high_value" if any(w in goal_lower for w in ["macbook", "pro", "high", "70000", "85000"]) else "req_standard")
            return {
                "thought": "I first need to fetch the request and employee details to understand item category and cost.",
                "specialist": "data",
                "action": "get_request_details",
                "parameters": {"request_id": req_id},
                "is_finished": False,
            }

        # Step 2: Employee profile needed?
        if "data.get_employee" not in completed_actions and "employee" in ctx.get("request_details", {}):
            emp_id = ctx.get("request_details", {}).get("employee_id", "emp_101")
            return {
                "thought": "I need to verify the requesting employee's profile and department permissions.",
                "specialist": "data",
                "action": "get_employee",
                "parameters": {"employee_id": emp_id},
                "is_finished": False,
            }

        # Step 3: Policy search via RAG needed?
        if "policy.search_policy" not in completed_actions:
            item_name = ctx.get("request_details", {}).get("item", "equipment")
            return {
                "thought": f"Now I must query the corporate knowledge base to check the policy and spending limits for '{item_name}'.",
                "specialist": "policy",
                "action": "search_policy",
                "parameters": {"query": f"{item_name} purchase limit and manager approval policy"},
                "is_finished": False,
            }

        # Step 4: Compliance evaluation
        if "policy.evaluate_compliance" not in completed_actions:
            req_cost = ctx.get("request_details", {}).get("cost", 25000)
            # Check if user explicitly mentioned cost in goal
            cost_matches = re.findall(r"(?:₹|\$|rs\.?|inr|usd)?\s*([0-9]+(?:,[0-9]+)*)", session.goal, re.IGNORECASE)
            if cost_matches:
                raw_c = cost_matches[0].replace(",", "")
                if raw_c.isdigit():
                    req_cost = int(raw_c)

            return {
                "thought": f"I will evaluate if the item cost ₹{req_cost:,} complies with standard limits or requires approval.",
                "specialist": "policy",
                "action": "evaluate_compliance",
                "parameters": {"cost": req_cost, "threshold": 25000},
                "is_finished": False,
            }

        # Step 5: Approval needed?
        requires_appr = ctx.get("compliance_info", {}).get("requires_approval", False)
        cost_val = ctx.get("compliance_info", {}).get("cost", 0)
        has_approval_step = "approval.request_human_approval" in completed_actions
        approval_granted = ctx.get("approval_status") == "approved" or ctx.get("approval_decision") == "approved"

        if requires_appr and not has_approval_step and not approval_granted:
            item_name = ctx.get("request_details", {}).get("item", "Equipment")
            return {
                "thought": f"The cost (₹{cost_val:,}) exceeds policy threshold (₹25,000). I must route for Human Manager approval.",
                "specialist": "approval",
                "action": "request_human_approval",
                "parameters": {
                    "approver_role": "manager",
                    "summary": f"Sign-off required for {item_name} (Cost: ₹{cost_val:,}) for {ctx.get('employee', {}).get('name', 'Employee')}",
                },
                "is_finished": False,
            }

        # Step 6: Post-approval / fulfillment action (e.g. notify IT team)
        if "action.send_notification" not in completed_actions:
            item_name = ctx.get("request_details", {}).get("item", "Equipment")
            emp_name = ctx.get("employee", {}).get("name", "Employee")
            return {
                "thought": "All checks and required approvals are satisfied. I am notifying the IT Fulfillment team to provision the equipment.",
                "specialist": "action",
                "action": "send_notification",
                "parameters": {
                    "recipient": "it_fulfillment@techcorp.io",
                    "subject": f"Procure & Provision {item_name} for {emp_name}",
                    "message": f"Approved request for {item_name} (Cost: ₹{cost_val:,}) is ready for immediate IT fulfillment.",
                },
                "is_finished": False,
            }

        # Step 7: Record final decision in DB
        if "action.record_decision" not in completed_actions:
            req_id = ctx.get("request_details", {}).get("request_id", ctx.get("request_id", "req_standard"))
            return {
                "thought": "I will persist the finalized decision and audit record into the business database.",
                "specialist": "action",
                "action": "record_decision",
                "parameters": {
                    "request_id": req_id,
                    "decision": "approved_and_fulfilled",
                    "policy_reference": ctx.get("policy_info", {}).get("source", "equipment_policy.md"),
                },
                "is_finished": False,
            }

        # Step 8: Completion
        return {
            "thought": "All necessary verification, policy validation, approvals, and dispatch actions have been verified successfully. Goal is complete.",
            "specialist": "manager",
            "action": "finish_goal",
            "parameters": {},
            "is_finished": True,
            "final_summary": f"Successfully processed request for {ctx.get('employee', {}).get('name', 'Employee')} ({ctx.get('request_details', {}).get('item', 'Item')}). Policy verified, managerial governance satisfied, and IT notification dispatched.",
        }

    def _decide_next_step(self, session: OrchestrationSession) -> Dict[str, Any]:
        """Queries LLM for supervisor decision or falls back to heuristic engine."""
        llm = get_llm(temperature=0.1)
        if llm is None:
            return self._heuristic_decide_next_step(session)

        try:
            prompt = SUPERVISOR_PROMPT.format(
                accumulated_context=json.dumps(session.accumulated_context, indent=2),
                steps_summary=self._format_steps_summary(session.steps),
                goal=session.goal,
            )
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content="What is the next action to take? Output pure JSON.")
            ]
            res = llm.invoke(messages)
            content = res.content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
            parsed = json.loads(content.strip())
            return parsed
        except Exception as e:
            logger.warning(f"LLM supervisor decision failed ({e}), using heuristic supervisor.")
            return self._heuristic_decide_next_step(session)

    def _execute_specialist(self, action: AgentAction, context: Dict[str, Any]) -> AgentObservation:
        """Dispatches action to the correct specialist sub-agent."""
        if action.specialist == "policy":
            return self.policy_specialist.execute(action, context)
        elif action.specialist == "data":
            return self.data_specialist.execute(action, context)
        elif action.specialist == "approval":
            return self.approval_specialist.execute(action, context)
        elif action.specialist == "action":
            return self.action_specialist.execute(action, context)
        else:
            return AgentObservation(
                success=True,
                summary="Manager completed internal evaluation.",
                data={"result": "evaluated"},
            )

    def orchestrate(
        self,
        goal: str,
        initial_context: Optional[Dict[str, Any]] = None,
        domain_hint: Optional[str] = None,
        max_steps: int = 8,
    ) -> OrchestrationSession:
        """
        Executes the autonomous loop: Reason -> Act -> Observe -> Reflect -> Repeat
        until goal is completed or paused for human-in-the-loop approval.
        """
        session = OrchestrationSession(
            goal=goal,
            domain_hint=domain_hint,
            accumulated_context=dict(initial_context or {}),
            status="in_progress",
        )
        ACTIVE_SESSIONS[session.session_id] = session

        for step_idx in range(1, max_steps + 1):
            decision = self._decide_next_step(session)
            thought = decision.get("thought", "Evaluating next workflow stage...")
            is_finished = decision.get("is_finished", False)

            if is_finished or decision.get("specialist") == "manager" and decision.get("action") == "finish_goal":
                final_summary = decision.get("final_summary") or "Goal fulfilled successfully."
                step = AgentThoughtStep(
                    step_number=step_idx,
                    agent_role="manager",
                    thought=thought,
                    action_taken=AgentAction(
                        specialist="manager",
                        action="finish_goal",
                        parameters={},
                        reasoning="All required workflow stages verified.",
                    ),
                    observation=AgentObservation(
                        success=True,
                        summary=final_summary,
                        data={"status": "completed"},
                    ),
                )
                session.steps.append(step)
                session.status = "completed"
                session.summary_message = final_summary
                session.final_outcome = {
                    "status": "completed",
                    "summary": final_summary,
                    "context": session.accumulated_context,
                }
                break

            # Construct Specialist Action
            action = AgentAction(
                specialist=decision.get("specialist", "data"),
                action=decision.get("action", "get_request_details"),
                parameters=decision.get("parameters", {}),
                reasoning=thought,
            )

            # Delegate to Specialist Sub-Agent
            obs = self._execute_specialist(action, session.accumulated_context)

            step = AgentThoughtStep(
                step_number=step_idx,
                agent_role=f"{action.specialist}_specialist",
                thought=thought,
                action_taken=action,
                observation=obs,
            )
            session.steps.append(step)

            # Accumulate extracted knowledge in context
            if obs.success and obs.data:
                if "request_details" in obs.data:
                    session.accumulated_context["request_details"] = obs.data["request_details"]
                if "employee" in obs.data:
                    session.accumulated_context["employee"] = obs.data["employee"]
                if "policy_info" in obs.data:
                    session.accumulated_context["policy_info"] = obs.data["policy_info"]
                if "requires_approval" in obs.data:
                    session.accumulated_context["compliance_info"] = obs.data
                if "approval_request" in obs.data:
                    session.accumulated_context["approval_request"] = obs.data["approval_request"]
                if "decision_record" in obs.data:
                    session.accumulated_context["decision_record"] = obs.data["decision_record"]

            # Human-in-the-Loop Interrupt Check
            if obs.requires_human:
                session.status = "awaiting_approval"
                session.pending_approval = obs.data.get("approval_request")
                session.summary_message = (
                    f"Workflow paused at step {step_idx}: Manager sign-off required before continuing."
                )
                break

        ACTIVE_SESSIONS[session.session_id] = session
        return session

    def resume(
        self,
        session_id: str,
        approval_decision: str,
        approver_comments: Optional[str] = None,
        reviewer_role: str = "manager",
        max_steps: int = 8,
    ) -> OrchestrationSession:
        """
        Resumes an awaiting-approval workflow after Human Reviewer provides decision.
        """
        session = ACTIVE_SESSIONS.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        # Record human approval response
        step_num = len(session.steps) + 1
        human_obs = AgentObservation(
            success=True,
            data={
                "decision": approval_decision,
                "reviewed_by": reviewer_role,
                "comments": approver_comments,
            },
            summary=f"Human Approver ({reviewer_role}) submitted decision: {approval_decision.upper()}. Comments: {approver_comments}",
        )
        step = AgentThoughtStep(
            step_number=step_num,
            agent_role="human_approver",
            thought=f"Human reviewer evaluated pending approval request.",
            observation=human_obs,
        )
        session.steps.append(step)

        session.accumulated_context["approval_status"] = approval_decision
        session.accumulated_context["approval_decision"] = approval_decision
        session.pending_approval = None

        if approval_decision == "rejected":
            session.status = "completed"
            summary = f"Request was rejected by {reviewer_role}. Workflow ended without fulfillment."
            session.summary_message = summary
            session.final_outcome = {"status": "rejected", "summary": summary}
            ACTIVE_SESSIONS[session_id] = session
            return session

        # Approval granted -> Resume autonomous execution to complete fulfillment
        session.status = "in_progress"

        for step_idx in range(len(session.steps) + 1, len(session.steps) + max_steps + 1):
            decision = self._decide_next_step(session)
            thought = decision.get("thought", "Resuming remaining fulfillment actions...")
            is_finished = decision.get("is_finished", False)

            if is_finished or decision.get("specialist") == "manager" and decision.get("action") == "finish_goal":
                final_summary = decision.get("final_summary") or "Workflow completed after approval."
                step = AgentThoughtStep(
                    step_number=step_idx,
                    agent_role="manager",
                    thought=thought,
                    action_taken=AgentAction(
                        specialist="manager",
                        action="finish_goal",
                        parameters={},
                        reasoning="Post-approval execution verified.",
                    ),
                    observation=AgentObservation(
                        success=True,
                        summary=final_summary,
                        data={"status": "completed"},
                    ),
                )
                session.steps.append(step)
                session.status = "completed"
                session.summary_message = final_summary
                session.final_outcome = {
                    "status": "completed",
                    "summary": final_summary,
                    "context": session.accumulated_context,
                }
                break

            action = AgentAction(
                specialist=decision.get("specialist", "action"),
                action=decision.get("action", "send_notification"),
                parameters=decision.get("parameters", {}),
                reasoning=thought,
            )
            obs = self._execute_specialist(action, session.accumulated_context)

            step = AgentThoughtStep(
                step_number=step_idx,
                agent_role=f"{action.specialist}_specialist",
                thought=thought,
                action_taken=action,
                observation=obs,
            )
            session.steps.append(step)

            if obs.success and obs.data:
                if "decision_record" in obs.data:
                    session.accumulated_context["decision_record"] = obs.data["decision_record"]

        ACTIVE_SESSIONS[session_id] = session
        return session


# Global singleton instance
_manager_agent: Optional[ManagerAgent] = None


def get_manager_agent() -> ManagerAgent:
    global _manager_agent
    if _manager_agent is None:
        _manager_agent = ManagerAgent()
    return _manager_agent
