"""
Simulation Engine for dry-running workflows without side effects.
Features safe variable interpolation, safe condition evaluation, and execution tracing.
"""

import re
import ast
import operator
import logging
import time
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

from app.schemas.workflow import WorkflowDefinition, WorkflowStep, StepType
from app.tools.registry import get_tool_registry, ToolRegistry

logger = logging.getLogger(__name__)


# ─── Safe Condition Evaluator ─────────────────────────────────────────────────

SAFE_OPERATORS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def _safe_eval_node(node: ast.AST, context: Dict[str, Any]) -> Any:
    """Safely evaluates a limited set of AST nodes without allowing arbitrary code."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Name):
        return context.get(node.id)
    elif isinstance(node, ast.Attribute):
        parent = _safe_eval_node(node.value, context)
        if isinstance(parent, dict):
            return parent.get(node.attr)
        return getattr(parent, node.attr, None)
    elif isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, context)
        for op_node, comparator in zip(node.ops, node.comparators):
            op_fn = SAFE_OPERATORS.get(type(op_node))
            if not op_fn:
                raise ValueError(f"Unsupported operator: {type(op_node)}")
            right = _safe_eval_node(comparator, context)
            if not op_fn(left, right):
                return False
            left = right
        return True
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _safe_eval_node(node.operand, context)
    else:
        raise ValueError(f"Unsupported expression construct: {type(node)}")


def evaluate_condition_safely(condition_str: str, context: Dict[str, Any]) -> bool:
    """Parses and evaluates condition expression strictly using safe AST nodes."""
    try:
        parsed = ast.parse(condition_str.strip(), mode="eval")
        return bool(_safe_eval_node(parsed.body, context))
    except Exception as e:
        logger.warning(f"Condition evaluation fallback for '{condition_str}': {e}")
        # Fallback simple regex evaluator for '<', '>', '=='
        match = re.search(r"([a-zA-Z0-9_\.]+)\s*(<|<=|>|>=|==|!=)\s*([0-9]+|'[^']*'|\"[^\"]*\")", condition_str)
        if match:
            var_path, op_sym, val_lit = match.groups()
            parts = var_path.split(".")
            curr = context
            for p in parts:
                if isinstance(curr, dict):
                    curr = curr.get(p)
                else:
                    curr = None
                    break

            # Parse literal
            target_val = int(val_lit) if val_lit.isdigit() else val_lit.strip("'\"")
            if curr is not None:
                if op_sym == "<":
                    return float(curr) < float(target_val)
                elif op_sym == "<=":
                    return float(curr) <= float(target_val)
                elif op_sym == ">":
                    return float(curr) > float(target_val)
                elif op_sym == ">=":
                    return float(curr) >= float(target_val)
                elif op_sym == "==":
                    return str(curr) == str(target_val)
                elif op_sym == "!=":
                    return str(curr) != str(target_val)

        return True


# ─── Variable Interpolation ───────────────────────────────────────────────────

def interpolate_variables(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively replaces {{source.field}} references with actual runtime values."""
    var_pattern = re.compile(r"\{\{([a-zA-Z0-9_\.]+)\}\}")

    def replace_value(val: Any) -> Any:
        if isinstance(val, str):
            matches = var_pattern.findall(val)
            if not matches:
                return val

            # Check if entire string is single variable reference
            if len(matches) == 1 and val.strip() == f"{{{{{matches[0]}}}}}":
                parts = matches[0].split(".")
                curr = context
                for p in parts:
                    if isinstance(curr, dict):
                        curr = curr.get(p)
                    else:
                        return val
                return curr

            # Multiple or embedded references
            result_str = val
            for m in matches:
                parts = m.split(".")
                curr = context
                for p in parts:
                    if isinstance(curr, dict):
                        curr = curr.get(p)
                    else:
                        curr = ""
                        break
                result_str = result_str.replace(f"{{{{{m}}}}}", str(curr if curr is not None else ""))
            return result_str

        elif isinstance(val, dict):
            return {k: replace_value(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [replace_value(item) for item in val]
        return val

    return {k: replace_value(v) for k, v in inputs.items()}


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StepExecutionRecord(BaseModel):
    step_id: str
    step_name: str
    step_type: str
    status: str  # completed, skipped, failed
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    error: Optional[str] = None


class SimulationResult(BaseModel):
    workflow_id: str
    status: str  # completed, failed
    total_duration_ms: int
    steps_executed: List[StepExecutionRecord]
    tools_simulated: List[str]
    final_outputs: Dict[str, Any]
    approval_simulated: bool


# ─── Simulation Engine ────────────────────────────────────────────────────────

class SimulationEngine:
    """Executes workflows in isolated simulation sandbox."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_tool_registry()

    def simulate(
        self,
        workflow: WorkflowDefinition,
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        start_time = time.perf_counter()
        records: List[StepExecutionRecord] = []
        tools_used: Set[str] = set()
        approval_simulated = False

        # Initialize execution context with trigger values
        trigger_data = initial_inputs or {
            "request_id": "req_standard",
            "employee_id": "emp_101",
            "cost": 18000,
        }
        context: Dict[str, Any] = {
            "trigger": trigger_data,
        }

        # Step map
        step_map: Dict[str, WorkflowStep] = {s.id: s for s in workflow.steps}
        completed_steps: Set[str] = {"trigger_1"}
        skipped_steps: Set[str] = set()

        # Step-by-step dry run execution
        active_step_ids = [s.id for s in workflow.steps]

        while True:
            # Find next runnable step whose dependencies are satisfied
            candidate: Optional[WorkflowStep] = None
            for sid in active_step_ids:
                if sid in completed_steps or sid in skipped_steps:
                    continue
                step = step_map[sid]
                deps = step.dependencies or []
                # Step is runnable if at least one dependency completed and none failed
                if all(d in completed_steps or d in skipped_steps for d in deps):
                    candidate = step
                    break

            if candidate is None:
                break

            step = candidate
            step_start = time.perf_counter()
            s_type = step.type.value if hasattr(step.type, "value") else str(step.type)

            # Check if this step should be skipped due to a decision branch
            if any(d in skipped_steps for d in step.dependencies) and not any(d in completed_steps for d in step.dependencies):
                skipped_steps.add(step.id)
                continue

            interpolated_inputs = interpolate_variables(step.inputs or {}, context)
            step_outputs: Dict[str, Any] = {}
            step_status = "completed"
            err_msg: Optional[str] = None

            # Execute step according to type
            if s_type == StepType.DECISION.value:
                # Merge current flattened variables for condition
                cond_context = dict(context)
                for k, v in context.items():
                    if isinstance(v, dict):
                        cond_context.update(v)

                cond_val = evaluate_condition_safely(step.condition or "True", cond_context)
                step_outputs = {"condition_result": cond_val}

                # Mark the unchosen branch as skipped
                if cond_val:
                    if step.if_false and step.if_false in step_map:
                        skipped_steps.add(step.if_false)
                else:
                    if step.if_true and step.if_true in step_map:
                        skipped_steps.add(step.if_true)

            elif s_type in (StepType.DATABASE.value, StepType.RAG.value, StepType.NOTIFICATION.value, StepType.APPROVAL.value):
                tool_name = step.tool or s_type.lower()
                action = step.action or (
                    "search_knowledge" if tool_name == "rag"
                    else "create_notification" if tool_name == "notification"
                    else "request_approval" if tool_name == "approval"
                    else "get_equipment_request"
                )
                tools_used.add(tool_name)
                if tool_name == "approval":
                    approval_simulated = True
                    if "approver_role" not in interpolated_inputs:
                        interpolated_inputs["approver_role"] = step.approver_role or "manager"
                    if "request_summary" not in interpolated_inputs:
                        interpolated_inputs["request_summary"] = interpolated_inputs.get("summary") or step.description or "Approval request"

                res = self.registry.execute_tool(
                    tool_name=tool_name,
                    action=action,
                    inputs=interpolated_inputs,
                    is_simulation=True,
                    context=context,
                )
                if res.success:
                    step_outputs = res.data
                else:
                    step_status = "failed"
                    err_msg = res.error

            elif s_type == StepType.TRANSFORM.value:
                step_outputs = {"transformed_data": interpolated_inputs}

            elif s_type == StepType.END.value:
                step_outputs = {"status": "workflow_completed"}

            step_duration = int((time.perf_counter() - step_start) * 1000)

            # Record step result
            records.append(
                StepExecutionRecord(
                    step_id=step.id,
                    step_name=step.name,
                    step_type=s_type,
                    status=step_status,
                    inputs=interpolated_inputs,
                    outputs=step_outputs,
                    duration_ms=step_duration,
                    error=err_msg,
                )
            )

            if step_status == "completed":
                completed_steps.add(step.id)
                # Save step outputs into context for future steps
                context[step.id] = step_outputs
                for k, v in step_outputs.items():
                    context[k] = v
            else:
                break

        total_duration = int((time.perf_counter() - start_time) * 1000)
        overall_status = "completed" if all(r.status == "completed" for r in records) else "failed"

        return SimulationResult(
            workflow_id=workflow.workflow_id,
            status=overall_status,
            total_duration_ms=total_duration,
            steps_executed=records,
            tools_simulated=list(tools_used),
            final_outputs=context,
            approval_simulated=approval_simulated,
        )
