import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import { fetchMyPolicies } from "../api/policies";
import { useAuth } from "../context/auth-context";
import type { PolicySummary } from "../types/policy";

const modules = [
  {
    name: "Claim Assistant",
    description: "Start and continue guided motor claim conversations.",
    accent: "blue",
    href: "/claim-assistant",
  },
  {
    name: "My Claims",
    description: "Review submitted claims and their current progress.",
    accent: "indigo",
    href: "/dashboard/claims",
  },
  {
    name: "Policy Support",
    description: "Ask questions about motor policy information and coverage.",
    accent: "cyan",
    href: null,
  },
  {
    name: "Profile",
    description: "View and manage your customer account information.",
    accent: "slate",
    href: null,
  },
] as const;

export const DashboardPage = () => {
  const { user } = useAuth();
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(true);
  const [policiesError, setPoliciesError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchMyPolicies()
      .then((response) => {
        if (active) setPolicies(response.policies);
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

  const formatValue = (value: unknown): string => {
    if (typeof value === "boolean") return value ? "Included" : "Not included";
    if (Array.isArray(value)) return value.join(", ");
    return String(value);
  };

  const formatLabel = (value: string): string =>
    value.replace(/[_-]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());

  return (
    <div className="dashboard">
      <section className="dashboard-welcome">
        <div>
          <p className="eyebrow">Customer dashboard</p>
          <h1>Welcome, {user?.email}</h1>
          <p>
            Review your active insurance policies, coverages, and claim tools in one place.
          </p>
        </div>
        <div className="account-summary">
          <span>Account role</span>
          <strong>{user?.role.replace("_", " ")}</strong>
          <span className="account-status"><i aria-hidden="true" /> Authenticated</span>
        </div>
      </section>

      <section aria-labelledby="coverage-heading" style={{ marginTop: "2.5rem" }}>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Your insurance</p>
            <h2 id="coverage-heading">Policies and coverages</h2>
          </div>
          <span className="development-label">Customer records</span>
        </div>

        {policiesError && <div className="alert alert-error" role="alert">{policiesError}</div>}
        {policiesLoading ? (
          <div className="module-card" role="status">Loading your insurance details…</div>
        ) : policies.length === 0 ? (
          <div className="module-card">
            <h3>No insurance policies found</h3>
            <p>Your policies and coverages will appear here once they are linked to your account.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gap: "1rem" }}>
            {policies.map((policy) => (
              <article className="module-card" key={policy.policy_id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
                  <div>
                    <p className="eyebrow" style={{ marginBottom: "0.35rem" }}>{formatLabel(policy.insurance_type)} insurance</p>
                    <h3>{policy.policy_number}</h3>
                  </div>
                  <span className="account-status"><i aria-hidden="true" /> {formatLabel(policy.status)}</span>
                </div>
                <p>
                  {formatLabel(policy.coverage_type)} coverage. Valid from {policy.start_date} to {policy.end_date}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.55rem", marginTop: "1rem" }}>
                  {Object.entries(policy.coverage_details).map(([key, value]) => (
                    <span key={key} style={{ background: "#eef5ff", borderRadius: "999px", color: "#234a79", padding: "0.45rem 0.7rem", fontSize: "0.82rem", fontWeight: 700 }}>
                      {formatLabel(key)}: {formatValue(value)}
                    </span>
                  ))}
                </div>
                {policy.exclusions.length > 0 && (
                  <p style={{ color: "#6c7890", fontSize: "0.88rem", margin: "1rem 0 0" }}>
                    Exclusions: {policy.exclusions.map(formatValue).join(", ")}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="services-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Portal services</p>
            <h2 id="services-heading">What you’ll be able to do</h2>
          </div>
          <span className="development-label">Foundation preview</span>
        </div>

        <div className="module-grid">
          {modules.map((module, index) => {
            const content = (
              <>
              <span className={`module-number module-number-${module.accent}`}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3>{module.name}</h3>
              <p>{module.description}</p>
              <span className={module.href ? "module-action" : "coming-soon"}>
                {module.href ? "Open assistant" : "Coming soon"}
              </span>
              </>
            );

            return module.href ? (
              <Link className="module-card module-card-link" to={module.href} key={module.name}>
                {content}
              </Link>
            ) : (
              <article className="module-card" key={module.name}>{content}</article>
            );
          })}
        </div>
      </section>
    </div>
  );
};
