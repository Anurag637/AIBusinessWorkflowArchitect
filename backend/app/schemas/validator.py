"""
Deterministic validator for Workflow Definitions.
Enforces the 14 security and architectural validation rules specified in docs/workflow-schema.md.
"""

import re
from typing import List, Dict, Set, Any, Optional
from pydantic import BaseModel, Field
from collections import defaultdict, deque

from app.schemas.workflow import (
    WorkflowDefinition,
    WorkflowStep,
    StepType,
    AllowedTool,
)


class ValidationIssue(BaseModel):
    rule_number: int
    rule_name: str
    severity: str  # ERROR or WARNING
    message: str
    step_id: Optional[str] = None


class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)


# Forbidden patterns for security checks
PYTHON_EXEC_PATTERNS = [
    r"__import__",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"os\.system",
    r"subprocess\.",
    r"\blambda\s*:",
    r"\bopen\s*\(",
    r"__globals__",
    r"getattr\s*\(",
    r"__subclasses__",
]

RAW_SQL_PATTERNS = [
    r"\bSELECT\b[\s\S]+\bFROM\b",
    r"\bINSERT\s+INTO\b",
    r"\bUPDATE\b[\s\S]+\bSET\b",
    r"\bDELETE\s+FROM\b",
    r"\bDROP\s+TABLE\b",
    r"\bUNION\s+SELECT\b",
    r";\s*--",
]

URL_PATTERNS = [
    r"https?://",
    r"ftp://",
]

ALLOWED_TOOLS = {tool.value for tool in AllowedTool}


def _check_string_for_patterns(text: str, patterns: List[str]) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _inspect_values_recursively(data: Any, patterns: List[str]) -> List[str]:
    """Recursively search for matched forbidden patterns in dictionary/list values."""
    matches = []
    if isinstance(data, str):
        for pattern in patterns:
            if re.search(pattern, data, re.IGNORECASE):
                matches.append(data)
    elif isinstance(data, dict):
        for k, v in data.items():
            matches.extend(_inspect_values_recursively(v, patterns))
    elif isinstance(data, list):
        for item in data:
            matches.extend(_inspect_values_recursively(item, patterns))
    return matches


