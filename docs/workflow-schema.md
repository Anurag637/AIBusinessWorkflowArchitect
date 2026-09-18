# AI Business Workflow Architect — Workflow Schema

## Overview

The Workflow Schema is the **core data contract** between all system components:
- Agents produce it
- Validator checks it
- Simulator dry-runs it
- Executor runs it
- Frontend displays it

This schema must be strict, unambiguous, and secure.

---

## WorkflowDefinition

The top-level workflow object.

```json
{
  "workflow_id": "uuid",
  "name": "Equipment Request Approval",
  "description": "Automated workflow for processing employee equipment requests",
  "version": 1,
  "trigger": {
    "id": "trigger_1",
    "type": "TRIGGER",
    "event": "equipment_request_created",
    "description": "Employee submits equipment request",
    "outputs": ["request_id", "employee_id"]
  },
  "inputs": [
    {
      "name": "request_id",
      "type": "string",
      "required": true,
      "description": "The equipment request identifier"
    },
    {
      "name": "employee_id",
      "type": "string",
      "required": true,
      "description": "The requesting employee identifier"
    }
  ],
  "steps": [ ... ],
  "metadata": {
    "created_by": "workflow_architect_agent",
    "domain": "equipment_management",
    "estimated_duration_seconds": 300
  },
  "required_approvals": [
    {
      "step_id": "step_5",
      "approver_role": "manager",
      "condition": "Equipment cost exceeds ₹25,000"
    }
  ]
}
```

---

## WorkflowStep

Each step in the workflow.

```json
{
  "id": "step_1",
  "name": "Retrieve Equipment Request",
  "type": "DATABASE",
  "description": "Fetch the equipment request details from the database",
  "tool": "database",
  "action": "get_equipment_request",
  "inputs": {
    "request_id": "{{trigger.request_id}}"
  },
  "outputs": ["request_details"],
  "dependencies": ["trigger_1"],
  "configuration": {},
  "timeout_seconds": 30,
  "retry_config": {
    "max_retries": 2,
    "retry_delay_seconds": 5
  }
}
```

---

## Allowed Step Types

| Type | Purpose | Tool Required |
|------|---------|--------------|
| `TRIGGER` | Entry point of the workflow | No |
| `DATABASE` | Read/write business data | DatabaseTool |
| `RAG` | Search knowledge base | RAGTool |
| `DECISION` | Conditional branching | No |
| `NOTIFICATION` | Send notifications | NotificationTool |
| `APPROVAL` | Request human approval | HumanApprovalTool |
| `TRANSFORM` | Data transformation (no external calls) | No |
| `END` | Workflow termination | No |

**No other step types are allowed.** Any step with a type not in this list must be rejected by the validator.

---

## Step Type Specifications

### TRIGGER
```json
{
  "id": "trigger_1",
  "type": "TRIGGER",
  "event": "equipment_request_created",
  "description": "Employee submits equipment request",
  "outputs": ["request_id", "employee_id"]
}
```
- Exactly **one** TRIGGER per workflow
- Must be the entry point (no dependencies)
- Defines the event that starts the workflow

### DATABASE
```json
{
  "id": "step_1",
  "type": "DATABASE",
  "tool": "database",
  "action": "get_equipment_request",
  "inputs": {"request_id": "{{trigger.request_id}}"},
  "outputs": ["request_details"],
  "dependencies": ["trigger_1"]
}
```
- Allowed actions: `get_employee`, `get_equipment_request`, `record_decision`
- **No raw SQL allowed**
- Inputs must be parameterized references

### RAG
```json
{
  "id": "step_2",
  "type": "RAG",
  "tool": "rag",
  "action": "search_knowledge",
  "inputs": {"query": "equipment approval policy and spending limits"},
  "outputs": ["policy_info"],
  "dependencies": ["step_1"]
}
```
- Allowed actions: `search_knowledge`
- Returns policy text with source attribution

### DECISION
```json
{
  "id": "step_3",
  "type": "DECISION",
  "description": "Check if equipment cost exceeds approval threshold",
  "condition": "request_details.cost < 25000",
  "if_true": "step_4",
  "if_false": "step_5",
  "dependencies": ["step_1", "step_2"]
}
```
- Must have `condition`, `if_true`, `if_false`
- Both branches must reference valid step IDs
- Condition is evaluated by the execution engine (not the LLM at runtime)

### NOTIFICATION
```json
{
  "id": "step_4",
  "type": "NOTIFICATION",
  "tool": "notification",
  "action": "create_notification",
  "inputs": {
    "recipient": "it_team",
    "subject": "Equipment Request Approved",
    "message": "Equipment request {{request_details.id}} has been approved for processing."
  },
  "dependencies": ["step_3"]
}
```
- Allowed actions: `create_notification`
- Notifications are simulated (stored in DB) for MVP

### APPROVAL
```json
{
  "id": "step_5",
  "type": "APPROVAL",
  "tool": "approval",
  "action": "request_approval",
  "approver_role": "manager",
  "inputs": {
    "request_summary": "Equipment request for {{request_details.item}} costing ₹{{request_details.cost}}"
  },
  "dependencies": ["step_3"]
}
```
- Allowed actions: `request_approval`, `check_approval`
- Must specify `approver_role`
- Execution engine pauses here until approval is received

### TRANSFORM
```json
{
  "id": "step_6",
  "type": "TRANSFORM",
  "description": "Format decision record",
  "transform": {
    "operation": "merge",
    "fields": ["request_details", "policy_info", "approval_result"]
  },
  "outputs": ["decision_record"],
  "dependencies": ["step_4", "step_5"]
}
```
- Pure data transformation, no external calls
- No arbitrary code execution
- Predefined operations only

