# AI Business Workflow Architect — System Architecture

## 1. System Overview

AI Business Workflow Architect is an agentic AI platform that converts natural-language business requirements into structured, validated, simulated, and executable business workflows. It is designed as an enterprise-grade system with strict security boundaries, human-in-the-loop approval, and complete audit logging.

```
                        USER
                          │
                          ▼
                  ┌───────────────┐
                  │  Next.js UI   │
                  │  (TypeScript) │
                  └───────┬───────┘
                          │ REST API (JSON)
                          ▼
                  ┌───────────────┐
                  │   FastAPI     │
                  │   (Python)   │
                  └───────┬───────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌──────────┐ ┌────────┐ ┌──────────┐
        │ LangGraph│ │  Tool  │ │ Workflow │
        │  Agents  │ │Registry│ │  Engine  │
        └────┬─────┘ └───┬────┘ └────┬─────┘
             │           │           │
    ┌────────┼────────┐  │  ┌────────┼────────┐
    ▼        ▼        ▼  ▼  ▼        ▼        ▼
Requirement Process Workflow DB   Simulation Execution
 Analyzer  Decomposer Architect Tool  Engine    Engine
                                │
                          ┌─────┼─────┐
                          ▼     ▼     ▼
                        RAG  Notify Approval
                        Tool  Tool   Tool
                          │
                          ▼
                  ┌───────────────┐
                  │    Qdrant     │
                  │  (Vectors)   │
                  └───────────────┘

                  ┌───────────────┐
                  │  PostgreSQL   │
                  │  (Relational) │
                  └───────────────┘

                  ┌───────────────┐
                  │  Audit Log    │
                  └───────────────┘
```

---

## 2. Frontend Architecture

### Technology
- **Framework**: Next.js (App Router)
- **Language**: TypeScript
- **Styling**: Modern CSS with responsive design
- **API Communication**: Typed REST client

### Pages
| Page | Purpose |
|------|---------|
| Dashboard | Overview: workflows, executions, approvals, activity |
| Create Workflow | Natural-language requirement input |
| Requirement Analysis | Structured analysis display |
| Workflow Designer | Visual workflow graph |
| Validation Results | Validation checks display |
| Simulation | Step-by-step dry-run results |
| Approval Center | Pending human approvals |
| Execution Details | Execution progress and logs |
| Knowledge Base | Indexed documents and search |
| Audit Logs | Complete audit trail |

### Frontend-Backend Contract
- All data flows through REST API (`/api/v1/...`)
- Typed request/response schemas
- No direct database access from frontend
- Loading, error, and empty states for all views

---

## 3. Backend Architecture

### Technology
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **ORM**: SQLAlchemy 2.0 (async-compatible)
- **Migrations**: Alembic
- **Validation**: Pydantic v2

### Layer Structure

```
┌─────────────────────────────────────────┐
│              API Layer                   │
│   (FastAPI routers, request handling)    │
├─────────────────────────────────────────┤
│            Service Layer                 │
│   (Business logic, orchestration)       │
├─────────────────────────────────────────┤
│            Agent Layer                   │
│   (LangGraph agents, LLM interaction)  │
├─────────────────────────────────────────┤
│            Tool Layer                    │
│   (Tool Registry, controlled tools)     │
├─────────────────────────────────────────┤
│           Engine Layer                   │
│   (Validator, Simulator, Executor)      │
├─────────────────────────────────────────┤
│         Repository Layer                 │
│   (Database access, data persistence)   │
├─────────────────────────────────────────┤
│          Infrastructure                  │
│   (PostgreSQL, Qdrant, LLM provider)    │
└─────────────────────────────────────────┘
```

### API Versioning
- All API endpoints prefixed with `/api/v1/`
- Consistent error response format
- OpenAPI documentation auto-generated

---

## 4. Agent Architecture

### Agent Orchestration: LangGraph

LangGraph provides a graph-based orchestration framework for the 4 agents. Each agent is a node in the processing graph with clearly defined inputs and outputs.

```
                    Requirement (text)
                          │
                          ▼
               ┌─────────────────────┐
               │ Requirement Analyzer│
               │      Agent          │
               └──────────┬──────────┘
                          │ RequirementAnalysis
                          ▼
               ┌─────────────────────┐
               │ Process Decomposer  │
               │      Agent          │
               └──────────┬──────────┘
                          │ ProcessPlan
                          ▼
               ┌─────────────────────┐
               │ Workflow Architect   │
               │      Agent          │
               └──────────┬──────────┘
                          │ WorkflowDefinition
                          ▼
               ┌─────────────────────┐
               │ Workflow Validator   │
               │      Agent          │
               └──────────┬──────────┘
                          │ ValidationResult
                          ▼
                   Valid / Invalid
```

