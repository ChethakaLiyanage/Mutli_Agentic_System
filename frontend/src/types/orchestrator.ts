type FutureValue = string & {};

export type WorkflowStatus =
  | "received"
  | "intake_processing"
  | "intake_complete"
  | "awaiting_clarification"
  | "manual_assistance_required"
  | "information_retrieval"
  | "fraud_triage"
  | "awaiting_human_review"
  | "guidance_processing"
  | "completed"
  | "failed"
  | FutureValue;

export type WorkflowType =
  | "information_request"
  | "claim_submission"
  | "claim_status"
  | "clarification"
  | "unknown"
  | FutureValue;

export type AuditEventStatus =
  | "started"
  | "success"
  | "awaiting_input"
  | "failed"
  | FutureValue;

export interface OrchestratorRequest {
  request_id: string;
  text: string;
}

export type ClarificationRequest = OrchestratorRequest;

export interface IntentResult {
  label:
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

export interface OrchestratorResponse {
  request_id: string;
  workflow_id: string;
  status: WorkflowStatus;
  workflow_type: WorkflowType;
  intake_result: IntakeResult | null;
  retrieval_result: Record<string, unknown> | null;
  fraud_result: Record<string, unknown> | null;
  human_review_result: Record<string, unknown> | null;
  guidance_result: Record<string, unknown> | null;
  missing_fields: string[];
  requires_clarification: boolean;
  errors: OrchestratorError[];
  audit_trail: AuditEvent[];
}

export interface ClarificationResponse {
  request_id: string;
  workflow_id: string;
  status: WorkflowStatus;
  workflow_type: WorkflowType;
  intake_result: IntakeResult | null;
  missing_fields: string[];
  questions: string[];
  reason: string | null;
  requires_clarification: true;
  audit_trail: AuditEvent[];
}

export type WorkflowResponse = OrchestratorResponse | ClarificationResponse;

export const isClarificationResponse = (
  response: WorkflowResponse,
): response is ClarificationResponse => "questions" in response;
