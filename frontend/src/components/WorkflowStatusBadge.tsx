import type { WorkflowStatus } from "../types/orchestrator";

const STATUS_LABELS: Record<string, string> = {
  received: "Received",
  intake_processing: "Processing Intake",
  intake_complete: "Intake Complete",
  awaiting_clarification: "Needs More Information",
  manual_assistance_required: "Manual Assistance Required",
  information_retrieval: "Retrieving Information",
  fraud_triage: "Fraud Triage",
  awaiting_human_review: "Awaiting Human Review",
  guidance_processing: "Preparing Guidance",
  completed: "Completed",
  failed: "Unable to Continue",
};

const toFriendlyLabel = (status: string): string =>
  status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export const WorkflowStatusBadge = ({ status }: { status: WorkflowStatus }) => (
  <span className={`workflow-status workflow-status-${status}`}>
    {STATUS_LABELS[status] ?? toFriendlyLabel(status)}
  </span>
);