class DeterministicValidator:
    """Validator enforcing the 14 structural and security workflow rules."""

    def __init__(self, allowed_tools: Optional[Set[str]] = None):
        self.allowed_tools = allowed_tools or ALLOWED_TOOLS

    def validate(self, workflow: WorkflowDefinition) -> ValidationResult:
        errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []

        all_steps: List[Dict[str, Any]] = []
        
        # Add trigger as step representation
        trigger_id = workflow.trigger.id
        all_steps.append({
            "id": trigger_id,
            "type": StepType.TRIGGER.value,
            "dependencies": [],
            "raw": workflow.trigger.model_dump(),
        })

        for s in workflow.steps:
            all_steps.append({
                "id": s.id,
                "type": s.type.value if hasattr(s.type, "value") else str(s.type),
                "dependencies": s.dependencies or [],
                "raw": s.model_dump(),
                "step_obj": s,
            })

        step_map: Dict[str, Dict[str, Any]] = {}
        step_ids: List[str] = []

        # Rule 3: All step IDs must be unique
        for s in all_steps:
            sid = s["id"]
            if sid in step_map:
                errors.append(ValidationIssue(
                    rule_number=3,
                    rule_name="Unique Step IDs",
                    severity="ERROR",
                    message=f"Duplicate step ID found: '{sid}'",
                    step_id=sid,
                ))
            else:
                step_map[sid] = s
                step_ids.append(sid)

        # Rule 1: Exactly one TRIGGER step
        trigger_count = sum(1 for s in all_steps if s["type"] == StepType.TRIGGER.value)
        if trigger_count != 1:
            errors.append(ValidationIssue(
                rule_number=1,
                rule_name="Single Trigger",
                severity="ERROR",
                message=f"Workflow must have exactly one TRIGGER step, found {trigger_count}",
            ))

        # Rule 2: At least one END step
        end_count = sum(1 for s in all_steps if s["type"] == StepType.END.value)
        if end_count < 1:
            errors.append(ValidationIssue(
                rule_number=2,
                rule_name="End Step Required",
                severity="ERROR",
                message="Workflow must contain at least one END step",
            ))

        # Rule 4: All dependencies must reference existing step IDs
        for s in all_steps:
            for dep in s["dependencies"]:
                if dep not in step_map:
                    errors.append(ValidationIssue(
                        rule_number=4,
                        rule_name="Valid Dependencies",
                        severity="ERROR",
                        message=f"Step '{s['id']}' references non-existent dependency '{dep}'",
                        step_id=s["id"],
                    ))

        # Rule 5: Workflow graph must be acyclic (DAG)
        adj: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {sid: 0 for sid in step_ids}

        for s in all_steps:
            for dep in s["dependencies"]:
                if dep in in_degree:
                    adj[dep].append(s["id"])
                    in_degree[s["id"]] += 1

        # Also account for DECISION branches (if_true / if_false)
        for s in all_steps:
            step_obj = s.get("step_obj")
            if step_obj and step_obj.type == StepType.DECISION:
                for branch in [step_obj.if_true, step_obj.if_false]:
                    if branch and branch in in_degree:
                        if branch not in adj[s["id"]]:
                            adj[s["id"]].append(branch)
                            in_degree[branch] += 1

        q = deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited_count = 0
        while q:
            curr = q.popleft()
            visited_count += 1
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    q.append(neighbor)

        if visited_count < len(step_ids):
            errors.append(ValidationIssue(
                rule_number=5,
                rule_name="Acyclic Graph",
                severity="ERROR",
                message="Workflow contains cyclic dependencies (must be a DAG)",
            ))

        # Per-step validations
        for s in all_steps:
            sid = s["id"]
            raw = s["raw"]
            step_obj: Optional[WorkflowStep] = s.get("step_obj")

            # Rule 6: Step types must be in allowlist
            valid_types = {t.value for t in StepType}
            if s["type"] not in valid_types:
                errors.append(ValidationIssue(
                    rule_number=6,
                    rule_name="Allowlisted Step Types",
                    severity="ERROR",
                    message=f"Step '{sid}' has invalid type '{s['type']}'",
                    step_id=sid,
                ))

            # Rule 7: Tool names must come from Tool Registry
            if step_obj and step_obj.tool is not None:
                if step_obj.tool not in self.allowed_tools:
                    errors.append(ValidationIssue(
                        rule_number=7,
                        rule_name="Tool Registry Membership",
                        severity="ERROR",
                        message=f"Step '{sid}' uses unapproved tool '{step_obj.tool}'",
                        step_id=sid,
                    ))

            # Rule 9: No executable Python
            py_matches = _inspect_values_recursively(raw, PYTHON_EXEC_PATTERNS)
            if py_matches:
                errors.append(ValidationIssue(
                    rule_number=9,
                    rule_name="No Executable Python",
                    severity="ERROR",
                    message=f"Step '{sid}' contains potentially unsafe Python code",
                    step_id=sid,
                ))

            # Rule 10: No raw SQL
            sql_matches = _inspect_values_recursively(raw, RAW_SQL_PATTERNS)
            if sql_matches:
                errors.append(ValidationIssue(
                    rule_number=10,
                    rule_name="No Raw SQL",
                    severity="ERROR",
                    message=f"Step '{sid}' contains forbidden raw SQL query statements",
                    step_id=sid,
                ))

            # Rule 11: No arbitrary HTTP URLs
            url_matches = _inspect_values_recursively(raw, URL_PATTERNS)
            if url_matches:
                errors.append(ValidationIssue(
                    rule_number=11,
                    rule_name="No Arbitrary URLs",
                    severity="ERROR",
                    message=f"Step '{sid}' contains arbitrary HTTP/FTP URLs",
                    step_id=sid,
                ))

            # Rule 12: APPROVAL steps must specify approver_role
            if step_obj and step_obj.type == StepType.APPROVAL:
                if not step_obj.approver_role:
                    errors.append(ValidationIssue(
                        rule_number=12,
                        rule_name="Approval Role Required",
                        severity="ERROR",
                        message=f"Approval step '{sid}' must specify 'approver_role'",
                        step_id=sid,
                    ))

            # Rule 13: DECISION steps must have condition, if_true, if_false
            if step_obj and step_obj.type == StepType.DECISION:
                if not step_obj.condition or not step_obj.if_true or not step_obj.if_false:
                    errors.append(ValidationIssue(
                        rule_number=13,
                        rule_name="Decision Fields Required",
                        severity="ERROR",
                        message=f"Decision step '{sid}' must specify condition, if_true, and if_false",
                        step_id=sid,
                    ))
                else:
                    if step_obj.if_true not in step_map:
                        errors.append(ValidationIssue(
                            rule_number=13,
                            rule_name="Decision Branch Exists",
                            severity="ERROR",
                            message=f"Decision step '{sid}' if_true targets non-existent step '{step_obj.if_true}'",
                            step_id=sid,
                        ))
                    if step_obj.if_false not in step_map:
                        errors.append(ValidationIssue(
                            rule_number=13,
                            rule_name="Decision Branch Exists",
                            severity="ERROR",
                            message=f"Decision step '{sid}' if_false targets non-existent step '{step_obj.if_false}'",
                            step_id=sid,
                        ))

        # Rule 8: Required inputs defined or referenced
        defined_inputs = {inp.name for inp in workflow.inputs}
        defined_outputs = {trigger_id: set(workflow.trigger.outputs)}
        for s in workflow.steps:
            defined_outputs[s.id] = set(s.outputs)

        var_pattern = re.compile(r"\{\{([a-zA-Z0-9_\.]+)\}\}")
        for s in workflow.steps:
            for val in _inspect_values_recursively(s.inputs, [r"\{\{"]):
                for match in var_pattern.findall(val):
                    parts = match.split(".")
                    source = parts[0]
                    if source == "trigger":
                        field = parts[1] if len(parts) > 1 else None
                        if field and field not in defined_inputs and field not in defined_outputs.get(trigger_id, set()):
                            warnings.append(ValidationIssue(
                                rule_number=8,
                                rule_name="Input Variable Reference",
                                severity="WARNING",
                                message=f"Step '{s.id}' references undefined trigger field '{field}'",
                                step_id=s.id,
                            ))
                    elif source in defined_outputs:
                        if source not in s.dependencies:
                            warnings.append(ValidationIssue(
                                rule_number=8,
                                rule_name="Undeclared Dependency",
                                severity="WARNING",
                                message=f"Step '{s.id}' references output of '{source}' but does not declare it as dependency",
                                step_id=s.id,
                            ))

        # Rule 14: All execution paths must reach an END node
        # Build forward graph
        forward_graph: Dict[str, List[str]] = defaultdict(list)
        for s in all_steps:
            for dep in s["dependencies"]:
                forward_graph[dep].append(s["id"])
            step_obj = s.get("step_obj")
            if step_obj and step_obj.type == StepType.DECISION:
                if step_obj.if_true and step_obj.if_true not in forward_graph[s["id"]]:
                    forward_graph[s["id"]].append(step_obj.if_true)
                if step_obj.if_false and step_obj.if_false not in forward_graph[s["id"]]:
                    forward_graph[s["id"]].append(step_obj.if_false)

        end_step_ids = {s["id"] for s in all_steps if s["type"] == StepType.END.value}

        # Check reachability to at least one END node from each step
        for s in all_steps:
            sid = s["id"]
            if sid in end_step_ids:
                continue
            reachable_end = False
            visited_nodes = set()
            stack = [sid]
            while stack:
                curr = stack.pop()
                if curr in end_step_ids:
                    reachable_end = True
                    break
                if curr not in visited_nodes:
                    visited_nodes.add(curr)
                    stack.extend(forward_graph.get(curr, []))
            if not reachable_end:
                warnings.append(ValidationIssue(
                    rule_number=14,
                    rule_name="Path to End Node",
                    severity="WARNING",
                    message=f"Step '{sid}' cannot reach any END step",
                    step_id=sid,
                ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
