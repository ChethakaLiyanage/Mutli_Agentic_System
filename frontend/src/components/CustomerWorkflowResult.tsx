import type {
  CustomerEvidence,
  OrchestratorResponse,
} from "../types/orchestrator";

const OUTCOME_HEADINGS = {
  approved: "Your claim has been approved",
  rejected: "Your claim review is complete",
  more_information_required: "More information is required",
  escalated: "Your claim needs additional review",
} as const;

const uniqueMessages = (...groups: Array<string[] | undefined>): string[] =>
  [...new Set(groups.flatMap((group) => group ?? []).filter(Boolean))];

const EvidenceList = ({
  evidence,
  headingId,
}: {
  evidence: CustomerEvidence[];
  headingId: string;
}) => {
  if (!evidence.length) return null;

  return (
    <section className="evidence-section" aria-labelledby={headingId}>
      <h3 id={headingId}>Sources used</h3>
      <div className="evidence-list">
        {evidence.map((item, index) => (
          <article
            className="evidence-item"
            key={item.evidence_id ?? `${item.source_title}-${item.section ?? index}`}
          >
            <strong>{item.source_title}</strong>
            {item.section && <span>Section: {item.section}</span>}
            {item.content && <p>{item.content}</p>}
            {typeof item.score === "number" && (
              <small>Relevance: {Math.round(item.score * 100)}%</small>
            )}
          </article>
        ))}
      </div>
    </section>
  );
};

interface CustomerWorkflowResultProps {
  workflow: OrchestratorResponse;
  refreshing: boolean;
  onRefresh: () => void;
  onUploadClick?: () => void;
}

export const CustomerWorkflowResult = ({
  workflow,
  refreshing,
  onRefresh,
  onUploadClick,
}: CustomerWorkflowResultProps) => {
  const headingSuffix = workflow.workflow_id.replace(/[^a-zA-Z0-9_-]/g, "-");
  const resultHeadingId = `customer-result-heading-${headingSuffix}`;
  const nextStepsHeadingId = `next-steps-heading-${headingSuffix}`;
  const evidenceHeadingId = `evidence-heading-${headingSuffix}`;
  const warningsHeadingId = `warnings-heading-${headingSuffix}`;
  const guidance = workflow.guidance_result;
  const guidanceMessage = guidance?.data.message?.trim();
  const responseMessage = workflow.message?.trim();
  const warnings = uniqueMessages(workflow.warnings, guidance?.warnings);
  const nextSteps = guidance?.data.next_steps ?? [];
  const insufficientEvidence =
    guidance?.status === "insufficient_evidence" ||
    guidance?.data.insufficient_evidence === true ||
    /insufficient evidence|not enough (?:policy )?information/i.test(
      guidanceMessage || responseMessage || "",
    );

  if (workflow.status === "awaiting_human_review") {
    return (
      <section className="customer-result customer-result-review" aria-live="polite">
        <p className="eyebrow">Claim submitted</p>
        <h2>Your claim is awaiting human review</h2>
        {responseMessage && <p>{responseMessage}</p>}
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap" }}>
          {onUploadClick && (
            <button
              className="upload-docs-btn"
              type="button"
              onClick={onUploadClick}
            >
              <span className="upload-icon">📤</span>
              Upload Documents
            </button>
          )}
          <button
            className="button button-primary"
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
          >
            {refreshing ? "Checking status…" : "Check status"}
          </button>
        </div>
      </section>
    );
  }

  const outcomeHeading =
    workflow.status in OUTCOME_HEADINGS
      ? OUTCOME_HEADINGS[workflow.status as keyof typeof OUTCOME_HEADINGS]
      : null;
  const showCompletedResult =
    workflow.status === "completed" || outcomeHeading !== null;

  if (!showCompletedResult) return null;

  return (
    <section
      className={`customer-result customer-result-${workflow.status}`}
      aria-labelledby={resultHeadingId}
      aria-live="polite"
    >
      <div className="customer-result-heading">
        <div>
          <p className="eyebrow">
            {outcomeHeading ? "Claim outcome" : "Your answer"}
          </p>
          <h2 id={resultHeadingId}>
            {outcomeHeading ?? "Policy guidance"}
          </h2>
        </div>
        {guidance?.data.grounded && (
          <span className="grounded-label">Grounded in policy information</span>
        )}
      </div>

      {insufficientEvidence ? (
        <div className="insufficient-evidence" role="status">
          <strong>Limited information available</strong>
          {(guidanceMessage || responseMessage) && (
            <p>{guidanceMessage || responseMessage}</p>
          )}
        </div>
      ) : (
        (guidanceMessage || responseMessage) && (
          <p className="guidance-message">
            {guidanceMessage || responseMessage}
          </p>
        )
      )}

      {nextSteps.length > 0 && (
        <section className="next-steps" aria-labelledby={nextStepsHeadingId}>
          <h3 id={nextStepsHeadingId}>Next steps</h3>
          <ul>
            {nextSteps.map((step) => <li key={step}>{step}</li>)}
          </ul>
        </section>
      )}

      <EvidenceList
        evidence={workflow.evidence_summary}
        headingId={evidenceHeadingId}
      />

      {warnings.length > 0 && (
        <section className="workflow-warnings" aria-labelledby={warningsHeadingId}>
          <h3 id={warningsHeadingId}>Important information</h3>
          <ul>
            {warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </section>
      )}
    </section>
  );
};
