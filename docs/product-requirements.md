# AI Business Workflow Architect — Product Requirements

## 1. Problem Statement

Companies receive business requirements in natural language, such as:

> "When an employee submits an equipment request, check company policy. Requests below ₹25,000 can be processed by IT after policy verification. Requests above ₹25,000 require manager approval."

Currently, converting such requirements into executable workflows requires manual effort from developers and business analysts who must:

1. Understand the requirement
2. Break it into steps
3. Identify which systems/tools are needed
4. Define approval rules
5. Build the workflow
6. Test it
7. Deploy it

This process is time-consuming, error-prone, and doesn't scale.

## 2. Target Users

| User Role | Usage |
|-----------|-------|
| Business Analyst | Enters natural-language requirements, reviews generated workflows |
| Manager | Reviews and approves workflows, approves equipment requests |
| IT Administrator | Monitors workflow execution, manages knowledge base |
| System Administrator | Deploys and configures the platform |

## 3. Primary Use Case (MVP)

**Employee Equipment Request Workflow**

A fictional company needs to automate the process of handling employee equipment requests. The system should:

1. Accept natural-language business requirements
2. Analyze and decompose the requirement
3. Generate a structured workflow
4. Retrieve relevant company policies (RAG)
5. Validate the workflow
6. Allow human approval
7. Simulate the workflow safely
8. Execute the workflow with controlled tools
9. Record complete audit trail

## 4. User Journey

```
1. User opens Dashboard
       │
2. User clicks "Create Workflow"
       │
3. User enters business requirement in natural language
       │
4. System analyzes requirement → displays structured analysis
       │
5. User reviews analysis → proceeds
       │
6. System decomposes into process steps → displays process plan
       │
7. System generates workflow with tool assignments → displays visual workflow
       │
8. System validates workflow → displays validation results
       │
9. User runs simulation → views step-by-step dry run
       │
10. System requests human approval → user approves/rejects/modifies
       │
11. System executes workflow → displays real-time progress
       │
12. User views execution details and audit logs
```

## 5. Functional Requirements

### FR-01: Requirement Analysis
- Accept natural-language business requirements
- Extract: goal, actors, trigger, inputs, business rules, constraints, risks, missing information
- Return structured analysis (not free-form text)
- Identify ambiguity and request clarification

### FR-02: Process Decomposition
- Convert requirement analysis into logical process steps
- Identify: trigger, tasks, decisions, dependencies, human interventions
- Describe WHAT needs to happen, not HOW (no tool selection yet)

### FR-03: Workflow Generation
- Convert process plan into structured workflow JSON
- Map business steps to controlled tools (Database, RAG, Notification, Approval)
- Produce strict schema-compliant output
- Support conditional branching (decision nodes)

### FR-04: Knowledge Retrieval (RAG)
- Index company policy documents
- Semantic search using Qdrant
- Return relevant policy chunks with source attribution
- Support metadata filtering

### FR-05: Workflow Validation
- Deterministic validation: schema, structure, security (FINAL AUTHORITY)
- Semantic LLM validation: business logic, completeness (advisory)
- Return structured results: valid/invalid, errors, warnings, findings
- Block invalid workflows from simulation/execution

### FR-06: Simulation
- Execute workflow in sandbox mode
- No real side effects
- Record every step: input, output, status, timing
- Pause at approval steps
- Display step-by-step results

### FR-07: Human Approval
- Create approval requests for workflows requiring human review
- Support states: PENDING, APPROVED, REJECTED, MODIFICATION_REQUESTED
- Modification creates new workflow version requiring revalidation
- All approval actions recorded in audit log

### FR-08: Workflow Execution
- Execute validated and approved workflows
- Use Tool Registry for all tool calls
- Handle retries, timeouts, failures
- Pause at approval steps
- Record complete execution trace

### FR-09: Audit Logging
- Record all significant actions
- Immutable from normal operations
- Structured metadata (JSON)
- Filterable and searchable in UI

### FR-10: Dashboard
- Display workflow counts, execution stats, pending approvals
- Recent workflows and activity
- Navigation to all features

## 6. Non-Functional Requirements

### NFR-01: Security
- LLM restricted to planning/reasoning only
- No arbitrary code/SQL/HTTP execution
- Allowlisted tools with schema validation
- Human approval for sensitive operations
- Prompt injection protection
- Secret management through environment variables

### NFR-02: Reliability
- Graceful error handling at every layer
- Retry logic for transient failures
- Clear error messages for users
- Execution state tracking for recovery

### NFR-03: Observability
- Structured logging
- Execution traces
- Dashboard metrics
- Security event logging

### NFR-04: Maintainability
- Clear separation of concerns (layered architecture)
- Typed interfaces (Pydantic schemas)
- Configurable LLM and embedding providers
- Database migrations (Alembic)

### NFR-05: Usability
- Responsive web UI
- Loading, error, and empty states
- Clear workflow visualization
- Step-by-step simulation display
- Accessible approval interface

## 7. MVP Scope

### In Scope
- Single business domain: Employee Equipment Request
- 4 AI agents (Analyzer, Decomposer, Architect, Validator)
- 4 controlled tools (Database, RAG, Notification, Approval)
- RAG with Qdrant (fictional policy documents)
- Workflow validation (deterministic + semantic)
- Simulation mode
- Human approval system
- Execution engine
- Audit logging
- Web UI (10 pages)
- Docker deployment

### Out of Scope (Future)
- Drag-and-drop workflow editing
- Additional tool integrations
- OAuth / SSO authentication
- Multi-tenant support
- Workflow versioning UI
- Automatic test-case generation
- Agent performance metrics dashboard
- Cost tracking
- Advanced observability (distributed tracing)
- Workflow templates library
- Real email/SMS notifications
- Multiple business domains

## 8. Security Requirements

See `security-model.md` for complete security specification.

Key principles:
1. **LLM plans; backend controls execution**
2. **Allowlisted tools only**
3. **Schema-validated inputs/outputs**
4. **Human approval for sensitive actions**
5. **Deterministic validation has final authority**
6. **Complete audit trail**
7. **No secrets in code or logs**
