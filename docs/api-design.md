# AI Business Workflow Architect — API Design

## Base URL

```
/api/v1
```

## Authentication

MVP uses a simple authorization abstraction. Full JWT authentication is deferred but the interface is prepared.

```
Authorization: Bearer <token>
```

## Response Format

### Success
```json
{
  "status": "success",
  "data": { ... },
  "message": "Optional success message"
}
```

### Error
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  }
}
```

---

## API Groups

### 1. Health

#### `GET /health`

Check backend health and service connectivity.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "qdrant": "connected",
    "llm": "available"
  }
}
```

---

### 2. Requirements

#### `POST /api/v1/requirements/analyze`

Analyze a natural-language business requirement.

**Request:**
```json
{
  "requirement": "When an employee submits an equipment request, check company policy. Requests below ₹25,000 can be processed by IT after policy verification. Requests above ₹25,000 require manager approval."
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "analysis_id": "uuid",
    "business_goal": "Automate employee equipment request approval process",
    "actors": [
      {"name": "Employee", "role": "requester"},
      {"name": "IT Team", "role": "processor"},
      {"name": "Manager", "role": "approver"}
    ],
    "trigger": "Employee submits equipment request",
    "inputs": [
      {"name": "equipment_request", "type": "form_submission"}
    ],
    "business_rules": [
      "Requests below ₹25,000 processed by IT after policy verification",
      "Requests above ₹25,000 require manager approval"
    ],
    "expected_outcome": "Equipment request is either processed by IT or approved by manager",
    "constraints": ["Must check company policy before processing"],
    "potential_risks": ["Policy changes not reflected in real-time"],
    "missing_information": []
  }
}
```

---

### 3. Process

#### `POST /api/v1/process/decompose`

Decompose an analyzed requirement into a process plan.

**Request:**
```json
{
  "analysis_id": "uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "plan_id": "uuid",
    "analysis_id": "uuid",
    "trigger": {
      "event": "equipment_request_submitted",
      "description": "Employee submits equipment request"
    },
    "tasks": [
      {
        "id": "task_1",
        "name": "Retrieve equipment request",
        "description": "Get the submitted equipment request details",
        "required_inputs": ["request_id"],
        "expected_output": "request_details"
      }
    ],
    "decisions": [
      {
        "id": "decision_1",
        "condition": "Request cost compared to ₹25,000 threshold",
        "true_path": "Notify IT for processing",
        "false_path": "Request manager approval"
      }
    ],
    "dependencies": {
      "task_1": [],
      "task_2": ["task_1"],
      "decision_1": ["task_1", "task_2"]
    },
    "human_interventions": [
      {
        "step": "Manager approval",
        "condition": "Equipment cost exceeds ₹25,000"
      }
    ]
  }
}
```

---

### 4. Workflows

#### `POST /api/v1/workflows/generate`

Generate a workflow from a process plan.

**Request:**
```json
{
  "plan_id": "uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "workflow_id": "uuid",
    "version_id": "uuid",
    "workflow_definition": { ... }
  }
}
```

#### `GET /api/v1/workflows`

List all workflows.

**Query Parameters:**
- `status` (optional): Filter by status
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 20)

**Response:**
```json
{
  "status": "success",
  "data": {
    "workflows": [
      {
        "id": "uuid",
        "name": "Equipment Request Approval",
        "status": "VALIDATED",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 1
    }
  }
}
```

#### `GET /api/v1/workflows/{workflow_id}`

Get a specific workflow with its current version.

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "name": "Equipment Request Approval",
    "description": "...",
    "status": "VALIDATED",
    "current_version": {
      "id": "uuid",
      "version_number": 1,
      "workflow_definition": { ... },
      "validation_status": "VALID",
      "created_at": "2024-01-01T00:00:00Z"
    },
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### `POST /api/v1/workflows/{workflow_id}/validate`

Validate a workflow.

**Response:**
```json
{
  "status": "success",
  "data": {
    "valid": true,
    "errors": [],
    "warnings": [
      {
        "code": "W001",
        "message": "Consider adding error handling for database retrieval failure",
        "step_id": "step_1"
      }
    ],
    "semantic_findings": [
      {
        "finding": "Workflow correctly implements the ₹25,000 threshold for approval routing",
        "severity": "info"
      }
    ]
  }
}
```

#### `POST /api/v1/workflows/{workflow_id}/simulate`

Run a workflow in simulation mode.