### Agent 1: Requirement Analyzer
- **Input**: Raw business requirement text
- **Output**: `RequirementAnalysis` (goal, actors, trigger, inputs, rules, constraints, risks, missing info)
- **Restrictions**: No tool execution, no database access, no workflow generation
- **Purpose**: Understand WHAT the user wants

### Agent 2: Process Decomposer
- **Input**: `RequirementAnalysis`
- **Output**: `ProcessPlan` (trigger, tasks, decisions, dependencies, human interventions)
- **Restrictions**: No tool selection, no code generation
- **Purpose**: Define WHAT needs to happen (not HOW)

### Agent 3: Workflow Architect
- **Input**: `ProcessPlan`
- **Output**: `WorkflowDefinition` (structured JSON matching workflow schema)
- **Restrictions**: Can only use allowlisted tools from Tool Registry
- **Purpose**: Map business steps to controlled tools

### Agent 4: Workflow Validator
- **Layer 1**: Deterministic validation (schema, structure, security) — has FINAL AUTHORITY
- **Layer 2**: Semantic LLM validation (business logic, completeness)
- **Input**: `WorkflowDefinition`
- **Output**: `ValidationResult` (valid/invalid, errors, warnings, semantic findings)

### LangGraph Graph Definition

```python
# Conceptual graph structure
graph = StateGraph(WorkflowState)

graph.add_node("analyze", requirement_analyzer)
graph.add_node("decompose", process_decomposer)
graph.add_node("architect", workflow_architect)
graph.add_node("validate", workflow_validator)

graph.add_edge("analyze", "decompose")
graph.add_edge("decompose", "architect")
graph.add_edge("architect", "validate")

# Conditional edge: if validation fails, return to architect
graph.add_conditional_edges(
    "validate",
    should_retry,
    {"retry": "architect", "done": END}
)
```

---

## 5. Tool Registry

The Tool Registry is the **central security boundary** between LLM planning and system execution.

```
Agent Request
      │
      ▼
┌───────────────┐
│ Tool Registry │
├───────────────┤
│ 1. Tool exists?         → Reject if unknown
│ 2. Action allowed?      → Reject if not allowlisted
│ 3. Input valid?         → Reject if malformed
│ 4. Permission check?    → Reject if unauthorized
│ 5. Execute              → Controlled execution
└───────────────┘
```

### Registered Tools (MVP)

| Tool | Allowed Actions | Permission Level |
|------|----------------|-----------------|
| DatabaseTool | `get_employee`, `get_equipment_request`, `record_decision` | READ / WRITE |
| RAGTool | `search_knowledge` | READ |
| NotificationTool | `create_notification` | WRITE |
| HumanApprovalTool | `request_approval`, `check_approval` | APPROVAL |

### Key Constraints
- **No raw SQL** — only predefined parameterized operations
- **No arbitrary HTTP** — no external API calls
- **No code execution** — no eval, exec, subprocess
- **Schema-validated** — every input/output must match Pydantic schema

---

## 6. RAG Architecture

```
Company Documents (Markdown)
          │
          ▼
   Document Loader
          │
          ▼
    Text Chunking
   (with metadata preservation)
          │
          ▼
   Embedding Generation
   (configurable provider)
          │
          ▼
   Qdrant Vector Store
   (with metadata filtering)
          │
          ▼
   Semantic Search
          │
          ▼
   RAG Tool (via Tool Registry)
          │
          ▼
   Agent receives evidence
```

### Components
- **Document Loader**: Reads markdown files from `knowledge/` directory
- **Chunker**: Splits documents into retrievable chunks with metadata (doc ID, title, section, chunk ID)
- **Embeddings**: Configurable embedding provider (environment variable)
- **Vector Store**: Qdrant collection with metadata filtering
- **Retriever**: `search_knowledge(query, top_k, filters)` → ranked results with source attribution

### Access Control
- Agents access RAG **only** through the RAG Tool via Tool Registry
- No direct Qdrant access from agents
- Retrieved content is treated as **evidence**, not executable instructions

---

## 7. Workflow Engine

The Workflow Engine has three modes of operation:

