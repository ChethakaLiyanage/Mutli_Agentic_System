import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import { fetchMyClaims } from "../api/claims";
import type { ClaimSummary } from "../types/claim";

const statusBadges: Record<string, { label: string; bg: string; text: string }> = {
  awaiting_documents: { label: "Documents Required", bg: "#fff5df", text: "#a66800" },
  documents_submitted: { label: "Documents Submitted", bg: "#e8f4ff", text: "#1967a3" },
  awaiting_assignment: { label: "Queued for Review", bg: "#f3e8ff", text: "#6b21a8" },
  under_human_review: { label: "Under Review", bg: "#e8f4ff", text: "#1967a3" },
  awaiting_human_review: { label: "Under Review", bg: "#e8f4ff", text: "#1967a3" },
  approved: { label: "Approved", bg: "#e8f7ee", text: "#17734c" },
  rejected: { label: "Rejected", bg: "#fff0ed", text: "#bd3e2b" },
  more_information_required: { label: "Info Required", bg: "#fff5df", text: "#a66800" },
  escalated: { label: "Escalated", bg: "#fff0ed", text: "#bd3e2b" },
  policy_link_required: { label: "Policy Linking", bg: "#f0f4f5", text: "#526b75" },
  draft: { label: "Draft", bg: "#f0f4f5", text: "#526b75" },
  failed: { label: "Incomplete", bg: "#fff0ed", text: "#bd3e2b" },
};

const formatIncidentType = (type: string | null | undefined): string => {
  if (!type) return "Motor Claim";
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

export const MyClaimsPage = () => {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchMyClaims()
      .then((res) => {
        if (active) setClaims(res.claims);
      })
      .catch((err) => {
        if (active) setError(getApiErrorMessage(err, "Could not load your claims. Please try again."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2rem 1.5rem" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "2rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <p style={{ fontSize: "11px", fontWeight: "bold", textTransform: "uppercase", color: "#819198", letterSpacing: "0.1em", margin: "0 0 4px 0" }}>
            Customer portal
          </p>
          <h1 style={{ fontSize: "28px", fontWeight: "900", color: "#142b3a", margin: 0 }}>
            My Claims
          </h1>
          <p style={{ color: "#526b75", fontSize: "14px", marginTop: "4px" }}>
            Track the status and details of your motor insurance claims.
          </p>
        </div>
        <Link
          to="/claim-assistant"
          style={{
            backgroundColor: "#e86d45",
            color: "white",
            padding: "10px 18px",
            borderRadius: "8px",
            textDecoration: "none",
            fontWeight: "bold",
            fontSize: "13px",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>+</span> Start New Claim
        </Link>
      </header>

      {error && (
        <div style={{ backgroundColor: "#fff0ed", border: "1px solid #f1d7cd", color: "#bd3e2b", padding: "12px 16px", borderRadius: "8px", marginBottom: "1.5rem", fontSize: "14px" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: "3rem", color: "#788990" }}>
          Loading your claims…
        </div>
      ) : claims.length === 0 ? (
        <div
          style={{
            backgroundColor: "white",
            border: "1px solid #dfe7e7",
            borderRadius: "12px",
            padding: "3rem 2rem",
            textAlign: "center",
          }}
        >
          <p style={{ fontSize: "40px", margin: "0 0 10px 0" }}>📋</p>
          <h2 style={{ fontSize: "18px", fontWeight: "bold", color: "#142b3a", margin: "0 0 6px 0" }}>
            No claims filed yet
          </h2>
          <p style={{ color: "#788990", fontSize: "14px", margin: "0 0 1.5rem 0" }}>
            When you file a motor claim with the Claim Assistant, it will appear here.
          </p>
          <Link
            to="/claim-assistant"
            style={{
              backgroundColor: "#123c42",
              color: "white",
              padding: "10px 20px",
              borderRadius: "8px",
              textDecoration: "none",
              fontWeight: "600",
              fontSize: "14px",
            }}
          >
            File a Claim
          </Link>
        </div>
      ) : (
        <div
          style={{
            backgroundColor: "white",
            border: "1px solid #dfe7e7",
            borderRadius: "12px",
            overflow: "hidden",
            boxShadow: "0 4px 16px rgba(20,43,58,0.04)",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #edf1f1", backgroundColor: "#f9fbfb", fontSize: "11px", textTransform: "uppercase", color: "#819198", letterSpacing: "0.08em" }}>
                <th style={{ padding: "12px 16px" }}>Claim Ref</th>
                <th style={{ padding: "12px 16px" }}>Incident Type</th>
                <th style={{ padding: "12px 16px" }}>Date Filed</th>
                <th style={{ padding: "12px 16px" }}>Incident Date</th>
                <th style={{ padding: "12px 16px" }}>Policy</th>
                <th style={{ padding: "12px 16px" }}>Status</th>
                <th style={{ padding: "12px 16px", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim) => {
                const badge = statusBadges[claim.workflow_status || claim.claim_status || ""] ?? {
                  label: (claim.workflow_status || claim.claim_status || "Processing").replace(/_/g, " "),
                  bg: "#edf1f1",
                  text: "#526b75",
                };
                return (
                  <tr
                    key={claim.claim_id}
                    style={{ borderBottom: "1px solid #edf1f1", fontSize: "13px" }}
                  >
                    <td style={{ padding: "14px 16px", fontWeight: "bold", color: "#d75b36" }}>
                      {claim.claim_reference || claim.claim_id}
                    </td>
                    <td style={{ padding: "14px 16px", color: "#142b3a" }}>
                      {formatIncidentType(claim.incident_type)}
                    </td>
                    <td style={{ padding: "14px 16px", color: "#526b75", whiteSpace: "nowrap" }}>
                      {claim.created_at
                        ? new Date(claim.created_at).toLocaleDateString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })
                        : "—"}
                    </td>
                    <td style={{ padding: "14px 16px", color: "#526b75" }}>
                      {claim.incident_date ? String(claim.incident_date) : "—"}
                    </td>
                    <td style={{ padding: "14px 16px", color: "#526b75" }}>
                      {claim.policy_number || "—"}
                    </td>
                    <td style={{ padding: "14px 16px" }}>
                      <span
                        style={{
                          backgroundColor: badge.bg,
                          color: badge.text,
                          padding: "4px 10px",
                          borderRadius: "20px",
                          fontSize: "11px",
                          fontWeight: "bold",
                          display: "inline-block",
                        }}
                      >
                        {badge.label}
                      </span>
                    </td>
                    <td style={{ padding: "14px 16px", textAlign: "right" }}>
                      <Link
                        to={`/dashboard/claims/${encodeURIComponent(claim.claim_id)}`}
                        style={{
                          color: "#1967a3",
                          fontWeight: "600",
                          textDecoration: "none",
                          fontSize: "13px",
                        }}
                      >
                        View details 
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
