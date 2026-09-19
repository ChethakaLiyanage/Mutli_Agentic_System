export type RiskLevel = "low" | "medium" | "high";

export interface ReviewerSummary {
  claim_overview: string;
  policy_findings: string[];
  risk_observations: string[];
  missing_items: string[];
  reviewer_action_points: string[];
}

export interface ReviewQueueItem {
  workflow_id: string;
  claim_id: string;
  created_at: string;
  updated_at: string;
  claim_status: string | null;
  incident_type: string | null;
  incident_date: string | null;
  location: string | null;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  recommended_action: string | null;
  risk_indicator_count: number;
  missing_documents: string[];
  reviewer_summary: ReviewerSummary | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  limit: number;
  offset: number;
  returned: number;
}
