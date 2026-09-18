/**
 * Typed API client for communicating with the FastAPI backend.
 * Covers all phases: analysis, decomposition, architecture, validation, simulation, execution, approvals, and audit.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface HealthStatus {
  status: string;
  version: string;
  services: {
    database: string;
    qdrant: string;
    llm: string;
  };
}

export interface Actor {
  role: string;
  type: string;
  responsibilities: string[];
}

export interface BusinessRule {
  rule_id: string;
  description: string;
  condition?: string;
  action?: string;
}

export interface ApprovalCriteria {
  role: string;
  trigger_condition: string;
  rationale: string;
}

export interface RequirementAnalysis {
  business_goal: string;
  trigger_event: string;
  trigger_description: string;
  inputs: Array<{ name: string; type: string; required: boolean; description?: string }>;
  outputs: string[];
  actors: Actor[];
  business_rules: BusinessRule[];
  data_entities: string[];
  approval_requirements: ApprovalCriteria[];
  potential_exceptions: string[];
  complexity_assessment: string;
  confidence_score: number;
}

export interface ProcessStage {
  name: string;
  order: number;
  description?: string;
  step_ids: string[];
}

export interface PlannedStep {
  id: string;
  name: string;
  description: string;
  stage: string;
  category: string;
  dependencies: string[];
  expected_inputs: string[];
  expected_outputs: string[];
  requires_human: boolean;
  is_critical: boolean;
}

export interface ProcessPlan {
  process_name: string;
  summary: string;
  stages: ProcessStage[];
  steps: PlannedStep[];
  tool_requirements: Array<{ tool_name: string; action: string; purpose: string }>;
  data_flow_summary: Record<string, string[]>;
  estimated_duration_seconds: number;
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: string;
  tool?: string;
  action?: string;
  description?: string;
  inputs?: Record<string, unknown>;
  outputs?: string[];
  dependencies?: string[];
  condition?: string;
  if_true?: string;
  if_false?: string;
  approver_role?: string;
  timeout_seconds?: number;
}

export interface WorkflowDefinition {
  workflow_id: string;
  name: string;
  description?: string;
  version: number;
  trigger: {
    id: string;
    type: string;
    event: string;
    description?: string;
    outputs?: string[];
  };
  inputs: Array<{ name: string; type: string; required: boolean }>;
  steps: WorkflowStep[];
  metadata?: {
    created_by?: string;
    domain?: string;
    estimated_duration_seconds?: number;
  };
  required_approvals?: Array<{
    step_id: string;
    approver_role: string;
    condition?: string;
  }>;
}

export interface ValidationIssue {
  rule_number: number;
  rule_name: string;
  severity: string;
  message: string;
  step_id?: string;
}

export interface ComprehensiveValidationReport {
  is_valid: boolean;
  deterministic_passed: boolean;
  semantic_passed: boolean;
  fidelity_score: number;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  recommendations: string[];
}

export interface StepExecutionRecord {
  step_id: string;
  step_name: string;
  step_type: string;
  status: string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  duration_ms: number;
  error?: string;
}

export interface SimulationResult {
  workflow_id: string;
  status: string;
  total_duration_ms: number;
  steps_executed: StepExecutionRecord[];
  tools_simulated: string[];
  final_outputs: Record<string, unknown>;
  approval_simulated: boolean;
}

export interface WorkflowExecutionState {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  started_at: string;
  completed_at?: string;
  total_duration_ms: number;
  steps: Array<{
    step_id: string;
    step_name: string;
    step_type: string;
    status: string;
    inputs: Record<string, unknown>;
    outputs: Record<string, unknown>;
    error?: string;
    duration_ms: number;
  }>;
  context: Record<string, unknown>;
  pending_approval_id?: string;
  error_message?: string;
}

export interface ApprovalRecord {
  id: string;
  workflow_execution_id: string;
  step_id: string;
  approver_role: string;
  requested_by: string;
  reviewed_by?: string;
  status: string;
  context_data: Record<string, unknown>;
  comments?: string;
  created_at: string;
  reviewed_at?: string;
}

export interface AuditLogRecord {
  id: string;
  actor_type: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface AgentAction {
  specialist: 'policy' | 'data' | 'approval' | 'action' | 'manager';
  action: string;
  parameters: Record<string, unknown>;
  reasoning: string;
}

export interface AgentObservation {
  success: boolean;
  data: Record<string, unknown>;
  summary: string;
  error?: string;
  requires_human?: boolean;
  metadata?: Record<string, unknown>;
}

export interface AgentThoughtStep {
  step_number: number;
  agent_role: string;
  thought: string;
  action_taken?: AgentAction;
  observation?: AgentObservation;
  timestamp: string;
}

export interface OrchestrationSession {
  session_id: string;
  goal: string;
  domain_hint?: string;
  status: 'in_progress' | 'awaiting_approval' | 'completed' | 'failed';
  steps: AgentThoughtStep[];
  accumulated_context: Record<string, unknown>;
  pending_approval?: {
    approval_id?: string;
    approver_role?: string;
    request_summary?: string;
  };
  final_outcome?: {
    status?: string;
    summary?: string;
    context?: Record<string, unknown>;
  };
  summary_message?: string;
  created_at: string;
  updated_at: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      const data = await response.json();
      if (!response.ok) {
        return {
          status: 'error',
          error: {
            code: 'API_ERROR',
            message: data.detail || `HTTP ${response.status}`,
          },
        };
      }
      return { status: 'success', data };
    } catch (error) {
      return {
        status: 'error',
        error: {
          code: 'NETWORK_ERROR',
          message: error instanceof Error ? error.message : 'Network request failed',
        },
      };
    }
  }

  async getHealth(): Promise<ApiResponse<HealthStatus>> {
    return this.request<HealthStatus>('/health');
  }

  async analyzeRequirement(requirementText: string, domainHint?: string): Promise<ApiResponse<{ analysis: RequirementAnalysis }>> {
    return this.request('/api/v1/analyze-requirement', {
      method: 'POST',
      body: JSON.stringify({ requirement_text: requirementText, domain_hint: domainHint }),
    });
  }

  async decomposeProcess(analysis: RequirementAnalysis, maxStages: number = 6): Promise<ApiResponse<{ plan: ProcessPlan }>> {
    return this.request('/api/v1/decompose-process', {
      method: 'POST',
      body: JSON.stringify({ analysis, max_stages: maxStages }),
    });
  }

  async generateWorkflow(analysis: RequirementAnalysis, processPlan: ProcessPlan, name?: string): Promise<ApiResponse<{ workflow: WorkflowDefinition }>> {
    return this.request('/api/v1/generate-workflow', {
      method: 'POST',
      body: JSON.stringify({ analysis, process_plan: processPlan, name }),
    });
  }

  async validateWorkflow(workflow: WorkflowDefinition, requirementText?: string): Promise<ApiResponse<{ report: ComprehensiveValidationReport }>> {
    return this.request('/api/v1/comprehensive-validate', {
      method: 'POST',
      body: JSON.stringify({ workflow, requirement_text: requirementText }),
    });
  }

  async simulateWorkflow(workflow: WorkflowDefinition, initialInputs?: Record<string, unknown>): Promise<ApiResponse<{ simulation: SimulationResult }>> {
    return this.request('/api/v1/simulate', {
      method: 'POST',
      body: JSON.stringify({ workflow, initial_inputs: initialInputs }),
    });
  }

  async startExecution(workflow: WorkflowDefinition, initialInputs?: Record<string, unknown>, actorId?: string): Promise<ApiResponse<{ execution: WorkflowExecutionState }>> {
    return this.request('/api/v1/executions/start', {
      method: 'POST',
      body: JSON.stringify({ workflow, initial_inputs: initialInputs, actor_id: actorId || 'user' }),
    });
  }

  async getExecution(executionId: string): Promise<ApiResponse<{ execution: WorkflowExecutionState }>> {
    return this.request(`/api/v1/executions/${executionId}`);
  }

  async resumeExecution(executionId: string, reviewerId: string, decision: string, comments?: string): Promise<ApiResponse<{ execution: WorkflowExecutionState }>> {
    return this.request(`/api/v1/executions/${executionId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId, decision, comments }),
    });
  }

  async listPendingApprovals(role?: string): Promise<ApiResponse<{ total: number; approvals: ApprovalRecord[] }>> {
    const q = role ? `?role=${role}` : '';
    return this.request(`/api/v1/approvals/pending${q}`);
  }

  async decideApproval(approvalId: string, reviewerId: string, decision: string, comments?: string): Promise<ApiResponse<{ approval: ApprovalRecord }>> {
    return this.request(`/api/v1/approvals/${approvalId}/decide`, {
      method: 'POST',
      body: JSON.stringify({ reviewer_id: reviewerId, decision, comments }),
    });
  }

  async searchKnowledge(query: string, topK: number = 3, category?: string): Promise<ApiResponse<{ total_results: number; results: Array<{ source: string; score: number; content: string }> }>> {
    return this.request('/api/v1/knowledge/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK, category }),
    });
  }

  async listAuditLogs(resourceType?: string, limit: number = 50): Promise<ApiResponse<{ total: number; logs: AuditLogRecord[] }>> {
    const q = resourceType ? `?resource_type=${resourceType}&limit=${limit}` : `?limit=${limit}`;
    return this.request(`/api/v1/audit/logs${q}`);
  }

  async orchestrateGoal(goal: string, initialContext?: Record<string, unknown>, domainHint?: string): Promise<ApiResponse<{ session: OrchestrationSession }>> {
    return this.request('/api/v1/orchestrate', {
      method: 'POST',
      body: JSON.stringify({ goal, initial_context: initialContext, domain_hint: domainHint }),
    });
  }

  async resumeOrchestration(sessionId: string, approvalDecision: 'approved' | 'rejected', approverComments?: string, reviewerRole: string = 'manager'): Promise<ApiResponse<{ session: OrchestrationSession }>> {
    return this.request('/api/v1/orchestrate/resume', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        approval_decision: approvalDecision,
        approver_comments: approverComments,
        reviewer_role: reviewerRole,
      }),
    });
  }

  async getOrchestrationSession(sessionId: string): Promise<ApiResponse<OrchestrationSession>> {
    return this.request(`/api/v1/orchestrate/${sessionId}`);
  }
}

export const api = new ApiClient();
export default api;
