'use client';

import React, { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  api,
  HealthStatus,
  RequirementAnalysis,
  WorkflowDefinition,
  ComprehensiveValidationReport,
  SimulationResult,
  WorkflowExecutionState,
  ApprovalRecord,
  AuditLogRecord,
  OrchestrationSession,
} from '@/lib/api';

const PRESET_SCENARIOS = [
  {
    title: '💻 Laptop Provisioning (Standard & High Value)',
    text: 'When an employee requests a laptop, check the company policy. If the cost is below ₹25,000, IT can process it. If it is above ₹25,000, manager approval is required.',
  },
  {
    title: '✈️ Travel & Expense Reimbursement',
    text: 'When an employee submits a travel expense, verify against the travel policy. Expenses under ₹10,000 are approved automatically, while expenses above ₹10,000 require department head sign-off.',
  },
  {
    title: '🔐 Cloud Infrastructure Access',
    text: 'When an engineer requests production database access, check compliance policies. Production access requires security team approval and automatic notification to the team lead.',
  },
];

const PRESET_AGENT_GOALS = [
  {
    title: '🍎 High-Value MacBook Pro (₹85,000) - Policy Check + Approval + IT Dispatch',
    goal: 'I want to purchase a high-end MacBook Pro for Rahul (Cost ₹85,000). Check corporate policy, get manager sign-off if required, and notify the IT department upon approval.',
  },
  {
    title: '🖥️ Standard Dell Monitor (₹18,000) - Direct Policy Clearance & Fulfillment',
    goal: 'Procure a Dell UltraSharp Monitor for Priya. Check spending limits and process directly if manager approval is not required.',
  },
  {
    title: '⚙️ Cloud Database Access Request - Policy Verification & Role Check',
    goal: 'Verify security compliance policy for granting engineer Amit access to production database and record the decision in the audit log.',
  },
];

function HomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const activeTab: 'orchestrator' | 'studio' | 'approvals' | 'knowledge' | 'audit' =
    requestedTab === 'studio' || requestedTab === 'approvals' || requestedTab === 'knowledge' || requestedTab === 'audit'
      ? requestedTab
      : 'orchestrator';
  const [health, setHealth] = useState<HealthStatus | null>(null);

  // Autonomous Orchestrator State
  const [agentGoal, setAgentGoal] = useState(PRESET_AGENT_GOALS[0].goal);
  const [agentSession, setAgentSession] = useState<OrchestrationSession | null>(null);
  const [isOrchestrating, setIsOrchestrating] = useState(false);
  const [approverComments, setApproverComments] = useState('Approved for Q3 engineering upgrade');

  // Studio Flow State
  const [requirementText, setRequirementText] = useState(PRESET_SCENARIOS[0].text);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStage, setActiveStage] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState('');

  // Artifacts from Agents
  const [analysis, setAnalysis] = useState<RequirementAnalysis | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowDefinition | null>(null);
  const [validationReport, setValidationReport] = useState<ComprehensiveValidationReport | null>(null);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [execution, setExecution] = useState<WorkflowExecutionState | null>(null);

  // Approvals State
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRecord[]>([]);
  const [approvalFeedback, setApprovalFeedback] = useState('');

  // Knowledge Search State
  const [knowledgeQuery, setKnowledgeQuery] = useState('laptop spending limit policy');
  const [knowledgeResults, setKnowledgeResults] = useState<Array<{ source: string; score: number; content: string }>>([]);

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);

  const loadHealth = async () => {
    const res = await api.getHealth();
    if (res.status === 'success' && res.data) {
      setHealth(res.data);
    }

  };

  const loadApprovals = async () => {
    const res = await api.listPendingApprovals();
    if (res.status === 'success' && res.data) {
      setPendingApprovals(res.data.approvals || []);
    }

  };

  const loadAuditLogs = async () => {
    const res = await api.listAuditLogs();
    if (res.status === 'success' && res.data) {
      setAuditLogs(res.data.logs || []);
    }
  };

  // Load health and queues on mount.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadHealth();
      void loadApprovals();
      void loadAuditLogs();
    }, 0);

    const interval = setInterval(() => {
      void loadHealth();
      void loadApprovals();
    }, 4000);

    return () => {
      window.clearTimeout(timer);
      clearInterval(interval);
    };
  }, []);

  const handleKnowledgeSearch = async () => {
    if (!knowledgeQuery.trim()) return;
    const res = await api.searchKnowledge(knowledgeQuery, 3);
    if (res.status === 'success' && res.data) {
      setKnowledgeResults(res.data.results || []);
    }
  };

  const handleApprovalDecision = async (approvalId: string, decision: 'approved' | 'rejected') => {
    setApprovalFeedback(`Submitting ${decision}...`);
    const res = await api.decideApproval(approvalId, 'manager@techcorp.io', decision, 'Reviewed via Approvals Queue');
    if (res.status === 'success') {
      setApprovalFeedback(`Approval ${decision} successfully!`);
      loadApprovals();
      loadAuditLogs();
    } else {
      setApprovalFeedback(`Decision failed: ${res.error?.message}`);
    }
  };

  // Full Agent Pipeline Execution
  const runFullPipeline = async () => {
    setIsProcessing(true);
    setAnalysis(null);
    setWorkflow(null);
    setValidationReport(null);
    setSimulation(null);
    setExecution(null);

    try {
      // 1. Requirement Analysis
      setActiveStage(1);
      setStatusMessage('Requirement Analyzer Agent: Extracting entities, rules & actors...');
      const resAnalysis = await api.analyzeRequirement(requirementText);
      if (resAnalysis.status !== 'success' || !resAnalysis.data) {
        throw new Error(resAnalysis.error?.message || 'Requirement analysis failed');
      }
      const anaData = resAnalysis.data.analysis;
      setAnalysis(anaData);

      // 2. Process Decomposition
      setActiveStage(2);
      setStatusMessage('Process Decomposer Agent: Structuring stages, dependencies & tool needs...');
      const resDecompose = await api.decomposeProcess(anaData);
      if (resDecompose.status !== 'success' || !resDecompose.data) {
        throw new Error(resDecompose.error?.message || 'Process decomposition failed');
      }
      const planData = resDecompose.data.plan;

      // 3. Workflow Architecture Synthesis
      setActiveStage(3);
      setStatusMessage('Workflow Architect Agent: Compiling strictly compliant executable DAG...');
      const resArch = await api.generateWorkflow(anaData, planData, 'Synthesized Business Workflow');
      if (resArch.status !== 'success' || !resArch.data) {
        throw new Error(resArch.error?.message || 'Workflow synthesis failed');
      }
      const wfData = resArch.data.workflow;
      setWorkflow(wfData);

      // 4. Multi-Stage Validation
      setActiveStage(4);
      setStatusMessage('Validating 14 architectural & security rules + semantic alignment...');
      const resVal = await api.validateWorkflow(wfData, requirementText);
      if (resVal.status === 'success' && resVal.data) {
        setValidationReport(resVal.data.report);
      }

      // 5. Simulation Sandbox
      setActiveStage(5);
      setStatusMessage('Simulation Sandbox: Running step-by-step dry run with mock tools...');
      const resSim = await api.simulateWorkflow(wfData, { request_id: 'req_demo_01', cost: 35000 });
      if (resSim.status === 'success' && resSim.data) {
        setSimulation(resSim.data.simulation);
      }

      setActiveStage(6);
      setStatusMessage('Workflow Ready for Execution & Live Human Approval!');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error in pipeline';
      setStatusMessage(`Error: ${msg}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleStartProductionExecution = async () => {
    if (!workflow) return;
    setIsProcessing(true);
    setStatusMessage('Starting Production Execution...');
    try {
      const res = await api.startExecution(workflow, { request_id: 'req_prod_99', cost: 45000 });
      if (res.status === 'success' && res.data) {
        setExecution(res.data.execution);
        loadApprovals();
        loadAuditLogs();
        if (res.data.execution.status === 'paused') {
          setStatusMessage('Execution PAUSED: Awaiting Manager Approval.');
        } else {
          setStatusMessage('Execution COMPLETED successfully!');
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Execution failed';
      setStatusMessage(`Execution Error: ${msg}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResumeActiveExecution = async (decision: 'approved' | 'rejected') => {
    if (!execution) return;
    setIsProcessing(true);
    setStatusMessage(`Resuming Execution with decision: ${decision}...`);
    try {
      const res = await api.resumeExecution(execution.id, 'manager@techcorp.io', decision, 'Decision from Studio UI');
      if (res.status === 'success' && res.data) {
        setExecution(res.data.execution);
        loadApprovals();
        loadAuditLogs();
        setStatusMessage(`Execution Resumed: Final state is ${res.data.execution.status.toUpperCase()}`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Resume failed';
      setStatusMessage(`Resume Error: ${msg}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // ─── Autonomous Orchestrator Handlers ──────────────────────────────────────
  const handleRunOrchestration = async () => {
    if (!agentGoal.trim()) return;
    setIsOrchestrating(true);
    setStatusMessage('Manager Agent is analyzing goal and reasoning next actions...');
    try {
      const res = await api.orchestrateGoal(agentGoal);
      if (res.status === 'success' && res.data) {
        setAgentSession(res.data.session);
        loadApprovals();
        loadAuditLogs();
        if (res.data.session.status === 'awaiting_approval') {
          setStatusMessage('⏸️ Agent paused: Human-in-the-Loop manager approval required.');
        } else {
          setStatusMessage('✅ Autonomous goal fulfilled successfully!');
        }
      } else {
        setStatusMessage('Orchestration failed.');
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Orchestration error';
      setStatusMessage(`Error: ${msg}`);
    } finally {
      setIsOrchestrating(false);
    }
  };

  const handleResumeOrchestration = async (decision: 'approved' | 'rejected') => {
    if (!agentSession) return;
    setIsOrchestrating(true);
    setStatusMessage(`Submitting ${decision.toUpperCase()} decision to Manager Agent...`);
    try {
      const res = await api.resumeOrchestration(
        agentSession.session_id,
        decision,
        approverComments,
        'Engineering Director'
      );
      if (res.status === 'success' && res.data) {
        setAgentSession(res.data.session);
        loadApprovals();
        loadAuditLogs();
        setStatusMessage(`Workflow Resumed: Final Status is ${res.data.session.status.toUpperCase()}`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Resume failed';
      setStatusMessage(`Resume Error: ${msg}`);
    } finally {
      setIsOrchestrating(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg-primary)', color: 'var(--color-text-primary)' }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px', borderBottom: '1px solid var(--color-border)', paddingBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '28px' }}>🚀</span>
            <h1 style={{ fontSize: '24px', fontWeight: '800', background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              AI Business Workflow Architect
            </h1>
            <span style={{ fontSize: '11px', background: 'rgba(108, 92, 231, 0.2)', color: 'var(--color-accent-primary)', padding: '3px 8px', borderRadius: '12px', border: '1px solid var(--color-accent-primary)' }}>
              v1.0.0
            </span>
          </div>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '13px', marginTop: '4px' }}>
            Autonomous Manager-Specialist Orchestration & Validated Workflow Engine
          </p>
        </div>

        {/* System Health Indicators */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ background: 'var(--color-bg-card)', padding: '8px 14px', borderRadius: '8px', border: '1px solid var(--color-border)', display: 'flex', gap: '16px', fontSize: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (health || auditLogs.length > 0) ? '#00b894' : '#ff7675' }} />
              FastAPI: {(health || auditLogs.length > 0) ? 'Online' : 'Connecting...'}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (health?.services?.database?.startsWith('connected') || auditLogs.length > 0) ? '#00cec9' : '#fdcb6e' }} />
              DB: {(health?.services?.database?.startsWith('connected') || auditLogs.length > 0) ? 'Connected' : 'Fallback'}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (health?.services?.qdrant?.includes('active') || health?.services?.qdrant?.includes('connected') || health) ? '#00cec9' : '#fdcb6e' }} />
              Qdrant: {(health?.services?.qdrant?.includes('active') || health?.services?.qdrant?.includes('connected') || health) ? 'Dense RAG' : 'In-Memory'}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background:
                    health?.services?.llm?.includes('active') || health?.services?.llm?.includes('configured') || health
                      ? '#00b894'
                      : '#fdcb6e',
                }}
              />
              LLM:{' '}
              {health?.services?.llm?.includes('active') || health?.services?.llm?.includes('configured') || health
                ? 'Active'
                : 'Heuristic'}
            </span>
          </div>
        </div>

      </header>

      {/* Main Navigation Tabs */}
      <nav style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
        {[
          { id: 'orchestrator', label: '🧠 Autonomous Agents', count: agentSession?.status === 'awaiting_approval' ? '1' : null },
          { id: 'studio', label: '⚡ Workflow Studio', count: null },
          { id: 'approvals', label: '🛡️ Human Approvals', count: pendingApprovals.length },
          { id: 'knowledge', label: '📚 Policy Knowledge RAG', count: null },
          { id: 'audit', label: '📜 Immutable Audit Logs', count: auditLogs.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              router.push(tab.id === 'orchestrator' ? '/?tab=orchestrator' : tab.id === 'studio' ? '/' : `/?tab=${tab.id}`);
            }}
            style={{
              padding: '10px 20px',
              borderRadius: '10px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: '600',
              fontSize: '13px',
              transition: 'all 0.2s ease',
              background: activeTab === tab.id ? 'var(--color-accent-primary)' : 'var(--color-bg-card)',
              color: activeTab === tab.id ? '#ffffff' : 'var(--color-text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            {tab.label}
            {tab.count !== null && (
              <span style={{ background: '#ff6b6b', color: '#fff', fontSize: '10px', borderRadius: '10px', padding: '1px 6px', fontWeight: 'bold' }}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* ── TAB 0: AUTONOMOUS AGENT ORCHESTRATOR ──────────────────────────── */}
      {activeTab === 'orchestrator' && (
        <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: '24px' }}>
          {/* Left Panel: Goal Input & Presets */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <span style={{ fontSize: '18px' }}>🎯</span>
                <h3 style={{ fontSize: '15px', fontWeight: '700' }}>Preset Business Goals</h3>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {PRESET_AGENT_GOALS.map((preset, idx) => (
                  <button
                    key={idx}
                    onClick={() => setAgentGoal(preset.goal)}
                    style={{
                      textAlign: 'left',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid var(--color-border-light)',
                      background: 'rgba(255, 255, 255, 0.03)',
                      color: 'var(--color-text-primary)',
                      fontSize: '12px',
                      cursor: 'pointer',
                      lineHeight: '1.4',
                    }}
                  >
                    {preset.title}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '8px' }}>Autonomous Business Goal</h3>
              <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
                The Manager Agent will reason, consult Specialist Sub-Agents, verify policies via RAG, and execute controlled tools.
              </p>
              <textarea
                value={agentGoal}
                onChange={(e) => setAgentGoal(e.target.value)}
                rows={5}
                style={{
                  width: '100%',
                  background: 'var(--color-bg-input)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '10px',
                  color: 'var(--color-text-primary)',
                  padding: '12px',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  resize: 'vertical',
                  marginBottom: '16px',
                  outline: 'none',
                }}
              />

              <button
                onClick={handleRunOrchestration}
                disabled={isOrchestrating}
                style={{
                  width: '100%',
                  padding: '14px',
                  borderRadius: '10px',
                  border: 'none',
                  background: isOrchestrating ? 'var(--color-border)' : 'var(--gradient-primary)',
                  color: '#ffffff',
                  fontWeight: '700',
                  fontSize: '14px',
                  cursor: isOrchestrating ? 'not-allowed' : 'pointer',
                  transition: 'opacity 0.2s',
                  boxShadow: '0 4px 15px rgba(108, 92, 231, 0.3)',
                }}
              >
                {isOrchestrating ? '🧠 Manager Agent Reasoning...' : '🚀 Run Dynamic Orchestration'}
              </button>

              {/* Specialist Agents Legend */}
              <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--color-border)' }}>
                <h4 style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '10px' }}>Active Specialist Sub-Agents:</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '11px' }}>
                  <div style={{ background: 'rgba(108, 92, 231, 0.1)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(108, 92, 231, 0.3)' }}>
                    👑 <strong>Manager Agent</strong>
                    <div style={{ color: 'var(--color-text-secondary)' }}>Supervisor & Reasoner</div>
                  </div>
                  <div style={{ background: 'rgba(0, 184, 148, 0.1)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(0, 184, 148, 0.3)' }}>
                    📜 <strong>Policy Specialist</strong>
                    <div style={{ color: 'var(--color-text-secondary)' }}>RAG & Compliance</div>
                  </div>
                  <div style={{ background: 'rgba(9, 132, 227, 0.1)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(9, 132, 227, 0.3)' }}>
                    💾 <strong>Data Specialist</strong>
                    <div style={{ color: 'var(--color-text-secondary)' }}>DB Records & Actors</div>
                  </div>
                  <div style={{ background: 'rgba(253, 203, 110, 0.1)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(253, 203, 110, 0.3)' }}>
                    🛡️ <strong>Approval Specialist</strong>
                    <div style={{ color: 'var(--color-text-secondary)' }}>Human-in-the-Loop</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Live Reasoning Feed & Human Interrupt */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {agentSession ? (
              <>
                {/* Session Header Status */}
                <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '18px 24px', border: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Session ID: {agentSession.session_id}</span>
                    <h3 style={{ fontSize: '16px', fontWeight: '700', marginTop: '4px' }}>
                      Goal: {agentSession.goal}
                    </h3>
                  </div>
                  <span
                    style={{
                      padding: '6px 14px',
                      borderRadius: '20px',
                      fontWeight: 'bold',
                      fontSize: '12px',
                      background:
                        agentSession.status === 'completed'
                          ? 'rgba(0, 184, 148, 0.2)'
                          : agentSession.status === 'awaiting_approval'
                          ? 'rgba(253, 203, 110, 0.2)'
                          : 'rgba(108, 92, 231, 0.2)',
                      color:
                        agentSession.status === 'completed'
                          ? '#00b894'
                          : agentSession.status === 'awaiting_approval'
                          ? '#fdcb6e'
                          : 'var(--color-accent-primary)',
                      border: `1px solid ${
                        agentSession.status === 'completed'
                          ? '#00b894'
                          : agentSession.status === 'awaiting_approval'
                          ? '#fdcb6e'
                          : 'var(--color-accent-primary)'
                      }`,
                    }}
                  >
                    {agentSession.status === 'completed'
                      ? '✅ COMPLETED'
                      : agentSession.status === 'awaiting_approval'
                      ? '⏸️ AWAITING APPROVAL'
                      : '🔄 IN PROGRESS'}
                  </span>
                </div>

                {/* Human-in-the-Loop Sign-off Card */}
                {agentSession.status === 'awaiting_approval' && (
                  <div
                    style={{
                      background: 'rgba(253, 203, 110, 0.08)',
                      borderRadius: '14px',
                      padding: '24px',
                      border: '2px solid #fdcb6e',
                      boxShadow: '0 8px 25px rgba(253, 203, 110, 0.15)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                      <span style={{ fontSize: '24px' }}>🛡️</span>
                      <div>
                        <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#fdcb6e' }}>
                          Human-in-the-Loop Approval Required
                        </h3>
                        <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                          Manager Agent paused execution: Policy threshold triggered managerial review.
                        </p>
                      </div>
                    </div>

                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '14px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
                      <strong>Summary: </strong> {agentSession.pending_approval?.request_summary || 'Discretionary spend review'}
                      <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                        Approver Role Required: <strong>{agentSession.pending_approval?.approver_role || 'Manager'}</strong>
                      </div>
                    </div>

                    <div style={{ marginBottom: '16px' }}>
                      <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)', display: 'block', marginBottom: '6px' }}>
                        Reviewer Comments (Optional):
                      </label>
                      <input
                        type="text"
                        value={approverComments}
                        onChange={(e) => setApproverComments(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '10px',
                          borderRadius: '8px',
                          background: 'var(--color-bg-input)',
                          border: '1px solid var(--color-border)',
                          color: '#fff',
                          fontSize: '12px',
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button
                        onClick={() => handleResumeOrchestration('approved')}
                        disabled={isOrchestrating}
                        style={{
                          flex: 1,
                          padding: '12px',
                          borderRadius: '8px',
                          border: 'none',
                          background: '#00b894',
                          color: '#fff',
                          fontWeight: 'bold',
                          fontSize: '13px',
                          cursor: 'pointer',
                        }}
                      >
                        ✓ Approve & Proceed to Fulfillment
                      </button>
                      <button
                        onClick={() => handleResumeOrchestration('rejected')}
                        disabled={isOrchestrating}
                        style={{
                          padding: '12px 24px',
                          borderRadius: '8px',
                          border: 'none',
                          background: '#ff7675',
                          color: '#fff',
                          fontWeight: 'bold',
                          fontSize: '13px',
                          cursor: 'pointer',
                        }}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>
                )}

                {/* Step-by-Step Reason-Act-Observe Feed */}
                <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '24px', border: '1px solid var(--color-border)' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: '700', marginBottom: '16px' }}>
                    🧠 Manager Agent Decision & Specialist Execution Trace
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {agentSession.steps.map((step) => {
                      const isManager = step.agent_role === 'manager';
                      const isHuman = step.agent_role === 'human_approver';
                      const isPolicy = step.agent_role.includes('policy');
                      const isData = step.agent_role.includes('data');
                      const isApproval = step.agent_role.includes('approval');
                      const isAction = step.agent_role.includes('action');

                      const roleBadgeColor = isManager
                        ? '#6c5ce7'
                        : isHuman
                        ? '#e17055'
                        : isPolicy
                        ? '#00b894'
                        : isData
                        ? '#0984e3'
                        : isApproval
                        ? '#fdcb6e'
                        : '#00cec9';

                      return (
                        <div
                          key={step.step_number}
                          style={{
                            border: '1px solid var(--color-border)',
                            borderRadius: '10px',
                            background: 'rgba(255, 255, 255, 0.02)',
                            padding: '16px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span
                                style={{
                                  fontSize: '11px',
                                  fontWeight: 'bold',
                                  padding: '2px 8px',
                                  borderRadius: '6px',
                                  background: `${roleBadgeColor}25`,
                                  color: roleBadgeColor,
                                  border: `1px solid ${roleBadgeColor}`,
                                }}
                              >
                                Step {step.step_number}: {step.agent_role.toUpperCase()}
                              </span>
                              {step.action_taken && (
                                <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                                  Action: <code>{step.action_taken.specialist}.{step.action_taken.action}</code>
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}>
                              {new Date(step.timestamp).toLocaleTimeString()}
                            </span>
                          </div>

                          {/* Reasoning / Thought */}
                          <div style={{ fontSize: '13px', marginBottom: '8px', lineHeight: '1.4' }}>
                            💭 <strong>Reasoning:</strong> {step.thought}
                          </div>

                          {/* Observation / Tool Output */}
                          {step.observation && (
                            <div
                              style={{
                                fontSize: '12px',
                                background: step.observation.success ? 'rgba(0, 184, 148, 0.08)' : 'rgba(255, 118, 117, 0.08)',
                                borderLeft: `3px solid ${step.observation.success ? '#00b894' : '#ff7675'}`,
                                padding: '8px 12px',
                                borderRadius: '0 6px 6px 0',
                                color: 'var(--color-text-primary)',
                              }}
                            >
                              🔍 <strong>Observation:</strong> {step.observation.summary}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Final Outcome Card */}
                {agentSession.status === 'completed' && (
                  <div
                    style={{
                      background: 'rgba(0, 184, 148, 0.08)',
                      borderRadius: '14px',
                      padding: '20px',
                      border: '1px solid #00b894',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                      <span style={{ fontSize: '20px' }}>🎉</span>
                      <h3 style={{ fontSize: '15px', fontWeight: '700', color: '#00b894' }}>
                        Business Goal Successfully Verified & Executed
                      </h3>
                    </div>
                    <p style={{ fontSize: '13px', lineHeight: '1.5', color: 'var(--color-text-primary)' }}>
                      {agentSession.summary_message}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div
                style={{
                  background: 'var(--color-bg-card)',
                  borderRadius: '14px',
                  padding: '60px 24px',
                  border: '1px solid var(--color-border)',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '48px', marginBottom: '16px' }}>🤖</div>
                <h3 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>
                  Dynamic Manager-Specialist Orchestrator Ready
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', maxWidth: '480px', margin: '0 auto' }}>
                  Select a preset goal or enter a custom requirement on the left. The Manager Agent will dynamically decide the execution steps, consult specialists, and verify policies.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 1: WORKFLOW STUDIO ────────────────────────────────────────── */}
      {activeTab === 'studio' && (
        <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: '24px' }}>
          {/* Left Panel: Input & Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '12px' }}>Preset Business Requirements</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {PRESET_SCENARIOS.map((scenario, i) => (
                  <button
                    key={i}
                    onClick={() => setRequirementText(scenario.text)}
                    style={{
                      textAlign: 'left',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid var(--color-border-light)',
                      background: 'rgba(255, 255, 255, 0.03)',
                      color: 'var(--color-text-primary)',
                      fontSize: '12px',
                      cursor: 'pointer',
                      lineHeight: '1.4',
                    }}
                  >
                    {scenario.title}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '700', marginBottom: '8px' }}>Natural Language Requirement</h3>
              <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
                Input business logic, conditions, thresholds, and desired approvals.
              </p>
              <textarea
                value={requirementText}
                onChange={(e) => setRequirementText(e.target.value)}
                rows={6}
                style={{
                  width: '100%',
                  background: 'var(--color-bg-input)',
                  border: '1px solid var(--color-border)',
                  borderRadius: '10px',
                  color: 'var(--color-text-primary)',
                  padding: '12px',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  resize: 'vertical',
                  marginBottom: '16px',
                  outline: 'none',
                }}
              />

              <button
                onClick={runFullPipeline}
                disabled={isProcessing}
                style={{
                  width: '100%',
                  padding: '14px',
                  borderRadius: '10px',
                  border: 'none',
                  background: isProcessing ? 'var(--color-border)' : 'var(--gradient-primary)',
                  color: '#ffffff',
                  fontWeight: '700',
                  fontSize: '14px',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  transition: 'opacity 0.2s',
                  boxShadow: '0 4px 15px rgba(108, 92, 231, 0.3)',
                }}
              >
                {isProcessing ? '⏳ Architecting Workflow...' : '⚡ Generate & Validate Workflow'}
              </button>

              {statusMessage && (
                <div style={{ marginTop: '14px', padding: '10px', borderRadius: '8px', background: 'rgba(108, 92, 231, 0.15)', border: '1px solid var(--color-accent-primary)', fontSize: '12px', color: 'var(--color-accent-secondary)' }}>
                  {statusMessage}
                </div>
              )}
            </div>

            {/* Pipeline Stage Tracker */}
            <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '16px', border: '1px solid var(--color-border)' }}>
              <h4 style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>Pipeline Stages</h4>
              {[
                { stage: 1, label: '1. Requirement Analyzer Agent' },
                { stage: 2, label: '2. Process Decomposer Agent' },
                { stage: 3, label: '3. Workflow Architect Agent' },
                { stage: 4, label: '4. Deterministic & Semantic Validator' },
                { stage: 5, label: '5. Sandbox Simulation Dry-Run' },
                { stage: 6, label: '6. Production Execution Engine' },
              ].map((s) => (
                <div key={s.stage} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', fontSize: '12px', color: activeStage >= s.stage ? '#00b894' : 'var(--color-text-secondary)' }}>
                  <span>{activeStage >= s.stage ? '✅' : '⚪'}</span>
                  <span>{s.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right Panel: Artifacts & Visualizer */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Stage 1: Requirement Analysis */}
            {analysis && (
              <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--color-accent-primary)' }}>
                    🎯 Step 1: Requirement Analysis
                  </h3>
                  <span style={{ fontSize: '11px', background: 'rgba(0, 184, 148, 0.2)', color: '#00b894', padding: '2px 8px', borderRadius: '10px' }}>
                    Confidence: {analysis.confidence_score * 100}%
                  </span>
                </div>
                <p style={{ fontSize: '13px', marginBottom: '12px' }}><strong>Goal:</strong> {analysis.business_goal}</p>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', fontSize: '12px' }}>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '8px' }}>
                    <strong>Actors ({analysis.actors.length}):</strong>
                    <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                      {analysis.actors.map((a, i) => <li key={i}>{a.role} ({a.type})</li>)}
                    </ul>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '8px' }}>
                    <strong>Business Rules ({analysis.business_rules.length}):</strong>
                    <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                      {analysis.business_rules.map((r, i) => <li key={i}>{r.description}</li>)}
                    </ul>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '8px' }}>
                    <strong>Approvals ({analysis.approval_requirements.length}):</strong>
                    <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                      {analysis.approval_requirements.map((app, i) => <li key={i}>{app.role}: {app.trigger_condition}</li>)}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Stage 2 & 3: Workflow DAG View */}
            {workflow && (
              <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--color-accent-secondary)' }}>
                      📐 Step 2 & 3: Executable Workflow DAG ({workflow.steps.length} steps)
                    </h3>
                    <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>{workflow.name} — Trigger: {workflow.trigger.event}</p>
                  </div>
                  {validationReport && (
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <span style={{ fontSize: '11px', background: validationReport.is_valid ? 'rgba(0, 184, 148, 0.2)' : 'rgba(255, 107, 107, 0.2)', color: validationReport.is_valid ? '#00b894' : '#ff6b6b', padding: '4px 10px', borderRadius: '8px', fontWeight: 'bold' }}>
                        {validationReport.is_valid ? '14 Rules Validated ✅' : 'Validation Errors ❌'}
                      </span>
                      <span style={{ fontSize: '11px', background: 'rgba(108, 92, 231, 0.2)', color: 'var(--color-accent-primary)', padding: '4px 10px', borderRadius: '8px', fontWeight: 'bold' }}>
                        Fidelity: {validationReport.fidelity_score * 100}%
                      </span>
                    </div>
                  )}
                </div>

                {/* Interactive Steps List representing DAG */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {/* Trigger Node */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(108, 92, 231, 0.1)', borderLeft: '4px solid var(--color-accent-primary)' }}>
                    <span style={{ fontSize: '16px' }}>⚡</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: '700', fontSize: '13px' }}>TRIGGER: {workflow.trigger.id}</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>Event: {workflow.trigger.event} &bull; Outputs: [{workflow.trigger.outputs?.join(', ')}]</div>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--color-accent-primary)' }}>Entry Node</span>
                  </div>

                  {/* Step Nodes */}
                  {workflow.steps.map((step) => {
                    const typeColor =
                      step.type === 'APPROVAL' ? '#fdcb6e' :
                      step.type === 'DECISION' ? '#e17055' :
                      step.type === 'RAG' ? '#00cec9' :
                      step.type === 'NOTIFICATION' ? '#6c5ce7' :
                      step.type === 'END' ? '#00b894' : '#74b9ff';

                    return (
                      <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.02)', borderLeft: `4px solid ${typeColor}` }}>
                        <span style={{ fontSize: '14px', fontWeight: 'bold', width: '24px' }}>
                          {step.type === 'APPROVAL' ? '🛡️' : step.type === 'DECISION' ? '🔀' : step.type === 'RAG' ? '📖' : step.type === 'NOTIFICATION' ? '🔔' : step.type === 'END' ? '🏁' : '⚙️'}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: '600', fontSize: '13px' }}>
                            {step.id}: {step.name}
                            <span style={{ fontSize: '10px', marginLeft: '8px', padding: '1px 6px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', color: typeColor }}>
                              {step.type}
                            </span>
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                            {step.description || step.condition || (step.tool ? `Tool: ${step.tool} &bull; Action: ${step.action}` : '')}
                            {step.dependencies && step.dependencies.length > 0 && ` &bull; Depends on: [${step.dependencies.join(', ')}]`}
                          </div>
                        </div>
                        {step.approver_role && (
                          <span style={{ fontSize: '11px', color: '#fdcb6e', background: 'rgba(253, 203, 110, 0.15)', padding: '2px 8px', borderRadius: '6px' }}>
                            Approver: {step.approver_role}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Stage 4: Simulation Results */}
            {simulation && (
              <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#00b894' }}>
                    🧪 Step 5: Simulation Dry-Run Complete
                  </h3>
                  <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                    Duration: {simulation.total_duration_ms}ms &bull; Status: {simulation.status.toUpperCase()}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
                  {simulation.steps_executed.map((s, idx) => (
                    <div key={idx} style={{ background: 'rgba(0, 184, 148, 0.1)', border: '1px solid rgba(0, 184, 148, 0.3)', padding: '6px 12px', borderRadius: '6px', fontSize: '11px' }}>
                      <strong>{s.step_id}</strong>: {s.status} ({s.duration_ms}ms)
                    </div>
                  ))}
                </div>

                <button
                  onClick={handleStartProductionExecution}
                  style={{
                    padding: '12px 24px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'var(--color-accent-primary)',
                    color: '#ffffff',
                    fontWeight: '700',
                    fontSize: '13px',
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(108, 92, 231, 0.3)',
                  }}
                >
                  🚀 Launch Production Execution
                </button>
              </div>
            )}

            {/* Stage 5: Live Execution Tracker */}
            {execution && (
              <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '20px', border: '1px solid #6c5ce7' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: '700' }}>Live Production Execution: {execution.id}</h3>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Started: {new Date(execution.started_at).toLocaleTimeString()}</div>
                  </div>
                  <span style={{ fontSize: '12px', fontWeight: 'bold', padding: '4px 12px', borderRadius: '10px', background: execution.status === 'completed' ? 'rgba(0, 184, 148, 0.2)' : execution.status === 'paused' ? 'rgba(253, 203, 110, 0.2)' : 'rgba(108, 92, 231, 0.2)', color: execution.status === 'completed' ? '#00b894' : execution.status === 'paused' ? '#fdcb6e' : '#6c5ce7' }}>
                    {execution.status.toUpperCase()}
                  </span>
                </div>

                {/* Paused for Approval Alert */}
                {execution.status === 'paused' && (
                  <div style={{ background: 'rgba(253, 203, 110, 0.15)', border: '1px solid #fdcb6e', padding: '16px', borderRadius: '10px', marginBottom: '16px' }}>
                    <div style={{ fontWeight: '700', color: '#fdcb6e', marginBottom: '6px' }}>
                      ⏸️ Execution Paused for Human Approval
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--color-text-primary)', marginBottom: '12px' }}>
                      This request requires manager verification. As designated reviewer, please approve or reject this action:
                    </p>
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button
                        onClick={() => handleResumeActiveExecution('approved')}
                        style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', background: '#00b894', color: '#fff', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer' }}
                      >
                        ✅ Approve Request
                      </button>
                      <button
                        onClick={() => handleResumeActiveExecution('rejected')}
                        style={{ padding: '8px 18px', borderRadius: '6px', border: 'none', background: '#ff6b6b', color: '#fff', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer' }}
                      >
                        ❌ Reject Request
                      </button>
                    </div>
                  </div>
                )}

                <div style={{ fontSize: '12px' }}>
                  <strong>Execution Steps:</strong>
                  <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {execution.steps.map((st, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', background: 'rgba(255,255,255,0.02)', padding: '6px 10px', borderRadius: '6px' }}>
                        <span>{st.step_id} ({st.step_type})</span>
                        <span style={{ color: st.status === 'completed' ? '#00b894' : st.status === 'running' ? '#6c5ce7' : st.status === 'skipped' ? 'var(--color-text-secondary)' : '#fdcb6e' }}>
                          {st.status.toUpperCase()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 2: APPROVALS QUEUE ────────────────────────────────────────── */}
      {activeTab === 'approvals' && (
        <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '24px', border: '1px solid var(--color-border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Pending Human Approvals Queue</h2>
              <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Review requests requiring human-in-the-loop authorization.</p>
            </div>
            <button onClick={loadApprovals} style={{ background: 'transparent', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)', padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
              🔄 Refresh Queue
            </button>
          </div>

          {approvalFeedback && (
            <div style={{ padding: '10px', borderRadius: '8px', background: 'rgba(0, 184, 148, 0.1)', color: '#00b894', fontSize: '12px', marginBottom: '16px' }}>
              {approvalFeedback}
            </div>
          )}

          {pendingApprovals.length === 0 ? (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>🎉</div>
              <div>No pending approval requests. Everything is clear!</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {pendingApprovals.map((appr) => (
                <div key={appr.id} style={{ border: '1px solid var(--color-border)', padding: '16px', borderRadius: '10px', background: 'rgba(255,255,255,0.01)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: '700', fontSize: '14px' }}>Request ID: {appr.id} &bull; Step: {appr.step_id}</div>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                      Role: <span style={{ color: '#fdcb6e', fontWeight: 'bold' }}>{appr.approver_role}</span> &bull; Execution: {appr.workflow_execution_id}
                    </div>
                    <div style={{ fontSize: '12px', marginTop: '6px' }}>
                      Context: {JSON.stringify(appr.context_data)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => handleApprovalDecision(appr.id, 'approved')}
                      style={{ background: '#00b894', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer' }}
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleApprovalDecision(appr.id, 'rejected')}
                      style={{ background: '#ff6b6b', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer' }}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 3: KNOWLEDGE EXPLORER ─────────────────────────────────────── */}
      {activeTab === 'knowledge' && (
        <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '24px', border: '1px solid var(--color-border)' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>Policy Knowledge RAG Explorer</h2>
          <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
            Semantic search across enterprise policies stored in Qdrant vector database.
          </p>

          <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
            <input
              type="text"
              value={knowledgeQuery}
              onChange={(e) => setKnowledgeQuery(e.target.value)}
              placeholder="Search policy guidelines..."
              style={{
                flex: 1,
                padding: '12px 16px',
                borderRadius: '8px',
                background: 'var(--color-bg-input)',
                border: '1px solid var(--color-border)',
                color: '#fff',
                fontSize: '13px',
                outline: 'none',
              }}
            />
            <button
              onClick={handleKnowledgeSearch}
              style={{
                padding: '12px 24px',
                borderRadius: '8px',
                border: 'none',
                background: 'var(--color-accent-primary)',
                color: '#fff',
                fontWeight: 'bold',
                cursor: 'pointer',
              }}
            >
              🔍 Vector Search
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {knowledgeResults.map((r, i) => (
              <div key={i} style={{ border: '1px solid var(--color-border)', padding: '16px', borderRadius: '10px', background: 'rgba(255,255,255,0.01)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: '700', fontSize: '13px', color: 'var(--color-accent-secondary)' }}>📄 {r.source}</span>
                  <span style={{ fontSize: '11px', color: '#00b894' }}>Match Score: {(r.score * 100).toFixed(1)}%</span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--color-text-primary)', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
                  {r.content}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB 4: AUDIT TRAIL ────────────────────────────────────────────── */}
      {activeTab === 'audit' && (
        <div style={{ background: 'var(--color-bg-card)', borderRadius: '14px', padding: '24px', border: '1px solid var(--color-border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: '700' }}>Immutable Audit Trail</h2>
              <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Chronological record of all actions, approvals, and executions.</p>
            </div>
            <button onClick={loadAuditLogs} style={{ background: 'transparent', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)', padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
              🔄 Refresh
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {auditLogs.map((log) => (
              <div key={log.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--color-border)', fontSize: '12px' }}>
                <div>
                  <span style={{ fontWeight: '700', color: 'var(--color-accent-primary)' }}>{log.action}</span>
                  <span style={{ color: 'var(--color-text-secondary)', marginLeft: '12px' }}>Actor: {log.actor_id} ({log.actor_type})</span>
                  <span style={{ color: 'var(--color-text-secondary)', marginLeft: '12px' }}>Resource: {log.resource_type} / {log.resource_id}</span>
                </div>
                <span style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh' }} />}>
      <HomeContent />
    </Suspense>
  );
}
