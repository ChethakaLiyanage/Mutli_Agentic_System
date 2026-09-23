import { useEffect, useState } from "react";
import { apiClient, getApiErrorMessage } from "../api/client";
import {
  assignClaim,
  fetchReviewDetail,
  fetchReviewQueue,
  submitHumanDecision,
} from "../api/review";
import {
  createCustomerAccount,
  fetchCustomersList,
  type AdminCustomer,
  type PolicyCategory,
} from "../api/admin";
import type {
  HumanDecisionRequest,
  ReviewDetailResponse,
  ReviewQueueItem,
} from "../types/review";

type Section =
  | "overview"
  | "analytics"
  | "claims"
  | "rules"
  | "users"
  | "documents"
  | "settings";

const sections: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "analytics", label: "Risk analytics" },
  { id: "claims", label: "Claims management" },
  { id: "rules", label: "Rules & models" },
  { id: "users", label: "Users & access" },
  { id: "documents", label: "Policy documents" },
  { id: "settings", label: "Settings" },
];

const colors: Record<string, string> = {
  High: "bg-[#fff0ed] text-[#bd3e2b]",
  Medium: "bg-[#fff5df] text-[#a66800]",
  Low: "bg-[#e8f7ee] text-[#17734c]",
  "Under review": "bg-[#e8f4ff] text-[#1967a3]",
  "Awaiting assignment": "bg-[#f3e8ff] text-[#6b21a8]",
};