### 7.1 Validation Engine
```
WorkflowDefinition → Deterministic Checks → Semantic Checks → ValidationResult
```
- Deterministic validation has **final authority**
- LLM semantic validation provides advisory findings
- Invalid workflows cannot proceed

### 7.2 Simulation Engine
```
Validated Workflow → Sandbox Execution → Step-by-Step Results → SimulationResult
```
- Uses mock/sandbox tool implementations
- **No real side effects** — no emails, no DB writes, no external calls
- Records every step: input, output, status, timing
- Pauses at approval steps
- Purpose: user verification before real execution

### 7.3 Execution Engine
```
Approved Workflow → Pre-execution Checks → Sequential Execution → Verification → AuditLog
```
- Pre-checks: workflow exists, validated, approved, tools registered, permissions valid
- Executes steps in **dependency order**
- Uses Tool Registry for **every** tool call
- Handles: retries, timeouts, failures, cancellation
- Pauses at approval steps → creates ApprovalRequest → waits for human
- Records complete execution trace

### Execution States
```
PENDING → RUNNING → COMPLETED
                  → FAILED
                  → PAUSED (waiting for approval)
                  → CANCELLED
```

---

## 8. Human Approval System

```
Workflow reaches APPROVAL step
          │
          ▼
   Create ApprovalRequest
   (status: PENDING)
          │
          ▼
   Pause Execution
          │
          ▼
   Human reviews in UI
          │
     ┌────┼────────────┐
     ▼    ▼            ▼
  APPROVE REJECT   MODIFY
     │    │            │
     ▼    ▼            ▼
  Resume  Stop     New Version
  Exec    Exec     → Revalidate
                   → Re-approve
```

### Rules
1. Only authorized users can approve
2. LLM cannot approve its own workflow
3. All approval actions recorded in AuditLog
4. Rejected workflows cannot continue
5. Modification creates new WorkflowVersion
6. Modified workflows must be revalidated
7. Previous versions preserved

---

## 9. Audit Logging

Every significant action is recorded:

| Event Type | Recorded Data |
|------------|---------------|
| Workflow created | actor, workflow_id, requirement_text |
| Requirement analyzed | agent, analysis_summary |
| Process decomposed | agent, plan_summary |
| Workflow generated | agent, workflow_version |
| Workflow validated | validator, result, errors |
| Simulation started | execution_id, mode |
| Simulation completed | execution_id, result |
| Approval requested | step_id, approver |
| Approval granted/rejected | reviewer, decision |
| Execution started | execution_id, mode |
| Step executed | step_id, tool, status, duration |
| Execution completed | execution_id, result |
| Security event | event_type, details |

### Properties
- **Immutable**: Audit logs cannot be modified through normal application operations
- **Privacy-conscious**: No API keys, passwords, secrets, or unnecessary PII logged
- **Structured**: JSON metadata for machine readability
- **Timestamped**: UTC timestamps for all entries

---

## 10. Database Architecture

### PostgreSQL (Relational)
- **8 entities**: User, Workflow, WorkflowVersion, WorkflowExecution, ExecutionStep, ApprovalRequest, KnowledgeDocument, AuditLog
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Access pattern**: Repository layer → Service layer → API layer
- **Agents NEVER directly access SQLAlchemy sessions**

### Qdrant (Vector)
- **Purpose**: RAG document embeddings and semantic search
- **Access pattern**: RAG Service → Qdrant Client
- **Agents access through**: RAG Tool → Tool Registry → RAG Service → Qdrant

---

## 11. Deployment Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
│                                             │
│  ┌──────────┐  ┌──────────┐                │
│  │ Frontend │  │ Backend  │                │
│  │ (Next.js)│  │ (FastAPI)│                │
│  │ :3000    │  │ :8000    │                │
│  └──────────┘  └──────────┘                │
│                                             │
│  ┌──────────┐  ┌──────────┐                │
│  │PostgreSQL│  │  Qdrant  │                │
│  │ :5432    │  │  :6333   │                │
│  └──────────┘  └──────────┘                │
│                                             │
└─────────────────────────────────────────────┘
```

### Services
| Service | Port | Purpose |
|---------|------|---------|
| frontend | 3000 | Next.js UI |
| backend | 8000 | FastAPI API |
| postgres | 5432 | Relational data |
| qdrant | 6333 | Vector search |

### Configuration
- All configuration through environment variables
- `.env.example` with documented variables
- No hardcoded secrets
- Docker networking for inter-service communication
- Health checks for all services
- Database migrations run on backend startup
