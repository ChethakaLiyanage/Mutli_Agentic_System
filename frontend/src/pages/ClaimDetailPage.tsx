import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../api/client";
import { fetchClaimDetail } from "../api/claims";
import { recheckWorkflowDocuments } from "../api/orchestrator";
import { DocumentUploadModal } from "../components/DocumentUploadModal";
import type { ClaimDetailCustomer } from "../types/claim";

const formatIncidentType = (type: string | null | undefined): string => {
  if (!type) return "Motor Insurance Claim";
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatFileSize = (bytes?: number): string => {
  if (!bytes) return "";
  const kb = Math.round(bytes / 1024);
  if (kb > 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${kb} KB`;
};

export const ClaimDetailPage = () => {
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<ClaimDetailCustomer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const [recheckMessage, setRecheckMessage] = useState<string | null>(null);

  const loadClaim = useCallback(() => {
    if (!claimId) return;
    setLoading(true);
    setError(null);
    void fetchClaimDetail(claimId)
      .then((data) => {
        setClaim(data);
        const action = new URLSearchParams(window.location.search).get("action");
        if (
          action === "upload-documents" &&
          data.workflow_id &&
          (data.workflow_status === "more_information_required" ||
            data.workflow_status === "awaiting_documents")
        ) {
          setUploadModalOpen(true);
          const cleanUrl = new URL(window.location.href);
          cleanUrl.searchParams.delete("action");
          window.history.replaceState({}, "", cleanUrl.toString());
        }
      })
      .catch((err) => {
        setError(
          err.response?.status === 404
            ? "Claim not found."
            : "Unable to load claim details.",
        );
      })
      .finally(() => setLoading(false));
  }, [claimId]);

  const handleOpenDocument = async (docId: string) => {
    try {
      const res = await apiClient.get(`/documents/${encodeURIComponent(docId)}/download`, {
        responseType: "blob",
      });
      const blobType = String(res.headers["content-type"] || "application/pdf");
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: blobType }));
      window.open(blobUrl, "_blank");
    } catch {
      alert("Could not open document. Please try again.");
    }
  };

  const handleDownloadDocument = async (docId: string, filename?: string) => {
    try {
      const res = await apiClient.get(`/documents/${encodeURIComponent(docId)}/download?as_attachment=true`, {
        responseType: "blob",
      });
      const blobUrl = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = blobUrl;
      a.setAttribute("download", filename || `document_${docId}.pdf`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch {
      alert("Could not download document. Please try again.");
    }
  };

  const handleRecheckDocuments = async () => {
    if (!workflowId || rechecking) return;
    setRechecking(true);
    setRecheckMessage(null);
    try {
      const response = await recheckWorkflowDocuments(workflowId);
      setRecheckMessage(response.message);
      await loadClaim();
    } catch {
      setRecheckMessage("We could not recheck the documents. Please try again.");
    } finally {
      setRechecking(false);
    }
  };

  useEffect(() => {
    loadClaim();
  }, [loadClaim]);

  if (loading) {
    return (
      <div style={{ maxWidth: "860px", margin: "0 auto", padding: "3rem 1.5rem", textAlign: "center", color: "#788990" }}>
        Loading claim details…
      </div>
    );
  }

  if (error || !claim) {
    return (
      <div style={{ maxWidth: "860px", margin: "0 auto", padding: "3rem 1.5rem" }}>
        <Link to="/dashboard/claims" style={{ color: "#1967a3", textDecoration: "none", fontSize: "14px" }}>
          Back to My Claims
        </Link>
        <div style={{ marginTop: "1.5rem", backgroundColor: "#fff0ed", border: "1px solid #f1d7cd", color: "#bd3e2b", padding: "16px", borderRadius: "8px" }}>
          {error || "Claim not found."}
        </div>
      </div>
    );
  }

  const isApproved = claim.decision === "approve" || claim.claim_status === "approved" || claim.workflow_status === "approved";
  const isRejected = claim.decision === "reject" || claim.claim_status === "rejected" || claim.workflow_status === "rejected";
  const isMoreInfo = claim.decision === "request_more_information" || claim.workflow_status === "more_information_required";
  const isUnderReview = claim.workflow_status === "under_human_review" || claim.workflow_status === "awaiting_assignment" || claim.workflow_status === "awaiting_human_review";
  const workflowId = claim.workflow_id || new URLSearchParams(window.location.search).get("workflowId");

  return (
    <div style={{ maxWidth: "860px", margin: "0 auto", padding: "2rem 1.5rem" }}>
      <div style={{ marginBottom: "1.5rem" }}>
        <Link
          to="/dashboard/claims"
          style={{ color: "#1967a3", textDecoration: "none", fontSize: "14px", fontWeight: "600" }}
        >
          Back to My Claims
        </Link>
      </div>

      <header style={{ marginBottom: "1.5rem" }}>
        <p style={{ fontSize: "11px", fontWeight: "bold", textTransform: "uppercase", color: "#819198", letterSpacing: "0.1em", margin: "0 0 4px 0" }}>
          Claim Reference: {claim.claim_reference || claim.claim_id}
        </p>
        <h1 style={{ fontSize: "28px", fontWeight: "900", color: "#142b3a", margin: "0 0 4px 0" }}>
          {formatIncidentType(claim.incident_type)}
        </h1>
        <p style={{ color: "#526b75", fontSize: "14px", margin: 0 }}>
          Policy #{claim.policy_number || "Pending verification"}
        </p>
      </header>

      {/* Decision / Status Banner */}
      {isApproved && (
        <section
          style={{
            backgroundColor: "#e8f7ee",
            border: "1px solid #c2ebd5",
            borderRadius: "10px",
            padding: "1.25rem",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "24px" }}>✅</span>
            <div>
              <h2 style={{ fontSize: "16px", fontWeight: "bold", color: "#17734c", margin: 0 }}>
                Claim Approved
              </h2>
              <p style={{ color: "#17734c", fontSize: "13px", margin: "4px 0 0 0" }}>
                Your claim has been officially approved by a human claims officer. Settlement processing is underway.
              </p>
            </div>
          </div>
        </section>
      )}

      {isRejected && (
        <section
          style={{
            backgroundColor: "#fff0ed",
            border: "1px solid #f1d7cd",
            borderRadius: "10px",
            padding: "1.25rem",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <span style={{ fontSize: "24px" }}>ℹ️</span>
            <div>
              <h2 style={{ fontSize: "16px", fontWeight: "bold", color: "#bd3e2b", margin: 0 }}>
                Claim Review Completed - Rejected
              </h2>
              <p style={{ color: "#bd3e2b", fontSize: "13px", margin: "4px 0 0 0" }}>
                Following a thorough review by a human claims officer, this claim could not be approved.
              </p>
              {claim.rejection_reason && (
                <div style={{ marginTop: "10px", backgroundColor: "white", padding: "10px 14px", borderRadius: "6px", border: "1px solid #f1d7cd" }}>
                  <strong style={{ fontSize: "12px", color: "#bd3e2b", display: "block" }}>
                    Reason from claims officer:
                  </strong>
                  <span style={{ fontSize: "13px", color: "#142b3a" }}>
                    {claim.rejection_reason}
                  </span>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {isMoreInfo && (
        <section
          style={{
            backgroundColor: "#fff5df",
            border: "1px solid #fae1a0",
            borderRadius: "10px",
            padding: "1.25rem",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <span style={{ fontSize: "24px" }}>⚠️</span>
            <div>
              <h2 style={{ fontSize: "16px", fontWeight: "bold", color: "#a66800", margin: 0 }}>
                Additional Information Requested
              </h2>
              <p style={{ color: "#a66800", fontSize: "13px", margin: "4px 0 0 0" }}>
                The claims officer has requested more information to continue reviewing your claim.
              </p>
              {claim.rejection_reason && (
                <div style={{ marginTop: "10px", backgroundColor: "white", padding: "10px 14px", borderRadius: "6px", border: "1px solid #fae1a0" }}>
                  <strong style={{ fontSize: "12px", color: "#a66800", display: "block" }}>
                    Details requested:
                  </strong>
                  <span style={{ fontSize: "13px", color: "#142b3a" }}>
                    {claim.rejection_reason}
                  </span>
                </div>
              )}
              {workflowId && (
                <div style={{ marginTop: "14px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    onClick={() => setUploadModalOpen(true)}
                    style={{
                      cursor: "pointer",
                      backgroundColor: "#123c42",
                      color: "white",
                      border: "none",
                      padding: "9px 14px",
                      borderRadius: "6px",
                      fontSize: "13px",
                      fontWeight: "700",
                    }}
                  >
                    Provide Missing Documents
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleRecheckDocuments()}
                    disabled={rechecking}
                    style={{
                      cursor: rechecking ? "wait" : "pointer",
                      backgroundColor: "white",
                      color: "#123c42",
                      border: "1px solid #123c42",
                      padding: "9px 14px",
                      borderRadius: "6px",
                      fontSize: "13px",
                      fontWeight: "700",
                    }}
                  >
                    {rechecking ? "Rechecking…" : "Recheck Documents"}
                  </button>
                </div>
              )}
              {recheckMessage && (
                <p style={{ margin: "10px 0 0", color: "#526b75", fontSize: "13px" }} role="status">
                  {recheckMessage}
                </p>
              )}
            </div>
          </div>
        </section>
      )}

      {isUnderReview && (
        <section
          style={{
            backgroundColor: "#e8f4ff",
            border: "1px solid #c7e1fc",
            borderRadius: "10px",
            padding: "1.25rem",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "24px" }}>⏳</span>
            <div>
              <h2 style={{ fontSize: "16px", fontWeight: "bold", color: "#1967a3", margin: 0 }}>
                Under Human Review
              </h2>
              <p style={{ color: "#1967a3", fontSize: "13px", margin: "4px 0 0 0" }}>
                Your claim and supporting documents have been received and are assigned to a claims officer for assessment.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Customer Guidance Card */}
      {claim.customer_explanation && (
        <section
          style={{
            backgroundColor: "white",
            border: "1px solid #dfe7e7",
            borderRadius: "12px",
            padding: "1.5rem",
            marginBottom: "1.5rem",
            boxShadow: "0 4px 16px rgba(20,43,58,0.04)",
          }}
        >
          <h2 style={{ fontSize: "14px", fontWeight: "bold", textTransform: "uppercase", color: "#819198", letterSpacing: "0.08em", margin: "0 0 10px 0" }}>
            Assistant Guidance
          </h2>
          <p style={{ color: "#2b3b44", fontSize: "14px", lineHeight: 1.5, margin: 0, whiteSpace: "pre-line" }}>
            {claim.customer_explanation}
          </p>
        </section>
      )}

      {/* Incident Details Card */}
      <section
        style={{
          backgroundColor: "white",
          border: "1px solid #dfe7e7",
          borderRadius: "12px",
          padding: "1.5rem",
          marginBottom: "1.5rem",
          boxShadow: "0 4px 16px rgba(20,43,58,0.04)",
        }}
      >
        <h2 style={{ fontSize: "14px", fontWeight: "bold", textTransform: "uppercase", color: "#819198", letterSpacing: "0.08em", margin: "0 0 1rem 0" }}>
          Incident Details
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <div>
            <span style={{ fontSize: "12px", color: "#788990", display: "block" }}>Date of incident</span>
            <strong style={{ fontSize: "14px", color: "#142b3a" }}>
              {claim.incident_date ? String(claim.incident_date) : "Not recorded"}
            </strong>
          </div>
          <div>
            <span style={{ fontSize: "12px", color: "#788990", display: "block" }}>Location</span>
            <strong style={{ fontSize: "14px", color: "#142b3a" }}>
              {claim.incident_location || "Not specified"}
            </strong>
          </div>
          <div>
            <span style={{ fontSize: "12px", color: "#788990", display: "block" }}>Claimed Amount</span>
            <strong style={{ fontSize: "14px", color: "#142b3a" }}>
              {claim.claimed_amount != null ? `$${claim.claimed_amount.toFixed(2)}` : "Pending appraisal"}
            </strong>
          </div>
        </div>

        {claim.incident_description && (
          <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid #edf1f1" }}>
            <span style={{ fontSize: "12px", color: "#788990", display: "block", marginBottom: "4px" }}>Description</span>
            <p style={{ fontSize: "13px", color: "#526b75", margin: 0 }}>{claim.incident_description}</p>
          </div>
        )}
      </section>

      {/* Documents Card */}
      <section
        style={{
          backgroundColor: "white",
          border: "1px solid #dfe7e7",
          borderRadius: "12px",
          padding: "1.5rem",
          boxShadow: "0 4px 16px rgba(20,43,58,0.04)",
        }}
      >
        <h2 style={{ fontSize: "14px", fontWeight: "bold", textTransform: "uppercase", color: "#819198", letterSpacing: "0.08em", margin: "0 0 1rem 0" }}>
          Supporting Documents ({claim.documents.length})
        </h2>
        {claim.documents.length === 0 ? (
          <p style={{ color: "#788990", fontSize: "13px", margin: 0 }}>
            No documents uploaded for this claim yet.
          </p>
        ) : (
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {claim.documents.map((doc) => (
              <div
                key={doc.document_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  backgroundColor: "#f9fbfb",
                  borderRadius: "8px",
                  border: "1px solid #edf1f1",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "20px" }}>📄</span>
                  <div>
                    <strong style={{ fontSize: "13px", color: "#142b3a", display: "block" }}>
                      {doc.original_filename}
                    </strong>
                    <span style={{ fontSize: "11px", color: "#788990" }}>
                      {doc.document_type.replace(/_/g, " ")} {doc.file_size_bytes ? `· ${formatFileSize(doc.file_size_bytes)}` : ""}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={() => handleOpenDocument(doc.document_id)}
                    style={{
                      cursor: "pointer",
                      backgroundColor: "#123c42",
                      color: "white",
                      border: "none",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: "bold",
                    }}
                  >
                    View
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadDocument(doc.document_id, doc.original_filename)}
                    style={{
                      cursor: "pointer",
                      backgroundColor: "white",
                      color: "#142b3a",
                      border: "1px solid #ccd8db",
                      padding: "6px 10px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: "600",
                    }}
                    title="Download file"
                  >
                    ⬇
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {uploadModalOpen && workflowId && (
        <DocumentUploadModal
          workflowId={workflowId}
          missingDocuments={[]}
          onClose={() => setUploadModalOpen(false)}
          onUploadComplete={() => loadClaim()}
        />
      )}
    </div>
  );
};
