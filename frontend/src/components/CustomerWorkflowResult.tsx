import type {
  CustomerEvidence,
  OrchestratorResponse,
} from "../types/orchestrator";

const OUTCOME_HEADINGS = {
  approved: "Your claim has been approved",
  rejected: "Your claim review is complete",
  more_information_required: "More information is required",
  awaiting_documents: "Supporting documents required",
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
  onSubmitClaim?: () => void;
  submitting?: boolean;
}

export const CustomerWorkflowResult = ({
  workflow,
  refreshing,
  onRefresh,
  onUploadClick,
  onSubmitClaim,
  submitting,
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

  if (workflow.status === "awaiting_documents") {
    const isEligibleClaim =
      workflow.workflow_type === "claim_submission" && Boolean(workflow.claim_id);

    return (
      <section className="customer-result customer-result-review" aria-live="polite">
        <p className="eyebrow">Claim draft created</p>
        <h2>Supporting documents required</h2>
        {responseMessage && <p style={{ whiteSpace: "pre-line" }}>{responseMessage}</p>}
        {workflow.missing_required_documents && workflow.missing_required_documents.length > 0 && (
          <div style={{ backgroundColor: "#fff5df", border: "1px solid #fae1a0", padding: "10px 14px", borderRadius: "8px", margin: "1rem 0", color: "#a66800", fontSize: "13px" }}>
            <strong>Missing required documents:</strong>
            <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
              {workflow.missing_required_documents.map((doc) => (
                <li key={doc}>{doc.replace(/_/g, " ")}</li>
              ))}
            </ul>
          </div>
        )}
        {isEligibleClaim && (
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap", alignItems: "center" }}>
            {onUploadClick && (
              <button
                className="upload-docs-btn"
                type="button"
                onClick={onUploadClick}
              >
                <span className="upload-icon">📤</span>
                Attach Documents
              </button>
            )}
            {onSubmitClaim && (
              <button
                className="button button-primary"
                type="button"
                onClick={onSubmitClaim}
                disabled={submitting}
              >
                {submitting ? "Submitting Claim…" : "Submit Claim"}
              </button>
            )}
          </div>
        )}
      </section>
    );
  }

  if (
    workflow.status === "documents_submitted" ||
    workflow.status === "fraud_triage" ||
    workflow.status === "fraud_triage_complete" ||
    workflow.status === "review_summary_generation" ||
    workflow.status === "awaiting_assignment"
  ) {
    return (
      <section className="customer-result customer-result-review" aria-live="polite">
        <p className="eyebrow">Claim submitted</p>
        <h2>Claim queued for assignment</h2>
        <p>{responseMessage || "Your claim has been submitted successfully and is queued for assignment to a claims officer."}</p>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap", alignItems: "center" }}>
          <a
            href="/dashboard/claims"
            style={{
              backgroundColor: "#123c42",
              color: "white",
              padding: "8px 16px",
              borderRadius: "8px",
              textDecoration: "none",
              fontWeight: "600",
              fontSize: "13px",
            }}
          >
            View in My Claims →
          </a>
          <button
            className="button button-secondary"
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

  if (workflow.status === "under_human_review" || workflow.status === "awaiting_human_review") {
    return (
      <section className="customer-result customer-result-review" aria-live="polite">
        <p className="eyebrow">Review in progress</p>
        <h2>Your claim is under human review</h2>
        <p>{responseMessage || "Your claim has been assigned to a claims officer and is currently under review."}</p>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap", alignItems: "center" }}>
          <a
            href="/dashboard/claims"
            style={{
              backgroundColor: "#123c42",
              color: "white",
              padding: "8px 16px",
              borderRadius: "8px",
              textDecoration: "none",
              fontWeight: "600",
              fontSize: "13px",
            }}
          >
            View in My Claims →
          </a>
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
