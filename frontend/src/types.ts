export interface QueryOptions {
  ensemble_mode: string;
  enable_web_search?: boolean;
  enable_technical?: boolean;
  max_pipelines?: number;
}

export interface PipelineStatus {
  slot_name: string;
  display_name: string;
  provider: string;
  status: 'queued' | 'running' | 'complete' | 'failed' | 'timeout';
  latency_ms?: number;
  error?: string;
}

export interface QueryStatus {
  query_id: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
  progress_pct: number;
  pipelines: PipelineStatus[];
  created_at: string;
  updated_at: string;
  error?: string;
}

export interface ConfidenceBreakdown {
  provider_agreement: number;
  source_quality: number;
  factual_consistency: number;
  hallucination_safety: number;
}

export interface ConfidenceResult {
  overall_score: number;
  label: 'high' | 'medium' | 'low';
  breakdown: ConfidenceBreakdown;
  uncertainty_notes: string[];
}

export interface Source {
  url: string;
  title: string;
  domain: string;
  trust_score: number;
  snippet?: string;
}

export interface ExecutionMetadata {
  total_latency_ms: number;
  pipelines_run: number;
  pipelines_failed: number;
  total_input_tokens: number;
  total_output_tokens: number;
  estimated_cost_usd: number;
  ensemble_mode: string;
  provider_used: string;
}

export interface FinalResponse {
  query_id: string;
  status: string;
  executive_summary: string;
  detailed_answer: string;
  key_findings: string[];
  conflicting_viewpoints: string[];
  limitations: string[];
  confidence: ConfidenceResult;
  sources: Source[];
  execution_metadata: ExecutionMetadata;
  created_at: string;
}

export interface QueryResult {
  query_id: string;
  status: string;
  warnings?: string[];
  final_response?: FinalResponse;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  slot: string;
  preferred_providers: string[];
}

export interface AgentsResponse {
  agents: Agent[];
  pipeline_modes: Record<string, string[]>;
}

export interface HistoryEntry {
  query_id: string;
  query: string;
  status: string;
  confidence?: number;
  created_at: string;
  mode?: string;
  pipeline_mode?: string;
}

export interface AppSettings {
  // Connection
  apiBaseUrl: string;
  apiKey: string;

  // Pipeline
  defaultMode: string;
  defaultPipelineMode: 'fast' | 'balanced' | 'deep';
  defaultEnsembleMode: string;
  enableWebSearch: boolean;
  enableTechnical: boolean;
  maxPipelines: number;
  providerTimeout: number;

  // Appearance
  theme: 'dark' | 'light' | 'system';
  accentColor: string;
  fontSize: 'sm' | 'md' | 'lg';
  density: 'compact' | 'default' | 'comfortable';

  // Advanced
  historyRetentionDays: number;
  debugMode: boolean;
  maxCostPerQuery: number;
  maxTokensPerQuery: number;
}

export interface WSEvent {
  event: string;
  stage?: string;
  detail?: string;
  [key: string]: unknown;
}