### END
```json
{
  "id": "end_1",
  "type": "END",
  "description": "Workflow completed",
  "dependencies": ["step_6"]
}
```
- Every workflow must have at least one END node
- All execution paths must terminate at an END node

---

## Variable References

Variables use mustache-style template syntax:

- `{{trigger.request_id}}` — References trigger output
- `{{step_1.request_details}}` — References a previous step's output
- `{{step_1.request_details.cost}}` — Nested field reference

Variable references can only access outputs of completed dependency steps.

---

## Complete Example Workflow

```json
{
  "workflow_id": "wf-001",
  "name": "Equipment Request Approval",
  "description": "Automated workflow for processing employee equipment requests with policy verification and conditional approval routing",
  "version": 1,
  "trigger": {
    "id": "trigger_1",
    "type": "TRIGGER",
    "event": "equipment_request_created",
    "description": "Employee submits equipment request",
    "outputs": ["request_id", "employee_id"]
  },
  "inputs": [
    {"name": "request_id", "type": "string", "required": true},
    {"name": "employee_id", "type": "string", "required": true}
  ],
  "steps": [
    {
      "id": "step_1",
      "name": "Retrieve Equipment Request",
      "type": "DATABASE",
      "tool": "database",
      "action": "get_equipment_request",
      "description": "Fetch equipment request details",
      "inputs": {"request_id": "{{trigger.request_id}}"},
      "outputs": ["request_details"],
      "dependencies": ["trigger_1"],
      "timeout_seconds": 30,
      "retry_config": {"max_retries": 2, "retry_delay_seconds": 5}
    },
    {
      "id": "step_2",
      "name": "Check Equipment Policy",
      "type": "RAG",
      "tool": "rag",
      "action": "search_knowledge",
      "description": "Retrieve equipment approval policy",
      "inputs": {"query": "equipment approval policy spending limits"},
      "outputs": ["policy_info"],
      "dependencies": ["step_1"],
      "timeout_seconds": 30
    },
    {
      "id": "step_3",
      "name": "Evaluate Cost Threshold",
      "type": "DECISION",
      "description": "Check if equipment cost is below approval threshold",
      "condition": "request_details.cost < 25000",
      "if_true": "step_4",
      "if_false": "step_5",
      "dependencies": ["step_1", "step_2"]
    },
    {
      "id": "step_4",
      "name": "Notify IT Team",
      "type": "NOTIFICATION",
      "tool": "notification",
      "action": "create_notification",
      "description": "Notify IT team to process the equipment request",
      "inputs": {
        "recipient": "it_team",
        "subject": "Equipment Request Ready for Processing",
        "message": "Equipment request for {{step_1.request_details.item}} has been policy-verified and is ready for processing."
      },
      "outputs": ["notification_result"],
      "dependencies": ["step_3"]
    },
    {
      "id": "step_5",
      "name": "Request Manager Approval",
      "type": "APPROVAL",
      "tool": "approval",
      "action": "request_approval",
      "description": "Request manager approval for high-value equipment",
      "approver_role": "manager",
      "inputs": {
        "request_summary": "Equipment: {{step_1.request_details.item}}, Cost: ₹{{step_1.request_details.cost}}, Employee: {{step_1.request_details.employee_name}}"
      },
      "outputs": ["approval_result"],
      "dependencies": ["step_3"]
    },
    {
      "id": "step_6",
      "name": "Record Decision",
      "type": "DATABASE",
      "tool": "database",
      "action": "record_decision",
      "description": "Record the approval decision in the database",
      "inputs": {
        "request_id": "{{trigger.request_id}}",
        "decision": "{{step_4.notification_result || step_5.approval_result}}",
        "policy_reference": "{{step_2.policy_info.source}}"
      },
      "outputs": ["decision_record"],
      "dependencies": ["step_4", "step_5"]
    },
    {
      "id": "end_1",
      "name": "Process Complete",
      "type": "END",
      "description": "Equipment request workflow completed",
      "dependencies": ["step_6"]
    }
  ],
  "metadata": {
    "created_by": "workflow_architect_agent",
    "domain": "equipment_management",
    "estimated_duration_seconds": 300
  },
  "required_approvals": [
    {
      "step_id": "step_5",
      "approver_role": "manager",
      "condition": "Equipment cost exceeds ₹25,000"
    }
  ]
}
```

---

## Validation Rules

The following rules are enforced by the deterministic validator:

| # | Rule | Severity |
|---|------|----------|
| 1 | Exactly one TRIGGER step | ERROR |
| 2 | At least one END step | ERROR |
| 3 | All step IDs must be unique | ERROR |
| 4 | All dependencies must reference existing step IDs | ERROR |
| 5 | Workflow graph must be acyclic (DAG) | ERROR |
| 6 | Step types must be in the allowlist | ERROR |
| 7 | Tool names must come from Tool Registry | ERROR |
| 8 | Required inputs must be defined or referenced | ERROR |
| 9 | No executable Python in any field | ERROR |
| 10 | No raw SQL in any field | ERROR |
| 11 | No arbitrary HTTP URLs in any field | ERROR |
| 12 | APPROVAL steps must specify approver_role | ERROR |
| 13 | DECISION steps must have condition, if_true, if_false | ERROR |
| 14 | All execution paths must reach an END node | WARNING |
