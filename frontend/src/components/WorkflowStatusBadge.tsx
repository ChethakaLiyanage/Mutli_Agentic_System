import type { WorkflowStatus } from "../types/orchestrator";

const STATUS_LABELS = {
  received: "Received",
  intake_processing: "Processing Intake",
  awaiting_clarification: "Needs More Information",
  awaiting_documents: "Awaiting Documents",
  manual_assistance_required: "Manual Assistance Required",
  intake_complete: "Intake Complete",
  information_retrieval: "Retrieving Information",
  retrieval_complete: "Information Retrieved",
  claim_information_retrieval: "Checking Claim Information",
  fraud_triage: "Processing Claim",
  awaiting_human_review: "Awaiting Human Review",
  guidance_processing: "Preparing Guidance",
  guidance_generation: "Preparing Response",
  completed: "Completed",
  approved: "Approved",
  rejected: "Review Completed",
  more_information_required: "More Information Required",
  escalated: "Additional Review",
  failed: "Unable to Continue",
} satisfies Record<WorkflowStatus, string>;

export const WorkflowStatusBadge = ({ status }: { status: WorkflowStatus }) => (
  <span className={`workflow-status workflow-status-${status}`}>
    {STATUS_LABELS[status]}
  </span>
);