const Badge = ({ value }: { value: string }) => (
  <span
    className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${
      colors[value] ?? "bg-slate-100 text-slate-600"
    }`}
  >
    {value}
  </span>
);

const Card = ({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <article
    className={`rounded-xl border border-[#dfe7e7] bg-white p-5 shadow-[0_5px_18px_rgba(20,43,58,0.04)] ${className}`}
  >
    {children}
  </article>
);

const riskLabel = (level: string | null) =>
  level ? `${level[0].toUpperCase()}${level.slice(1)}` : "Unknown";

const averageRisk = (items: ReviewQueueItem[]) =>
  items.length
    ? items.reduce((sum, item) => sum + (item.risk_score ?? 0), 0) / items.length
    : 0;

export const AdminDashboard = () => {
  const [section, setSection] = useState<Section>("overview");
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadQueue = () => {
    setLoading(true);
    fetchReviewQueue()
      .then((response) => {
        setItems(response.items);
      })
      .catch(() => {
        setError("Risk data is unavailable. Check the reviewer service and try again.");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadQueue();
  }, []);

  return (
    <div className="min-h-screen bg-[#f5f7f7] font-[Inter,ui-sans-serif,system-ui,sans-serif] text-[#142b3a]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[244px] border-r border-[#dbe5e5] bg-[#123c42] px-4 py-5 text-[#d7e8e5] lg:block">
        <div className="mb-10 px-2">
          <p className="text-sm font-black tracking-wide text-white">
            claim<span className="text-[#f18a62]">flow</span>
          </p>
          <p className="text-[10px] uppercase tracking-[0.18em] text-[#91b5b0]">
            operations
          </p>
        </div>
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-[#729a96]">
          Workspace
        </p>
        <nav className="space-y-1" aria-label="Admin workspace">
          {sections.map((item) => (
            <button
              key={item.id}
              onClick={() => setSection(item.id)}
              className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition ${
                section === item.id
                  ? "bg-[#e86d45] text-white"
                  : "text-[#b7d0cc] hover:bg-[#1d4d52] hover:text-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="lg:ml-[244px]">
        <header className="sticky top-0 z-10 flex min-h-[72px] items-center justify-between border-b border-[#dbe5e5] bg-[#f5f7f7]/95 px-5 backdrop-blur md:px-9">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#819198]">
              Admin workspace
            </p>
            <p className="text-sm font-bold text-[#365363]">
              Production risk operations
            </p>
          </div>
          <span className="rounded-full bg-[#e8f7ee] px-3 py-1 text-[11px] font-bold text-[#17734c]">
            Live operational queue
          </span>
        </header>
        <div className="mx-auto max-w-[1450px] p-5 md:p-9">
          {error && (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-[#f1d7cd] bg-[#fffaf7] px-4 py-3 text-sm font-bold text-[#bd3e2b]"
            >
              {error}
            </div>
          )}
          {section === "overview" && (
            <Overview
              items={items}
              loading={loading}
              onAnalytics={() => setSection("analytics")}
            />
          )}
          {section === "analytics" && (
            <Analytics items={items} loading={loading} />
          )}
          {section === "claims" && (
            <Claims items={items} loading={loading} onRefresh={loadQueue} />
          )}
          {section === "users" && <CustomerManagement />}
          {!(["overview", "analytics", "claims", "users"] as Section[]).includes(
            section,
          ) && (
            <Card>
              <h2 className="text-2xl font-black">
                {sections.find((item) => item.id === section)?.label}
              </h2>
              <p className="mt-2 text-sm text-[#778590]">
                This workspace section is not connected to production data yet.
              </p>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
};

function Overview({
  items,
  loading,
  onAnalytics,
}: {
  items: ReviewQueueItem[];
  loading: boolean;
  onAnalytics: () => void;
}) {
  const high = items.filter((item) => item.risk_level === "high").length;
  const medium = items.filter((item) => item.risk_level === "medium").length;
  const low = items.filter((item) => item.risk_level === "low").length;
  const average = averageRisk(items);
  const observations = items
    .flatMap((item) => item.reviewer_summary?.risk_observations ?? [])
    .slice(0, 3);
  const total = items.length;
  const highEnd = total ? (high / total) * 100 : 0;
  const mediumEnd = total ? ((high + medium) / total) * 100 : 0;

  return (
    <>
      <Header
        title="Claims command center"
        detail="Live fraud assessments with reviewer guidance context."
      />
      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Assessed claims", total],
          ["High risk", high],
          ["Average risk score", `${Math.round(average * 100)}%`],
          [
            "Missing documents",
            items.reduce(
              (sum, item) => sum + (item.missing_documents?.length ?? 0),
              0,
            ),
          ],
        ].map(([label, value]) => (
          <Card key={label}>
            <p className="text-xs font-bold text-[#788990]">{label}</p>
            <p className="mt-3 text-3xl font-black">{loading ? "..." : value}</p>
            <p className="mt-1 text-[11px] text-[#9aa8ac]">
              Persisted production values
            </p>
          </Card>
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-black">Risk distribution</h3>
          <p className="mt-1 text-xs text-[#8b9a9f]">
            Fraud assessment levels in the current reviewer queue
          </p>
          <div className="mt-6 flex items-center gap-6">
            <div
              className="grid h-32 w-32 place-items-center rounded-full"
              style={{
                background: `conic-gradient(#e86d45 0 ${highEnd}%, #f1c66a ${highEnd}% ${mediumEnd}%, #82cbb5 ${mediumEnd}% 100%)`,
              }}
            >
              <div className="grid h-20 w-20 place-items-center rounded-full bg-white">
                <span className="text-xl font-black">
                  {Math.round(average * 100)}
                </span>
              </div>
            </div>
            <div className="space-y-3 text-xs">
              {[
                ["Low risk", low],
                ["Medium risk", medium],
                ["High risk", high],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center gap-2">
                  <span className="w-24 text-[#788990]">{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-black">Reviewer guidance</h3>
              <p className="mt-1 text-xs text-[#8b9a9f]">
                Risk observations from Agent 4
              </p>
            </div>
            <button
              onClick={onAnalytics}
              className="text-xs font-bold text-[#d75b36]"
            >
              View analytics
            </button>
          </div>
          <div className="mt-5 space-y-3">
            {observations.length ? (
              observations.map((item) => (
                <p
                  key={item}
                  className="rounded-lg bg-[#f5f8f8] p-3 text-xs font-semibold text-[#526b75]"
                >
                  {item}
                </p>
              ))
            ) : (
              <p className="text-xs text-[#8b9a9f]">
                No reviewer summary is available yet.
              </p>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

function Analytics({
  items,
  loading,
}: {
  items: ReviewQueueItem[];
  loading: boolean;
}) {
  const buckets = Array.from(
    { length: 10 },
    (_, index) =>
      items.filter(
        (item) =>
          Math.min(9, Math.floor((item.risk_score ?? 0) * 10)) === index,
      ).length,
  );
  const rules = items.flatMap(
    (item) => item.reviewer_summary?.risk_observations ?? [],
  );
  const ruleCounts = rules.reduce<Record<string, number>>(
    (counts, rule) => ({ ...counts, [rule]: (counts[rule] ?? 0) + 1 }),
    {},
  );
  const average = averageRisk(items);
  return (
    <>
      <Header
        title="Risk analytics"
        detail="Metrics are calculated from persisted production fraud assessments."
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-black">Risk score distribution</h3>
          <div className="mt-6 flex h-52 items-end gap-1 border-b border-l border-[#e6eded] px-2">
            {buckets.map((count, index) => (
              <div
                key={index}
                className="flex-1 rounded-t bg-[#e86d45]"
                style={{
                  height: `${
                    loading
                      ? 0
                      : Math.max(
                          4,
                          (count / Math.max(1, ...buckets)) * 100,
                        )
                  }%`,
                }}
              />
            ))}
          </div>
          <div className="mt-2 flex justify-between text-[10px] text-[#9aa8ac]">
            <span>0</span>
            <span>25</span>
            <span>50</span>
            <span>75</span>
            <span>100</span>
          </div>
        </Card>
        <Card>
          <h3 className="font-black">Model and hybrid score</h3>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <Metric
              label="Average hybrid risk"
              value={`${Math.round(average * 100)}%`}
            />
            <Metric label="Assessed claims" value={String(items.length)} />
            <Metric
              label="High risk claims"
              value={String(
                items.filter((item) => item.risk_level === "high").length,
              )}
            />
            <Metric
              label="ML scores available"
              value={"Stored with assessment"}
            />
          </div>
        </Card>
        <Card>
          <h3 className="mb-4 font-black">Reviewer risk observations</h3>
          {Object.entries(ruleCounts).length ? (
            Object.entries(ruleCounts).map(([label, count]) => (
              <div
                key={label}
                className="mb-4 flex items-center justify-between rounded-lg bg-[#f5f8f8] p-3 text-xs"
              >
                <span className="font-bold text-[#526b75]">{label}</span>
                <strong>{count}</strong>
              </div>
            ))
          ) : (
            <p className="text-xs text-[#8b9a9f]">
              No reviewer observations are available yet.
            </p>
          )}
        </Card>
      </div>
    </>
  );
}

function Claims({
  items,
  loading,
  onRefresh,
}: {
  items: ReviewQueueItem[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [reviewDetail, setReviewDetail] = useState<ReviewDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Assignment state
  const [assigningWf, setAssigningWf] = useState<string | null>(null);
  const [assigneeId, setAssigneeId] = useState("claims_officer_1");
  const [assignmentSubmitting, setAssignmentSubmitting] = useState(false);

  // Decision state
  const [decisionType, setDecisionType] = useState<
    "approve" | "reject" | "request_more_information" | "escalate"
  >("approve");
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const handleOpenDocument = async (docId: string, filename?: string) => {
    try {
      const res = await apiClient.get(`/documents/${encodeURIComponent(docId)}/download`, {
        responseType: "blob",
      });
      const blobType = String(res.headers["content-type"] || "application/pdf");
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: blobType }));
      window.open(blobUrl, "_blank");
    } catch {
      alert("Could not open document. Please verify your connection.");
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
      alert("Could not download document. Please verify your connection.");
    }
  };

  const openReviewModal = async (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setLoadingDetail(true);
    setActionError(null);
    setActionSuccess(null);
    setDecisionReason("");
    setDecisionNotes("");
    try {
      const detail = await fetchReviewDetail(workflowId);
      setReviewDetail(detail);
    } catch {
      setActionError("Failed to fetch review details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  const closeReviewModal = () => {
    setSelectedWorkflowId(null);
    setReviewDetail(null);
    setActionError(null);
    setActionSuccess(null);
  };

  const handleAssign = async (workflowId: string) => {
    if (!assigneeId.trim()) return;
    setAssignmentSubmitting(true);
    setActionError(null);
    try {
      await assignClaim(workflowId, { assigned_to: assigneeId.trim() });
      setAssigningWf(null);
      onRefresh();
      if (selectedWorkflowId === workflowId) {
        await openReviewModal(workflowId);
      }
    } catch (err: unknown) {
      setActionError(getApiErrorMessage(err, "Failed to assign claim."));
    } finally {
      setAssignmentSubmitting(false);
    }
  };

  const handleSubmitDecision = async () => {
    if (!selectedWorkflowId) return;

    // Strict validation: Reject strictly requires a non-empty reason
    if (decisionType === "reject" && !decisionReason.trim()) {
      setActionError("A non-empty reason is strictly required to reject a claim.");
      return;
    }
    if (decisionType === "request_more_information" && !decisionReason.trim()) {
      setActionError("Please specify what additional information is required.");
      return;
    }

    setDecisionSubmitting(true);
    setActionError(null);
    try {
      const payload: HumanDecisionRequest = {
        decision: decisionType,
        reason: decisionReason.trim() || (decisionType === "approve" ? "Claim meets policy criteria" : "Escalated for specialist review"),
        notes: decisionNotes.trim() || undefined,
      };
      await submitHumanDecision(selectedWorkflowId, payload);
      setActionSuccess(`Authoritative decision submitted: ${decisionType.toUpperCase()}`);
      onRefresh();
      // Re-fetch detail to show decision
      const updated = await fetchReviewDetail(selectedWorkflowId);
      setReviewDetail(updated);
    } catch (err: unknown) {
      setActionError(getApiErrorMessage(err, "Failed to submit decision."));
    } finally {
      setDecisionSubmitting(false);
    }
  };

  return (
    <>
      <Header
        title="Claims management & review"
        detail="Common queue of claims awaiting assignment or review. AI triage is advisory only; claims officers make authoritative decisions."
      />

      {actionSuccess && (
        <div className="mb-4 rounded-lg border border-[#c2ebd5] bg-[#e8f7ee] p-3 text-sm font-semibold text-[#17734c]">
          {actionSuccess}
        </div>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left">
            <thead className="border-b border-[#edf1f1] text-[10px] uppercase tracking-wider text-[#8b9a9f]">
              <tr>
                {[
                  "Claim ID",
                  "Incident Type",
                  "Risk Level",
                  "Risk Score",
                  "Status",
                  "Assigned To",
                  "Actions",
                ].map((heading) => (
                  <th key={heading} className="px-3 py-3">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf1f1]">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-sm text-[#8b9a9f]">
                    Loading claims queue...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-sm text-[#8b9a9f]">
                    No claims currently in the review queue.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.workflow_id} className="hover:bg-[#fbfdfd]">
                    <td className="px-3 py-4 text-xs font-black text-[#d75b36]">
                      {item.claim_id}
                    </td>
                    <td className="px-3 py-4 text-xs font-semibold text-[#526b75]">
                      {item.incident_type ? item.incident_type.replace(/_/g, " ") : "Claim"}
                    </td>
                    <td className="px-3 py-4">
                      <Badge value={riskLabel(item.risk_level)} />
                    </td>
                    <td className="px-3 py-4 text-xs font-semibold">
                      {item.risk_score == null
                        ? "—"
                        : `${Math.round(item.risk_score * 100)}%`}
                    </td>
                    <td className="px-3 py-4 text-xs">
                      <span className="rounded bg-[#f0f4f4] px-2 py-0.5 text-[11px] font-bold text-[#526b75]">
                        {(item.status || "awaiting_assignment").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-3 py-4 text-xs text-[#526b75]">
                      {item.assigned_to ? (
                        <span className="font-semibold text-[#142b3a]">
                          👤 {item.assigned_to}
                        </span>
                      ) : (
                        <span className="italic text-[#9aa8ac]">Unassigned</span>
                      )}
                    </td>
                    <td className="px-3 py-4 text-xs">
                      <div className="flex items-center gap-2">
                        {item.assigned_to ? (
                          <button
                            onClick={() => setAssigningWf(item.workflow_id)}
                            className="rounded bg-slate-100 px-2 py-1 text-[11px] font-semibold text-[#526b75] hover:bg-slate-200"
                          >
                            Reassign
                          </button>
                        ) : (
                          <button
                            onClick={() => setAssigningWf(item.workflow_id)}
                            className="rounded bg-[#e86d45] px-2.5 py-1 text-[11px] font-bold text-white hover:bg-[#d75b36]"
                          >
                            Assign
                          </button>
                        )}
                        <button
                          onClick={() => void openReviewModal(item.workflow_id)}
                          className="rounded bg-[#123c42] px-2.5 py-1 text-[11px] font-bold text-white hover:bg-[#1d4d52]"
                        >
                          Review →
                        </button>
                      </div>

                      {/* Quick assignment inline dialog */}
                      {assigningWf === item.workflow_id && (
                        <div className="mt-2 flex items-center gap-1 rounded bg-[#f5f8f8] p-2">
                          <input
                            type="text"
                            value={assigneeId}
                            onChange={(e) => setAssigneeId(e.target.value)}
                            placeholder="Officer user ID"
                            className="w-32 rounded border border-[#dbe5e5] px-2 py-1 text-[11px]"
                          />
                          <button
                            onClick={() => void handleAssign(item.workflow_id)}
                            disabled={assignmentSubmitting}
                            className="rounded bg-[#17734c] px-2 py-1 text-[10px] font-bold text-white"
                          >
                            {assignmentSubmitting ? "…" : "Save"}
                          </button>
                          <button
                            onClick={() => setAssigningWf(null)}
                            className="px-1 text-[11px] text-[#788990]"
                          >
                            ✕
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Full Review & Decision Modal */}
      {selectedWorkflowId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#edf1f1] pb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#8b9a9f]">
                  Human claims review
                </span>
                <h3 className="text-xl font-black text-[#142b3a]">
                  Workflow: {selectedWorkflowId}
                </h3>
              </div>
              <button
                onClick={closeReviewModal}
                className="rounded-full p-2 text-lg text-[#788990] hover:bg-[#f5f8f8]"
              >
                ✕
              </button>
            </div>

            {loadingDetail ? (
              <div className="py-12 text-center text-sm text-[#788990]">
                Loading claim details, retrieval facts, and fraud assessment...
              </div>
            ) : reviewDetail ? (
              <div className="mt-6 space-y-6">
                {actionError && (
                  <div className="rounded-lg border border-[#f1d7cd] bg-[#fffaf7] p-3 text-sm font-bold text-[#bd3e2b]">
                    {actionError}
                  </div>
                )}

                {/* Claim Context & Assignment */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-[#dfe7e7] bg-[#fafcfc] p-4 text-xs">
                    <p className="font-bold text-[#142b3a]">Claim Context</p>
                    <div className="mt-2 space-y-1 text-[#526b75]">
                      <p><strong>Claim ID:</strong> {reviewDetail.claim?.claim_id}</p>
                      <p><strong>Incident Type:</strong> {reviewDetail.claim?.incident_type?.replace(/_/g, " ") ?? "—"}</p>
                      <p><strong>Incident Date:</strong> {reviewDetail.claim?.incident_date ?? "—"}</p>
                      <p><strong>Location:</strong> {reviewDetail.claim?.incident_location ?? "—"}</p>
                      <p><strong>Claimed Amount:</strong> {reviewDetail.claim?.claimed_amount != null ? `$${reviewDetail.claim?.claimed_amount}` : "—"}</p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-[#dfe7e7] bg-[#fafcfc] p-4 text-xs">
                    <p className="font-bold text-[#142b3a]">Review Status & Assignment</p>
                    <div className="mt-2 space-y-1 text-[#526b75]">
                      <p><strong>Workflow Status:</strong> <span className="font-semibold text-[#123c42]">{reviewDetail.status}</span></p>
                      <p><strong>Assigned To:</strong> {reviewDetail.assigned_to ? <span className="font-bold text-[#17734c]">👤 {reviewDetail.assigned_to}</span> : <span className="text-[#e86d45]">Unassigned</span>}</p>
                      {reviewDetail.assigned_at && <p><strong>Assigned At:</strong> {new Date(reviewDetail.assigned_at).toLocaleString()}</p>}
                      <div className="mt-2 flex items-center gap-2 pt-2">
                        <input
                          type="text"
                          value={assigneeId}
                          onChange={(e) => setAssigneeId(e.target.value)}
                          className="rounded border border-[#dbe5e5] px-2 py-1 text-xs"
                          placeholder="Assignee User ID"
                        />
                        <button
                          onClick={() => void handleAssign(reviewDetail.workflow_id)}
                          disabled={assignmentSubmitting}
                          className="rounded bg-[#123c42] px-3 py-1 text-xs font-bold text-white"
                        >
                          {assignmentSubmitting ? "Assigning…" : "Update Assignment"}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Customer Supporting Documents */}
                <div className="rounded-xl border border-[#dfe7e7] p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-[#8b9a9f]">
                    Uploaded Documents ({reviewDetail.documents?.length ?? 0})
                  </p>
                  {!reviewDetail.documents || reviewDetail.documents.length === 0 ? (
                    <p className="mt-2 text-xs text-[#788990]">No documents uploaded for this claim yet.</p>
                  ) : (
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {reviewDetail.documents.map((doc) => {
                        const displayName = doc.original_filename || (doc as any).file_name || "Document";
                        return (
                          <div key={doc.document_id} className="flex flex-col justify-between rounded-lg bg-[#f5f8f8] p-3 text-xs gap-2 border border-[#e5eeef]">
                            <div className="min-w-0">
                              <p className="font-bold text-[#142b3a] truncate" title={displayName}>📄 {displayName}</p>
                              <span className="text-[11px] text-[#788990]">
                                {doc.document_type.replace(/_/g, " ")} {doc.file_size_bytes ? `· ${(doc.file_size_bytes / 1024).toFixed(0)} KB` : ""}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 pt-1 border-t border-[#edf1f1]">
                              <button
                                type="button"
                                onClick={() => handleOpenDocument(doc.document_id, displayName)}
                                className="cursor-pointer rounded bg-[#123c42] hover:bg-[#1b525a] px-2.5 py-1 text-[11px] font-bold text-white transition-colors"
                                title="Open document in new tab"
                              >
                                View ↗
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownloadDocument(doc.document_id, displayName)}
                                className="cursor-pointer rounded border border-[#ccd8db] bg-white hover:bg-[#f0f4f5] px-2 py-1 text-[11px] font-semibold text-[#142b3a] transition-colors"
                                title="Download document"
                              >
                                Download ⬇
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Advisory Fraud Triage (Agent 3) */}
                <div className="rounded-xl border border-[#ffe0d6] bg-[#fffaf8] p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-black uppercase tracking-wider text-[#bd3e2b]">
                        Agent 3 · Advisory Fraud Triage
                      </span>
                      <h4 className="text-sm font-bold text-[#142b3a]">
                        Risk Assessment: {reviewDetail.fraud_assessment?.risk_level?.toUpperCase() ?? "UNASSESSED"}
                      </h4>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-[#bd3e2b] shadow-sm">
                      Score: {reviewDetail.fraud_assessment?.risk_score != null ? `${Math.round(reviewDetail.fraud_assessment.risk_score * 100)}%` : "—"}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-[#8b9a9f]">
                    AI advisory score only (automated_decision = false). This assessment is strictly confidential and never visible to customers.
                  </p>

                  {reviewDetail.fraud_assessment?.indicators && reviewDetail.fraud_assessment.indicators.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-bold text-[#526b75]">Triggered Risk Indicators:</p>
                      <ul className="mt-1 space-y-1 text-xs text-[#788990]">
                        {reviewDetail.fraud_assessment.indicators.map((ind, i) => (
                          <li key={i} className="flex items-center gap-1.5">
                            <span className="text-[#bd3e2b]">•</span>
                            <span>
                              {ind.title || ind.rule_name || ind.description || "Risk indicator"}
                              {ind.explanation && (
                                <span className="text-[#8b9a9f]">: {ind.explanation}</span>
                              )}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Internal Reviewer Guidance (Agent 4) */}
                {reviewDetail.reviewer_guidance_result?.data && (
                  <div className="rounded-xl border border-[#d2e8fc] bg-[#f7fbff] p-4 text-xs">
                    <span className="text-[10px] font-black uppercase tracking-wider text-[#1967a3]">
                      Agent 4 · Internal Staff Guidance (Confidential)
                    </span>
                    <h4 className="mt-1 text-sm font-bold text-[#142b3a]">
                      Claims Officer Review Summary
                    </h4>

                    {reviewDetail.reviewer_guidance_result.data.reviewer_summary?.claim_overview && (
                      <p className="mt-2 font-medium text-[#365363]">
                        {reviewDetail.reviewer_guidance_result.data.reviewer_summary.claim_overview}
                      </p>
                    )}

                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      {Boolean(reviewDetail.reviewer_guidance_result.data.reviewer_summary?.policy_findings?.length) && (
                        <div className="rounded bg-white p-3 shadow-sm">
                          <strong className="text-[#123c42]">Policy Findings:</strong>
                          <ul className="mt-1 list-disc pl-4 text-[#526b75]">
                            {reviewDetail.reviewer_guidance_result.data.reviewer_summary?.policy_findings?.map((f: string, i: number) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {Boolean(reviewDetail.reviewer_guidance_result.data.reviewer_summary?.reviewer_action_points?.length) && (
                        <div className="rounded bg-white p-3 shadow-sm">
                          <strong className="text-[#123c42]">Recommended Officer Actions:</strong>
                          <ul className="mt-1 list-disc pl-4 text-[#526b75]">
                            {reviewDetail.reviewer_guidance_result.data.reviewer_summary?.reviewer_action_points?.map((a: string, i: number) => (
                              <li key={i}>{a}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Authoritative Human Decision Section */}
                {reviewDetail.human_decision ? (
                  <div className="rounded-xl border border-[#c2ebd5] bg-[#e8f7ee] p-4">
                    <p className="text-xs font-bold uppercase tracking-wider text-[#17734c]">
                      Decision Already Submitted
                    </p>
                    <p className="mt-1 text-sm font-black text-[#142b3a]">
                      Decision: {reviewDetail.human_decision.decision?.toUpperCase()}
                    </p>
                    <p className="mt-1 text-xs text-[#526b75]">
                      <strong>Officer:</strong> {reviewDetail.human_decision.reviewer_id} · <strong>Date:</strong> {reviewDetail.human_decision.decided_at ? new Date(reviewDetail.human_decision.decided_at).toLocaleString() : "—"}
                    </p>
                    <p className="mt-2 text-xs text-[#142b3a]">
                      <strong>Reason:</strong> {reviewDetail.human_decision.reason}
                    </p>
                  </div>
                ) : (
                  <div className="rounded-xl border border-[#123c42]/20 bg-[#f9fbfb] p-5">
                    <h4 className="text-sm font-black text-[#142b3a]">
                      Authoritative Claims Officer Decision
                    </h4>
                    <p className="mt-0.5 text-xs text-[#788990]">
                      AI never approves or rejects. As the designated officer, enter your authoritative decision.
                    </p>

                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="block text-xs font-bold text-[#526b75]">
                          Select Decision
                        </label>
                        <select
                          value={decisionType}
                          onChange={(e) =>
                            setDecisionType(
                              e.target.value as
                                | "approve"
                                | "reject"
                                | "request_more_information"
                                | "escalate",
                            )
                          }
                          className="mt-1 w-full rounded-lg border border-[#dbe5e5] bg-white p-2.5 text-xs font-semibold text-[#142b3a]"
                        >
                          <option value="approve">Approve Claim</option>
                          <option value="reject">Reject Claim (Reason Required)</option>
                          <option value="request_more_information">Request More Information</option>
                          <option value="escalate">Escalate for Specialist Review</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-[#526b75]">
                          Authoritative Reason {decisionType === "reject" ? "(Mandatory)" : "(Required for rejection/info)"}
                        </label>
                        <textarea
                          rows={2}
                          value={decisionReason}
                          onChange={(e) => setDecisionReason(e.target.value)}
                          placeholder={
                            decisionType === "reject"
                              ? "Specify mandatory justification for rejecting this claim…"
                              : "Enter rationale for decision…"
                          }
                          className="mt-1 w-full rounded-lg border border-[#dbe5e5] p-2 text-xs"
                        />
                      </div>
                    </div>

                    <div className="mt-4 flex items-center justify-end gap-3">
                      <button
                        onClick={closeReviewModal}
                        className="rounded-lg px-4 py-2 text-xs font-bold text-[#788990] hover:bg-slate-100"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => void handleSubmitDecision()}
                        disabled={decisionSubmitting}
                        className="rounded-lg bg-[#123c42] px-5 py-2 text-xs font-bold text-white hover:bg-[#1d4d52]"
                      >
                        {decisionSubmitting ? "Submitting Decision…" : "Submit Authoritative Decision"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}

function Header({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="mb-6">
      <p className="mb-2 text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#d75b36]">
        Admin risk operations
      </p>
      <h2 className="text-2xl font-black tracking-[-0.03em] text-[#142b3a]">
        {title}
      </h2>
      <p className="mt-1 text-sm text-[#778590]">{detail}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#f5f8f8] p-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-[#8b9a9f]">
        {label}
      </p>
      <p className="mt-2 text-xl font-black">{value}</p>
    </div>
  );
}

const POLICY_LABELS: Record<PolicyCategory, { label: string; desc: string; badge: string }> = {
  full_comprehensive: {
    label: "Full Comprehensive",
    desc: "All Perils: Collision, fire, theft, flood, windscreen, vandalism & third-party liability.",
    badge: "bg-emerald-50 text-emerald-800 border-emerald-200",
  },
  partial_comprehensive: {
    label: "Partial Comprehensive",
    desc: "Fire, theft, flood, windscreen & third-party. Explicitly excludes ordinary own-vehicle collision.",
    badge: "bg-blue-50 text-blue-800 border-blue-200",
  },
  third_party: {
    label: "Third Party Liability",
    desc: "Third-party bodily injury & property damage only. Explicitly excludes all own-vehicle damage.",
    badge: "bg-amber-50 text-amber-800 border-amber-200",
  },
};

function CustomerManagement() {
  const [customers, setCustomers] = useState<AdminCustomer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [policyType, setPolicyType] = useState<PolicyCategory>("full_comprehensive");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<{
    name: string;
    email: string;
    policyNumber: string;
    policyType: PolicyCategory;
  } | null>(null);

  const loadCustomers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCustomersList();
      setCustomers(data.customers);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load customer accounts."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCustomers();
  }, []);

  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessInfo(null);

    if (!name.trim()) {
      setFormError("Full name is required.");
      return;
    }
    if (!email.trim() || !email.includes("@")) {
      setFormError("A valid email address is required.");
      return;
    }
    if (password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createCustomerAccount({
        name: name.trim(),
        email: email.trim(),
        password,
        policy_type: policyType,
      });

      setSuccessInfo({
        name: created.name ?? name.trim(),
        email: created.email,
        policyNumber: created.policy_number,
        policyType: created.policy_type,
      });

      // Clear inputs
      setName("");
      setEmail("");
      setPassword("");
      setPolicyType("full_comprehensive");

      // Reload customer directory
      await loadCustomers();
    } catch (err) {
      setFormError(getApiErrorMessage(err, "Failed to create customer account."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Header
        title="Customer & Policy Access Management"
        detail="Authorized internal provisioner: Create customer credentials with assigned motor-policy categories and manage customer access."
      />

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Create Customer Form */}
        <div className="lg:col-span-5">
          <Card>
            <div className="border-b border-[#eef2f2] pb-4">
              <h3 className="text-base font-black text-[#142b3a]">
                Create Customer Account
              </h3>
              <p className="mt-1 text-xs text-[#788990]">
                Provision portal credentials and assign a binding motor-policy category.
              </p>
            </div>

            {formError && (
              <div
                role="alert"
                className="mt-4 rounded-lg border border-[#f1d7cd] bg-[#fffaf7] p-3 text-xs font-bold text-[#bd3e2b]"
              >
                {formError}
              </div>
            )}

            {successInfo && (
              <div
                role="status"
                className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900"
              >
                <p className="font-black text-emerald-950">✓ Customer Account Created</p>
                <p className="mt-1">
                  <strong>{successInfo.name}</strong> ({successInfo.email}) has been provisioned with policy{" "}
                  <strong>{successInfo.policyNumber}</strong> under{" "}
                  <span className="font-bold underline">
                    {POLICY_LABELS[successInfo.policyType]?.label ?? successInfo.policyType}
                  </span>.
                </p>
              </div>
            )}

            <form onSubmit={handleCreateCustomer} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-[#142b3a]">
                  Customer Full Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Johnathan Smith"
                  required
                  className="mt-1 w-full rounded-lg border border-[#dbe5e5] px-3 py-2 text-xs focus:border-[#123c42] focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[#142b3a]">
                  Customer Email Address <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. jsmith@example.com"
                  required
                  className="mt-1 w-full rounded-lg border border-[#dbe5e5] px-3 py-2 text-xs focus:border-[#123c42] focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-[#8b9a9f]">
                  Must be unique across the organization.
                </p>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#142b3a]">
                  Initial Password <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  minLength={8}
                  required
                  className="mt-1 w-full rounded-lg border border-[#dbe5e5] px-3 py-2 text-xs focus:border-[#123c42] focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-[#8b9a9f]">
                  Hashed securely using Argon2id before database storage.
                </p>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#142b3a]">
                  Motor-Policy Category <span className="text-red-500">*</span>
                </label>
                <select
                  value={policyType}
                  onChange={(e) => setPolicyType(e.target.value as PolicyCategory)}
                  className="mt-1 w-full rounded-lg border border-[#dbe5e5] bg-white px-3 py-2 text-xs font-medium focus:border-[#123c42] focus:outline-none"
                >
                  <option value="full_comprehensive">Full Comprehensive</option>
                  <option value="partial_comprehensive">Partial Comprehensive</option>
                  <option value="third_party">Third Party Liability Only</option>
                </select>

                <div className="mt-2 rounded-lg bg-[#f8fafb] border border-[#e5ecec] p-2.5 text-[11px] text-[#4b5563]">
                  <p className="font-semibold text-[#142b3a]">
                    {POLICY_LABELS[policyType]?.label} Scope:
                  </p>
                  <p className="mt-0.5">{POLICY_LABELS[policyType]?.desc}</p>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-[#123c42] py-2.5 text-xs font-bold text-white transition-colors hover:bg-[#1d4d52] disabled:opacity-50"
              >
                {submitting ? "Provisioning Customer Account…" : "Create Customer Account"}
              </button>
            </form>
          </Card>
        </div>

        {/* Customer Directory Table */}
        <div className="lg:col-span-7">
          <Card>
            <div className="flex items-center justify-between border-b border-[#eef2f2] pb-4">
              <div>
                <h3 className="text-base font-black text-[#142b3a]">
                  Customer Directory ({customers.length})
                </h3>
                <p className="mt-1 text-xs text-[#788990]">
                  Active customers and their linked motor policy categories.
                </p>
              </div>
              <button
                onClick={() => void loadCustomers()}
                disabled={loading}
                className="rounded-lg border border-[#dbe5e5] px-3 py-1.5 text-xs font-bold text-[#142b3a] hover:bg-slate-50 disabled:opacity-50"
              >
                {loading ? "Refreshing…" : "Refresh"}
              </button>
            </div>

            {error && (
              <div
                role="alert"
                className="mt-4 rounded-lg border border-[#f1d7cd] bg-[#fffaf7] p-3 text-xs font-bold text-[#bd3e2b]"
              >
                {error}
              </div>
            )}

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#eef2f2] text-[11px] font-bold text-[#788990]">
                    <th className="pb-2.5">Customer</th>
                    <th className="pb-2.5">Policy Number</th>
                    <th className="pb-2.5">Policy Category</th>
                    <th className="pb-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#f2f6f6]">
                  {loading && customers.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-[#8b9a9f]">
                        Loading customer records…
                      </td>
                    </tr>
                  ) : customers.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-[#8b9a9f]">
                        No customer accounts found. Use the form to create the first customer.
                      </td>
                    </tr>
                  ) : (
                    customers.map((c) => {
                      const categoryInfo = c.policy_type ? POLICY_LABELS[c.policy_type] : null;
                      return (
                        <tr key={c.user_id} className="hover:bg-[#fbfcfc]">
                          <td className="py-3">
                            <p className="font-bold text-[#142b3a]">{c.name || "Customer"}</p>
                            <p className="text-[11px] text-[#788990]">{c.email}</p>
                          </td>
                          <td className="py-3 font-mono text-[11px] text-[#4b5563]">
                            {c.policy_number ?? "—"}
                          </td>
                          <td className="py-3">
                            {categoryInfo ? (
                              <span
                                className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${categoryInfo.badge}`}
                              >
                                {categoryInfo.label}
                              </span>
                            ) : (
                              <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500">
                                None assigned
                              </span>
                            )}
                          </td>
                          <td className="py-3">
                            <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                              Active
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

