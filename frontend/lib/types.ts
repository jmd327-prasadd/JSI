export interface Project {
  id: string;
  name: string;
  client_name: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Artifact {
  id: string;
  original_filename: string;
  size_bytes: number;
  extraction_status: string;
  inventory_summary: Record<string, unknown>;
  created_at: string;
}

export interface DocumentUpload {
  id: string;
  original_filename: string;
  file_type: string;
  conversion_status: string;
  created_at: string;
}

export interface ConnectionStub {
  id: string;
  connector_type: string;
  status: string;
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  status: string;
  progress_pct: number;
  status_message: string;
  error_message: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Finding {
  id: string;
  rule_id: string;
  category: string;
  subcategory: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  severity_base: string;
  detection_type: "deterministic" | "llm_assisted" | "hybrid";
  title: string;
  component: string;
  evidence: string;
  evidence_lines: number[];
  impact: string;
  recommendation: string;
  verification: string;
  confidence: string;
  context: string;
  layer: string;
  domain: string;
  upstream_models: string[];
  downstream_models: string[];
  transitive_downstream_count: number;
  impact_note: string;
  ai_reasoning: string;
  ai_evidence_cited: string[];
  status: string;
  reviewer_note: string;
  created_at: string;
}

export interface RunSummary {
  run_id: string;
  status: string;
  counts_by_severity: Record<string, number>;
  counts_by_category: Record<string, number>;
  total_findings: number;
  traffic_light_by_category: Record<string, "Red" | "Amber" | "Green">;
  readiness_score_by_category: Record<string, number>;
  recommended_action: string;
  punch_list: string[];
}

export const FINDING_STATUSES = [
  "New",
  "Acknowledged",
  "Needs Dev Fix",
  "False Positive",
  "Won't Fix",
] as const;

export const RUN_TERMINAL_STATUSES = new Set(["done", "failed"]);
