import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import { fetchMyClaims } from "../api/claims";
import { fetchMyPolicies } from "../api/policies";
import { useAuth } from "../context/auth-context";
import type { ClaimSummary } from "../types/claim";
import type { PolicySummary } from "../types/policy";
import "../profile.css";

/* ── Helpers (reused from DashboardPage / MyClaimsPage) ── */

const formatValue = (value: unknown): string => {
  if (typeof value === "boolean") return value ? "Included" : "Not included";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
};

const formatLabel = (value: string): string =>
  value.replace(/[_-]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());

const formatIncidentType = (type: string | null | undefined): string => {
  if (!type) return "Motor Claim";
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

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

/* ── ProfilePage ── */

export const ProfilePage = () => {
  const { user } = useAuth();

  /* Policies state */
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(true);
  const [policiesError, setPoliciesError] = useState<string | null>(null);

  /* Claims state */
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [claimsLoading, setClaimsLoading] = useState(true);
  const [claimsError, setClaimsError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchMyPolicies()
      .then((response) => {
        if (active) {
          const list = Array.isArray(response)
            ? response
            : Array.isArray(response?.policies)
            ? response.policies
            : [];
          setPolicies(list);
        }
      })
      .catch((error) => {
        if (active) {
          setPoliciesError(getApiErrorMessage(error, "Could not load your coverages."));
        }
      })
      .finally(() => {
        if (active) setPoliciesLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    fetchMyClaims()
      .then((res) => {
        if (active) {
          const list = Array.isArray(res)
            ? res
            : Array.isArray(res?.claims)
            ? res.claims
            : [];
          setClaims(list);
        }
      })
      .catch((err) => {
        if (active) setClaimsError(getApiErrorMessage(err, "Could not load your claims."));
      })
      .finally(() => {
        if (active) setClaimsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="profile-page">
      <header className="profile-header">
        <h1>Profile</h1>
        <Link to="/claim-assistant" className="button button-primary button-small">
           Back to Assistant
        </Link>
      </header>

      {/* ── Personal Details ── */}
      <section className="profile-section" aria-labelledby="personal-heading">
        <h2 id="personal-heading">Personal Details</h2>
        <div className="profile-details-grid">
          <div className="profile-detail">
            <span className="profile-detail-label">Email</span>
            <span className="profile-detail-value">{user?.email}</span>
          </div>
          <div className="profile-detail">
            <span className="profile-detail-label">Account Role</span>
            <span className="profile-detail-value" style={{ textTransform: "capitalize" }}>
              {user?.role.replace("_", " ")}
            </span>
          </div>
          <div className="profile-detail">
            <span className="profile-detail-label">Account Created</span>
            <span className="profile-detail-value">
              {user?.created_at
                ? new Date(user.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })
                : "—"}
            </span>
          </div>
        </div>
      </section>

      {/* ── Coverage Type / Policies ── */}
      <section className="profile-section" aria-labelledby="coverage-heading">
        <h2 id="coverage-heading">Coverage Type</h2>

        {policiesError && (
          <div className="alert alert-error" role="alert">{policiesError}</div>
        )}
        {policiesLoading ? (
          <div className="profile-loading" role="status">Loading your insurance details…</div>
        ) : policies.length === 0 ? (
          <div className="profile-empty">
            <p>No insurance policies found.</p>
            <p className="profile-empty-sub">
              Your policies and coverages will appear here once they are linked to your account.
            </p>
          </div>
        ) : (
          <div className="profile-cards-grid">
            {policies.map((policy) => (
              <article className="profile-policy-card" key={policy.policy_id}>
                <div className="profile-policy-header">
                  <div>
                    <p className="eyebrow" style={{ marginBottom: "0.35rem" }}>
                      {formatLabel(policy.insurance_type)} insurance
                    </p>
                    <h3>{policy.policy_number}</h3>
                  </div>
                  <span className="profile-policy-status">
                    <i aria-hidden="true" /> {formatLabel(policy.status)}
                  </span>
                </div>
                <p>
                  {formatLabel(policy.coverage_type)} coverage. Valid from{" "}
                  {policy.start_date} to {policy.end_date}
                </p>
                <div className="profile-policy-tags">
                  {policy.coverage_details &&
                    Object.entries(policy.coverage_details).map(([key, value]) => (
                      <span key={key} className="profile-coverage-tag">
                        {formatLabel(key)}: {formatValue(value)}
                      </span>
                    ))}
                </div>
                {Array.isArray(policy.exclusions) && policy.exclusions.length > 0 && (
                  <p className="profile-policy-exclusions">
                    Exclusions: {policy.exclusions.map(formatValue).join(", ")}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {/* ── My Claims ── */}
      <section className="profile-section" aria-labelledby="claims-heading">
        <div className="profile-section-header">
          <h2 id="claims-heading">My Claims</h2>
          <Link
            to="/claim-assistant"
            className="button button-primary button-small"
          >
            <span>+</span> Start New Claim
          </Link>
        </div>

        {claimsError && (
          <div className="alert alert-error" role="alert">{claimsError}</div>
        )}
        {claimsLoading ? (
          <div className="profile-loading" role="status">Loading your claims…</div>
        ) : claims.length === 0 ? (
          <div className="profile-empty">
            <p className="profile-empty-icon">📋</p>
            <p><strong>No claims filed yet</strong></p>
            <p className="profile-empty-sub">
              When you file a motor claim with the Claim Assistant, it will appear here.
            </p>
          </div>
        ) : (
          <div className="profile-claims-table-wrapper">
            <table className="profile-claims-table">
              <thead>
                <tr>
                  <th>Claim Ref</th>
                  <th>Incident Type</th>
                  <th>Date Filed</th>
                  <th>Incident Date</th>
                  <th>Policy</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {claims.map((claim, index) => {
                  const badge = statusBadges[claim.workflow_status || claim.claim_status || ""] ?? {
                    label: (claim.workflow_status || claim.claim_status || "Processing").replace(/_/g, " "),
                    bg: "#edf1f1",
                    text: "#526b75",
                  };
                  return (
                    <tr key={claim.claim_id || claim.claim_reference || index}>
                      <td className="profile-claim-ref">
                        {claim.claim_reference || claim.claim_id}
                      </td>
                      <td>{formatIncidentType(claim.incident_type)}</td>
                      <td className="profile-claim-date">
                        {claim.created_at
                          ? new Date(claim.created_at).toLocaleDateString(undefined, {
                              year: "numeric",
                              month: "short",
                              day: "numeric",
                            })
                          : "—"}
                      </td>
                      <td>{claim.incident_date ? String(claim.incident_date) : "—"}</td>
                      <td>{claim.policy_number || "—"}</td>
                      <td>
                        <span
                          className="profile-status-badge"
                          style={{ backgroundColor: badge.bg, color: badge.text }}
                        >
                          {badge.label}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <Link
                          to={`/dashboard/claims/${encodeURIComponent(claim.claim_id)}`}
                          className="profile-claim-link"
                        >
                          View details →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