**Request:**
```json
{
  "simulation_inputs": {
    "request_id": "REQ-104",
    "employee_id": "EMP-001"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "execution_id": "uuid",
    "mode": "simulation",
    "status": "COMPLETED",
    "steps": [
      {
        "step_id": "step_1",
        "step_name": "Retrieve equipment request",
        "step_type": "database",
        "status": "COMPLETED",
        "input": {"request_id": "REQ-104"},
        "output": {"item": "Laptop", "cost": 32000},
        "started_at": "2024-01-01T00:00:01Z",
        "completed_at": "2024-01-01T00:00:01Z"
      }
    ]
  }
}
```

#### `POST /api/v1/workflows/{workflow_id}/execute`

Execute a validated and approved workflow.

**Request:**
```json
{
  "execution_inputs": {
    "request_id": "REQ-104",
    "employee_id": "EMP-001"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "execution_id": "uuid",
    "mode": "execution",
    "status": "RUNNING"
  }
}
```

---

### 5. Knowledge

#### `POST /api/v1/knowledge/index`

Index knowledge documents into Qdrant.

**Request:**
```json
{
  "directory": "knowledge/policies"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "documents_indexed": 4,
    "chunks_created": 24,
    "collection": "company_knowledge"
  }
}
```

#### `POST /api/v1/knowledge/search`

Search knowledge base.

**Request:**
```json
{
  "query": "What is the approval limit for equipment purchases?",
  "top_k": 5
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "results": [
      {
        "text": "Equipment purchases exceeding ₹25,000 require manager approval...",
        "document": "equipment_policy.md",
        "source_id": "chunk_uuid",
        "relevance_score": 0.92,
        "metadata": {
          "title": "Equipment Policy",
          "section": "Approval Requirements"
        }
      }
    ]
  }
}
```

---

### 6. Executions

#### `GET /api/v1/executions/{execution_id}`

Get execution details with all steps.

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "workflow_id": "uuid",
    "mode": "execution",
    "status": "COMPLETED",
    "started_at": "2024-01-01T00:00:00Z",
    "completed_at": "2024-01-01T00:00:05Z",
    "steps": [
      {
        "step_id": "step_1",
        "step_name": "Retrieve equipment request",
        "step_type": "database",
        "status": "COMPLETED",
        "input": { ... },
        "output": { ... },
        "started_at": "...",
        "completed_at": "...",
        "retry_count": 0
      }
    ]
  }
}
```

---

### 7. Approvals

#### `GET /api/v1/approvals`

List pending approval requests.

**Query Parameters:**
- `status` (optional): Filter by status (PENDING, APPROVED, REJECTED, MODIFICATION_REQUESTED)

**Response:**
```json
{
  "status": "success",
  "data": {
    "approvals": [
      {
        "id": "uuid",
        "workflow_execution_id": "uuid",
        "step_id": "step_5",
        "status": "PENDING",
        "requested_by": "system",
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

#### `GET /api/v1/approvals/{approval_id}`

Get a specific approval request.

#### `POST /api/v1/approvals/{approval_id}/approve`

Approve a request.

**Request:**
```json
{
  "comments": "Approved for procurement."
}
```

#### `POST /api/v1/approvals/{approval_id}/reject`

Reject a request.

**Request:**
```json
{
  "comments": "Budget exceeded for this quarter."
}
```

#### `POST /api/v1/approvals/{approval_id}/modify`

Request modification.

**Request:**
```json
{
  "comments": "Manager approval should be required for amounts above ₹25,000, not ₹50,000.",
  "modification_details": "Update threshold from ₹50,000 to ₹25,000"
}
```

---

### 8. Audit

#### `GET /api/v1/audit`

Get audit log entries.

**Query Parameters:**
- `resource_type` (optional): Filter by resource type (workflow, execution, approval)
- `resource_id` (optional): Filter by resource ID
- `action` (optional): Filter by action
- `from_date` (optional): Start date
- `to_date` (optional): End date
- `page` (optional): Page number
- `per_page` (optional): Items per page

**Response:**
```json
{
  "status": "success",
  "data": {
    "entries": [
      {
        "id": "uuid",
        "actor_type": "user",
        "actor_id": "user_uuid",
        "action": "workflow.approved",
        "resource_type": "workflow",
        "resource_id": "workflow_uuid",
        "metadata": {
          "comments": "Approved for procurement."
        },
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 42
    }
  }
}
```

---

### 9. Dashboard Metrics

#### `GET /api/v1/dashboard/metrics`

Get dashboard summary metrics.

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_workflows": 5,
    "active_executions": 1,
    "pending_approvals": 2,
    "completed_executions": 12,
    "failed_executions": 1,
    "recent_workflows": [ ... ],
    "recent_activity": [ ... ]
  }
}
```
