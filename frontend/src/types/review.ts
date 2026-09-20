export type RiskLevel = "low" | "medium" | "high" | "unassessed";

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
  status?: string;
  assigned_to?: string | null;
  assigned_at?: string | null;
  missing_documents?: string[];
  reviewer_summary?: ReviewerSummary | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  limit: number;
  offset: number;
  returned: number;
}

export interface ClaimAssignmentRequest {
  assigned_to: string;
}

export interface ClaimAssignmentResponse {
  assignment_id: string;
  workflow_id: string;
  claim_id: string;
  assigned_to: string;
  assigned_by: string;
  assigned_at: string;
  status: string;
  message: string;
}

export interface HumanDecisionRequest {
  decision: "approve" | "reject" | "request_more_information" | "escalate";
  reason: string;
  notes?: string | null;
  settlement_amount?: number | null;
}

export interface HumanDecisionResponse {
  workflow_id: string;
  claim_id: string;
  decision_id: string;
  decision: string;
  claim_status: string;
  decided_at: string;
  status: string;
  message: string;
}

export interface ClaimDocumentItem {
  document_id: string;
  claim_id: string;
  customer_id?: string;
  document_type: string;
  original_filename: string;
  file_size_bytes?: number;
  content_type?: string;
  uploaded_at?: string;
}

export interface ClaimContextDetails {
  claim_id?: string;
  claim_reference?: string;
  customer_id?: string;
  incident_type?: string;
  incident_date?: string;
  incident_location?: string;
  incident_description?: string;
  claimed_amount?: number | null;
  claim_status?: string;
  policy_id?: string;
  policy_number?: string;
}

export interface PolicyContextDetails {
  policy_id?: string;
  policy_number?: string;
  customer_id?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  coverage_details?: Record<string, unknown>;
  exclusions?: string[];
}

export interface FraudIndicatorDetails {
  rule_name?: string;
  description?: string;
  severity?: string;
}

export interface FraudAssessmentDetails {
  risk_level?: string;
  risk_score?: number | null;
  recommended_action?: string;
  indicators?: FraudIndicatorDetails[];
}

export interface ReviewerGuidanceResultDetails {
  status?: string;
  data?: {
    reviewer_summary?: ReviewerSummary;
  };
}

export interface HumanDecisionDetails {
  decision_id?: string;
  workflow_id?: string;
  claim_id?: string;
  decision?: string;
  reviewer_id?: string;
  reviewer_role?: string;
  reason?: string;
  notes?: string;
  decided_at?: string;
}

export interface ReviewDetailResponse {
  workflow_id: string;
  status: string;
  claim: ClaimContextDetails;
  policy?: PolicyContextDetails;
  retrieval_context?: Record<string, unknown>;
  fraud_assessment?: FraudAssessmentDetails;
  reviewer_guidance_result?: ReviewerGuidanceResultDetails;
  audit_timeline?: Record<string, unknown>[];
  human_decision?: HumanDecisionDetails;
  documents: ClaimDocumentItem[];
  assigned_to?: string | null;
  assigned_at?: string | null;
}
