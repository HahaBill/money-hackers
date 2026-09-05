export type Headline = {
  metric: string;
  change: number;
  change_pct?: number;
  context?: string;
  node?: string;
};

export type Hypothesis = {
  id: string;
  class: string;
  verdict: 'supported' | 'unresolved' | 'weakening' | 'rejected' | string;
  posterior: number;
  claim: string;
};

export type Finding = {
  id: string;
  node?: string;
  severity: string;
  title: string;
  leaf: string;
  attribution_dollars: number;
  z: number;
  confidence: number;
  confidence_cap?: number;
  attribution?: string[];
  concentration?: string[];
  evidence?: string[];
  simulations?: string[];
  directives?: string[];
  hypotheses: Hypothesis[];
};

export type Question = {
  id: string;
  text: string;
  options: string[];
  leaf?: string;
  class?: string;
  voi_dollars?: number;
};

export type VerifyItem = {
  node: string;
  rule: string;
  entity: string;
  gap_dollars: number;
  counter_explanation: string;
  detail?: string;
  evidence_rows?: string[];
};

export type Simulation = {
  node: string;
  leaf: string;
  delta_pct: number;
  delta_profit: number;
  assumption: string;
  volume_response_pct?: number | null;
  sweep_range?: [number, number] | null;
  confidence: number;
};

export type Directive = {
  node: string;
  driver: string;
  current: number;
  unit: string;
  normal_range: [number, number];
  direction: string;
  target: number;
  gap_dollars_month: number;
  controllability: number;
  indicator: string;
  justifies: string[];
  review_period: string;
};

export type Concentration = {
  node: string;
  leaf: string;
  hhi: number;
  label: string;
  contributors: Array<{
    entity: string;
    dollars: number;
    share: number;
    recurring_top: boolean;
  }>;
};

export type RunReport = {
  period: string;
  run_id: string;
  status: 'complete' | 'blocked' | string;
  reconciliation: string;
  confidence_regime?: string;
  headline: Headline;
  findings: Finding[];
  questions: Question[];
  verify: VerifyItem[];
  improved?: unknown[];
  revisions?: Array<{ summary?: string; old?: string; new?: string }>;
  next_period_watch?: string[];
  simulations?: Simulation[];
  directives?: Directive[];
  concentrations?: Concentration[];
  narrative?: Record<string, string | Record<string, string>>;
  checks?: Array<{ label?: string; status?: string; detail?: string }>;
  source_workbook?: string;
  prevalidated_summary?: string;
  workbook_rows?: SheetRow[];
  observability?: {
    captured_at: string;
    live_traces: number;
    active_agents: number;
    average_latency_seconds: number;
    guardrail_blocks: number;
    compliance_score_pct: number;
    cost_today: number;
  };
};

export type RunSummary = {
  run_id: string;
  period?: string;
  status: string;
  headline?: Headline;
  finding_count: number;
  graph_node_count: number;
  updated_at: number;
};

export type ChatTurn = { role: 'user' | 'assistant'; text: string };

export type ChatReply = {
  answer: string;
  sources: string[];
  mode: 'model' | 'deterministic';
};

export type Attribution = { node: string | null; driver: string; dollars: number };

export type SheetRow = {
  key: string;
  kind: 'metric' | 'cause';
  label: string;
  prior: number | null;
  current: number | null;
  change: number | null;
  confidence: number | null;
  note: string;
  node: string | null;
};

export type Dashboard = {
  business: { name: string };
  report: RunReport;
  metrics: Record<string, unknown>;
  attributions: Attribution[];
  attribution_summary: Attribution[];
  attribution_total: number;
  sheet_rows: SheetRow[];
  graph_counts: { nodes: number; edges: number };
};

export type GraphNode = {
  id: string;
  type: string;
  period: string;
  run_id: string;
  label: string;
  value: unknown;
  unit?: string | null;
  formula?: string | null;
  method?: string | null;
  inputs: string[];
  confidence: number;
  status: string;
  supersedes?: string | null;
  provenance: string;
  payload: Record<string, unknown>;
  created_at?: string;
};

export type GraphEdge = {
  src: string;
  dst: string;
  type: string;
  period: string;
  run_id: string;
};

export type RunGraph = { run_id: string; nodes: GraphNode[]; edges: GraphEdge[] };
