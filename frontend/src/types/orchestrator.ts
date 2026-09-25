export type WorkflowStatus =
  | "received"
  | "intake_processing"
  | "awaiting_clarification"
  | "awaiting_documents"
  | "documents_submitted"
  | "manual_assistance_required"
  | "intake_complete"
  | "information_retrieval"
  | "retrieval_complete"
  | "claim_information_retrieval"
  | "fraud_triage"
  | "fraud_triage_complete"
  | "review_summary_generation"
  | "awaiting_assignment"
  | "under_human_review"
  | "awaiting_human_review"
  | "guidance_processing"
  | "guidance_generation"
  | "completed"
  | "approved"
  | "rejected"
  | "more_information_required"
  | "escalated"
  | "failed";

export type WorkflowType =
  | "information_request"
  | "claim_submission"
  | "claim_status"
  | "clarification"
  | "unknown";

export type AuditEventStatus =
  | "started"
  | "success"
  | "awaiting_input"
  | "failed";

export interface OrchestratorRequest {
  request_id: string;
  text: string;
  context_workflow_id?: string;
}

export type ClarificationRequest = OrchestratorRequest;

export interface IntentResult {
  label:
    | "greeting"
    | "claim_submission"
    | "policy_question"
    | "coverage_question"
    | "required_documents_question"
    | "claim_status"
    | "general_information"
    | null;
  confidence: number;
}

export interface ExtractedEntity {
  entity_type: string;
  value: string;
  start: number | null;
  end: number | null;
  confidence: number | null;
}

export interface IncidentInformation {
  type:
    | "vehicle_collision"
    | "windscreen_damage"
    | "flood_damage"
    | "theft_or_break_in"
    | null;
  date_text: string | null;
  normalized_date: string | null;
  location: string | null;
}

export interface DamageInformation {
  areas: string[];
  description: string | null;
}

export interface IntakeResult {
  request_id: string;
  agent: "claim_intake";
  status: "success" | "pending" | "needs_clarification" | "error";
  data: {
    intent: IntentResult;
    insurance_type: "motor";
    incident: IncidentInformation;
    damage: DamageInformation;
    entities: ExtractedEntity[];
    missing_fields: string[];
    requires_clarification: boolean;
  };
  errors: string[];
}

export interface AuditEvent {
  step: string;
  status: AuditEventStatus;
  message: string;
  timestamp: string;
}

export interface OrchestratorError {
  code: string;
  message: string;
  step: string | null;
}

export type GuidanceStatus = "success" | "insufficient_evidence" | "error";

export type GuidanceResponseType =
  | "greeting"
  | "claim_submission_start"
  | "information_answer"
  | "coverage_answer"
  | "policy_answer"
  | "claim_progress"
  | "awaiting_human_review"
  | "human_decision"
  | "insufficient_evidence"
  | "manual_assistance_required"
  | "safe_error"
  | "coverage_explanation"
  | "policy_explanation"
  | "required_documents"
  | "required_documents_information"
  | "claim_document_requirements"
  | "claim_status"
  | "claim_information"
  | "authorization_denied"
  | "next_steps"
  | "clarification_question"
  | "reviewer_summary"
  | "fraud_indicator_explanation"
  | "final_decision_explanation";

export interface CustomerGuidanceData {
  message?: string;
  next_steps?: string[];
  evidence_used?: string[];
  insufficient_evidence?: boolean;
  grounded?: boolean;
}

export interface CustomerGuidanceResult {
  status: GuidanceStatus;
  response_type: GuidanceResponseType;
  agent: "guidance_agent";
  data: CustomerGuidanceData;
  warnings?: string[];
  created_at?: string;
}

export interface CustomerEvidence {
  evidence_id?: string;
  source_title: string;
  section?: string | null;
  content?: string;
  score?: number | null;
}

interface WorkflowResponseBase {
  request_id: string;
  workflow_id: string;
  claim_id?: string | null;
  status: WorkflowStatus;
  workflow_type: WorkflowType;
  intake_result: IntakeResult | null;
  missing_fields: string[];
  requires_clarification: boolean;
  audit_trail: AuditEvent[];
}

export interface OrchestratorResponse extends WorkflowResponseBase {
  retrieval_status: string | null;
  warnings: string[];
  evidence_summary: CustomerEvidence[];
  message: string | null;
  guidance_result: CustomerGuidanceResult | null;
  missing_required_documents?: string[];
  pending_claim_workflow_id?: string | null;
  errors: OrchestratorError[];
}

export interface ClarificationResponse extends WorkflowResponseBase {
  status: "awaiting_clarification";
  workflow_type: "clarification";
  questions: string[];
  reason: string | null;
  message: string | null;
  guidance_result: CustomerGuidanceResult | null;
  requires_clarification: true;
}

export type WorkflowResponse = OrchestratorResponse | ClarificationResponse;

export const isClarificationResponse = (
  response: WorkflowResponse,
): response is ClarificationResponse => "questions" in response;

export const isOrchestratorResponse = (
  response: WorkflowResponse,
): response is OrchestratorResponse => "evidence_summary" in response;
