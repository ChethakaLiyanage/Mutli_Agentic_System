import React, { useEffect, useState } from "react";
import {
  fetchPolicyDocuments,
  fetchPolicyDocumentDetail,
  fetchPolicyDocumentVersions,
  uploadPolicyDocument,
  replacePolicyDocument,
  type PolicyDocumentItem,
  type PolicyCategory,
  type DocumentStatus,
  type DocumentAudience,
} from "../api/admin";
import { getApiErrorMessage } from "../api/client";

const policyBadges: Record<string, { label: string; badge: string }> = {
  full_comprehensive: {
    label: "Full Comprehensive",
    badge: "bg-[#e8f7ee] text-[#17734c] border-[#b6e8cb]",
  },
  partial_comprehensive: {
    label: "Partial Comprehensive",
    badge: "bg-[#e8f4ff] text-[#1967a3] border-[#bad8f5]",
  },
  third_party: {
    label: "Third Party",
    badge: "bg-[#fff5df] text-[#a66800] border-[#fae2a6]",
  },
};

const statusBadges: Record<DocumentStatus, { label: string; badge: string }> = {
  active: {
    label: "Active",
    badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  processing: {
    label: "Processing",
    badge: "bg-amber-50 text-amber-700 border-amber-200 animate-pulse",
  },
  superseded: {
    label: "Superseded",
    badge: "bg-slate-100 text-slate-600 border-slate-200",
  },
  failed: {
    label: "Failed",
    badge: "bg-red-50 text-red-700 border-red-200",
  },
  archived: {
    label: "Archived",
    badge: "bg-zinc-100 text-zinc-600 border-zinc-200",
  },
};

export const PolicyKnowledgeManagement: React.FC = () => {
  const [documents, setDocuments] = useState<PolicyDocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [policyFilter, setPolicyFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedDocForDetail, setSelectedDocForDetail] = useState<PolicyDocumentItem | null>(null);
  const [contentPreview, setContentPreview] = useState<string | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [selectedDocForReplace, setSelectedDocForReplace] = useState<PolicyDocumentItem | null>(null);
  const [selectedDocForHistory, setSelectedDocForHistory] = useState<PolicyDocumentItem | null>(null);
  const [historyVersions, setHistoryVersions] = useState<PolicyDocumentItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Add form state
  const [addTitle, setAddTitle] = useState("");
  const [addDocType, setAddDocType] = useState("policy_document");
  const [addPolicyType, setAddPolicyType] = useState<string>("none");
  const [addAudience, setAddAudience] = useState<DocumentAudience>("customer");
  const [addVersion, setAddVersion] = useState("1.0");
  const [addFile, setAddFile] = useState<File | null>(null);
  const [submittingAdd, setSubmittingAdd] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Replace form state
  const [replaceVersion, setReplaceVersion] = useState("");
  const [replaceTitle, setReplaceTitle] = useState("");
  const [replaceChangeSummary, setReplaceChangeSummary] = useState("");
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [submittingReplace, setSubmittingReplace] = useState(false);
  const [replaceError, setReplaceError] = useState<string | null>(null);

  const loadDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPolicyDocuments({ root_only: true });
      setDocuments(data.documents);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load policy documents."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDocuments();
  }, []);

  const openDetailModal = async (doc: PolicyDocumentItem) => {
    setSelectedDocForDetail(doc);
    setContentPreview(null);
    setLoadingDetail(true);
    try {
      const detail = await fetchPolicyDocumentDetail(doc.id);
      setContentPreview(detail.content_preview || null);
    } catch {
      setContentPreview("Could not load preview text for this document.");
    } finally {
      setLoadingDetail(false);
    }
  };

  const openReplaceModal = (doc: PolicyDocumentItem) => {
    setSelectedDocForReplace(doc);
    setReplaceTitle(doc.title);
    // Suggest next minor version, e.g. 1.0 -> 1.1 or 2.0
    const parts = doc.version.split(".");
    if (parts.length >= 2) {
      setReplaceVersion(`${parseInt(parts[0]) + 1}.0`);
    } else {
      setReplaceVersion("2.0");
    }
    setReplaceChangeSummary("");
    setReplaceFile(null);
    setReplaceError(null);
  };

  const openHistoryModal = async (doc: PolicyDocumentItem) => {
    setSelectedDocForHistory(doc);
    setLoadingHistory(true);
    try {
      const res = await fetchPolicyDocumentVersions(doc.id);
      setHistoryVersions(res.versions);
    } catch {
      setHistoryVersions([doc]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError(null);

    if (!addTitle.trim()) {
      setAddError("Document title is required.");
      return;
    }
    if (!addFile) {
      setAddError("Please select a document file (.txt, .pdf, or .docx).");
      return;
    }
    if (addDocType === "policy_document" && addPolicyType === "none") {
      setAddError("Policy category is required for a policy document.");
      return;
    }

    setSubmittingAdd(true);
    try {
      const formData = new FormData();
      formData.append("title", addTitle.trim());
      formData.append("document_type", addDocType);
      if (addPolicyType !== "none") {
        formData.append("policy_type", addPolicyType);
      }
      formData.append("audience", addAudience);
      formData.append("version", addVersion.trim() || "1.0");
      formData.append("file", addFile);

      const res = await uploadPolicyDocument(formData);
      setSuccessBanner(
        `Document "${res.document.title}" uploaded & ingested successfully. ${res.document.chunks_count} chunks indexed into Agent 2.`
      );
      setShowAddModal(false);
      setAddTitle("");
      setAddFile(null);
      void loadDocuments();
    } catch (err) {
      setAddError(getApiErrorMessage(err, "Failed to upload and ingest document."));
    } finally {
      setSubmittingAdd(false);
    }
  };

  const handleReplaceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocForReplace) return;
    setReplaceError(null);

    if (!replaceVersion.trim()) {
      setReplaceError("Version string is required.");
      return;
    }
    if (!replaceFile) {
      setReplaceError("Please select a replacement file.");
      return;
    }

    setSubmittingReplace(true);
    try {
      const formData = new FormData();
      formData.append("version", replaceVersion.trim());
      if (replaceTitle.trim()) {
        formData.append("title", replaceTitle.trim());
      }
      if (replaceChangeSummary.trim()) {
        formData.append("change_summary", replaceChangeSummary.trim());
      }
      formData.append("file", replaceFile);

      const res = await replacePolicyDocument(selectedDocForReplace.id, formData);
      setSuccessBanner(
        `Document "${res.document.title}" upgraded to V${res.document.version}. Previous version superseded; Agent 2 TF-IDF index refreshed automatically.`
      );
      setSelectedDocForReplace(null);
      void loadDocuments();
    } catch (err) {
      setReplaceError(getApiErrorMessage(err, "Failed to process and activate replacement document."));
    } finally {
      setSubmittingReplace(false);
    }
  };

  // Filtered documents
  const filtered = documents.filter((doc) => {
    const matchesSearch =
      doc.title.toLowerCase().includes(search.toLowerCase()) ||
      doc.original_filename.toLowerCase().includes(search.toLowerCase());
    const matchesPolicy =
      policyFilter === "all" ||
      (policyFilter === "common" && !doc.policy_type) ||
      doc.policy_type === policyFilter;
    const matchesStatus = statusFilter === "all" || doc.status === statusFilter;
    return matchesSearch && matchesPolicy && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-[#142b3a]">
            Policy & Knowledge Document Management
          </h2>
          <p className="mt-1 text-xs text-[#527278]">
            Manage authoritative insurance policies, procedural guides, and retrieval chunks for Agent 2 with live zero-restart index updates.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowAddModal(true);
            setAddError(null);
          }}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#123c42] px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-[#1a555e]"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add New Document
        </button>
      </div>

      {/* Success Notification Banner */}
      {successBanner && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800">
          <div className="flex items-center gap-2">
            <svg className="h-4 w-4 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span>{successBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-700 hover:text-emerald-900"
          >
            ✕
          </button>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs font-medium text-red-700">
          {error}
        </div>
      )}

      {/* Filters & Search */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[#dfe7e7] bg-white p-3.5 shadow-sm">
        <div className="relative flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Search documents by title or filename..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-[#cfdede] bg-[#fbfdfd] px-3.5 py-2 text-xs text-[#142b3a] outline-none transition focus:border-[#123c42]"
          />
        </div>

        <select
          value={policyFilter}
          onChange={(e) => setPolicyFilter(e.target.value)}
          className="rounded-lg border border-[#cfdede] bg-[#fbfdfd] px-3 py-2 text-xs text-[#142b3a] outline-none transition focus:border-[#123c42]"
        >
          <option value="all">All Policy Categories</option>
          <option value="full_comprehensive">Full Comprehensive</option>
          <option value="partial_comprehensive">Partial Comprehensive</option>
          <option value="third_party">Third Party</option>
          <option value="common">Common / General</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-[#cfdede] bg-[#fbfdfd] px-3 py-2 text-xs text-[#142b3a] outline-none transition focus:border-[#123c42]"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="processing">Processing</option>
          <option value="superseded">Superseded</option>
          <option value="failed">Failed</option>
        </select>

        <button
          type="button"
          onClick={() => void loadDocuments()}
          className="rounded-lg border border-[#cfdede] bg-white px-3 py-2 text-xs font-medium text-[#527278] hover:bg-slate-50"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Documents Table */}
      <div className="overflow-hidden rounded-xl border border-[#dfe7e7] bg-white shadow-[0_5px_18px_rgba(20,43,58,0.04)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#dfe7e7] bg-[#f7faf9] text-[11px] font-bold uppercase tracking-wider text-[#527278]">
              <tr>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Document Type</th>
                <th className="px-4 py-3">Policy Category</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Audience</th>
                <th className="px-4 py-3">Chunks</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf3f3] text-[#142b3a]">
              {loading && documents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-[#778590]">
                    Loading policy knowledge base...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-[#778590]">
                    No documents found matching the filters.
                  </td>
                </tr>
              ) : (
                filtered.map((doc) => {
                  const policyInfo = doc.policy_type ? policyBadges[doc.policy_type] : null;
                  const statusInfo = statusBadges[doc.status] || {
                    label: doc.status,
                    badge: "bg-slate-100 text-slate-600 border-slate-200",
                  };

                  return (
                    <tr key={doc.id} className="transition hover:bg-[#fafcfc]">
                      <td className="px-4 py-3">
                        <div className="font-bold text-[#142b3a]">{doc.title}</div>
                        <div className="font-mono text-[10px] text-[#778590]">{doc.original_filename}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-700">
                          {doc.document_type.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {policyInfo ? (
                          <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${policyInfo.badge}`}>
                            {policyInfo.label}
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500">
                            General / Common
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-semibold text-[#123c42]">
                        V{doc.version}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium ${
                            doc.audience === "internal"
                              ? "bg-purple-50 text-purple-700"
                              : "bg-blue-50 text-blue-700"
                          }`}
                        >
                          {doc.audience}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[#527278]">
                        {doc.chunks_count > 0 ? (
                          <span className="font-mono">{doc.chunks_count} chunks</span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${statusInfo.badge}`}>
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => void openDetailModal(doc)}
                            className="rounded border border-[#cfdede] bg-white px-2 py-1 text-[11px] font-semibold text-[#123c42] hover:bg-[#f0f6f6]"
                          >
                            View
                          </button>
                          <button
                            type="button"
                            onClick={() => openReplaceModal(doc)}
                            className="rounded border border-[#123c42] bg-[#123c42] px-2 py-1 text-[11px] font-semibold text-white hover:bg-[#1a555e]"
                          >
                            Update
                          </button>
                          <button
                            type="button"
                            onClick={() => void openHistoryModal(doc)}
                            className="rounded border border-[#cfdede] bg-white px-2 py-1 text-[11px] text-[#527278] hover:bg-slate-50"
                          >
                            History
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ========================================================= */}
      {/* 1. ADD NEW DOCUMENT MODAL */}
      {/* ========================================================= */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between border-b border-[#dfe7e7] pb-3">
              <h3 className="text-lg font-black text-[#142b3a]">Add New Policy / Knowledge Document</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            {addError && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                {addError}
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                  Document Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Collision Reporting Deadlines"
                  value={addTitle}
                  onChange={(e) => setAddTitle(e.target.value)}
                  className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                    Document Type
                  </label>
                  <select
                    value={addDocType}
                    onChange={(e) => setAddDocType(e.target.value)}
                    className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                  >
                    <option value="policy_document">Policy Document</option>
                    <option value="procedure_guide">Procedure Guide</option>
                    <option value="guideline">Guideline</option>
                    <option value="policy_manual">Policy Manual</option>
                    <option value="manual">Manual</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                    Policy Category
                  </label>
                  <select
                    value={addPolicyType}
                    onChange={(e) => setAddPolicyType(e.target.value)}
                    required={addDocType === "policy_document"}
                    className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                  >
                    <option value="none" disabled={addDocType === "policy_document"}>
                      {addDocType === "policy_document"
                        ? "Select a policy category"
                        : "Not Policy Specific (Common)"}
                    </option>
                    <option value="full_comprehensive">Full Comprehensive</option>
                    <option value="partial_comprehensive">Partial Comprehensive</option>
                    <option value="third_party">Third Party</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                    Audience
                  </label>
                  <select
                    value={addAudience}
                    onChange={(e) => setAddAudience(e.target.value as DocumentAudience)}
                    className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                  >
                    <option value="customer">Customer (Public Retrieval)</option>
                    <option value="internal">Internal (Staff & Reviewers Only)</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                    Version
                  </label>
                  <input
                    type="text"
                    value={addVersion}
                    onChange={(e) => setAddVersion(e.target.value)}
                    placeholder="1.0"
                    className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                  Document File (.txt, .pdf, .docx) *
                </label>
                <input
                  type="file"
                  accept=".txt,.pdf,.docx"
                  required
                  onChange={(e) => setAddFile(e.target.files?.[0] || null)}
                  className="w-full rounded-lg border border-[#cfdede] bg-[#fbfdfd] p-2 text-xs text-[#527278] file:mr-3 file:rounded file:border-0 file:bg-[#123c42] file:px-3 file:py-1 file:text-xs file:font-semibold file:text-white hover:file:bg-[#1a555e]"
                />
              </div>

              <div className="mt-6 flex justify-end gap-2 border-t border-[#dfe7e7] pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingAdd}
                  className="rounded-lg bg-[#123c42] px-5 py-2 text-xs font-bold text-white hover:bg-[#1a555e] disabled:opacity-50"
                >
                  {submittingAdd ? "Extracting & Ingesting..." : "Upload & Ingest"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* 2. VIEW DOCUMENT DETAILS MODAL */}
      {/* ========================================================= */}
      {selectedDocForDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between border-b border-[#dfe7e7] pb-3">
              <div>
                <h3 className="text-lg font-black text-[#142b3a]">
                  {selectedDocForDetail.title}
                </h3>
                <p className="text-xs text-[#527278]">
                  Version {selectedDocForDetail.version} • {selectedDocForDetail.original_filename}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDocForDetail(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Document Type</span>
                <div className="font-semibold text-slate-800">{selectedDocForDetail.document_type}</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Policy Category</span>
                <div className="font-semibold text-slate-800">{selectedDocForDetail.policy_type || "Common"}</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Audience</span>
                <div className="font-semibold text-slate-800">{selectedDocForDetail.audience}</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5">
                <span className="text-[10px] text-slate-500 uppercase font-bold">Active Chunks</span>
                <div className="font-semibold text-slate-800">{selectedDocForDetail.chunks_count} chunks</div>
              </div>
            </div>

            <div className="mt-4">
              <div className="mb-1 text-xs font-bold text-[#142b3a]">Document Content Preview</div>
              {loadingDetail ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-400">
                  Loading content preview...
                </div>
              ) : (
                <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg border border-[#dfe7e7] bg-[#fbfdfd] p-3 text-[11px] font-mono text-[#142b3a]">
                  {contentPreview || "No preview available."}
                </pre>
              )}
            </div>

            <div className="mt-6 flex justify-between items-center border-t border-[#dfe7e7] pt-4">
              <span className="text-[10px] text-slate-400 font-mono">
                Checksum: {selectedDocForDetail.checksum?.slice(0, 16)}...
              </span>
              <button
                type="button"
                onClick={() => setSelectedDocForDetail(null)}
                className="rounded-lg bg-[#123c42] px-4 py-2 text-xs font-bold text-white hover:bg-[#1a555e]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* 3. UPDATE / ATOMIC REPLACE DOCUMENT MODAL */}
      {/* ========================================================= */}
      {selectedDocForReplace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between border-b border-[#dfe7e7] pb-3">
              <div>
                <h3 className="text-lg font-black text-[#142b3a]">
                  Update / Replace Document
                </h3>
                <p className="text-xs text-[#527278]">
                  Current active: {selectedDocForReplace.title} (V{selectedDocForReplace.version})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDocForReplace(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            {/* Zero downtime guarantee banner */}
            <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
              <span className="font-bold">Zero-Downtime Guarantee:</span> The current active version (V{selectedDocForReplace.version}) remains live and searchable until the new version successfully processes and is activated. If processing fails, the existing version stays active.
            </div>

            {replaceError && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                {replaceError}
              </div>
            )}

            <form onSubmit={handleReplaceSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                  New Version String *
                </label>
                <input
                  type="text"
                  required
                  value={replaceVersion}
                  onChange={(e) => setReplaceVersion(e.target.value)}
                  placeholder="e.g. 2.0 or 1.1"
                  className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                  Document Title (Optional Override)
                </label>
                <input
                  type="text"
                  value={replaceTitle}
                  onChange={(e) => setReplaceTitle(e.target.value)}
                  className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                  Change Summary / Audit Notes
                </label>
                <input
                  type="text"
                  placeholder="e.g. Extended collision reporting timeline from 7 to 14 days"
                  value={replaceChangeSummary}
                  onChange={(e) => setReplaceChangeSummary(e.target.value)}
                  className="w-full rounded-lg border border-[#cfdede] px-3 py-2 text-xs outline-none focus:border-[#123c42]"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-bold text-[#142b3a]">
                  Replacement Document File (.txt, .pdf, .docx) *
                </label>
                <input
                  type="file"
                  accept=".txt,.pdf,.docx"
                  required
                  onChange={(e) => setReplaceFile(e.target.files?.[0] || null)}
                  className="w-full rounded-lg border border-[#cfdede] bg-[#fbfdfd] p-2 text-xs text-[#527278] file:mr-3 file:rounded file:border-0 file:bg-[#123c42] file:px-3 file:py-1 file:text-xs file:font-semibold file:text-white hover:file:bg-[#1a555e]"
                />
              </div>

              <div className="mt-6 flex justify-end gap-2 border-t border-[#dfe7e7] pt-4">
                <button
                  type="button"
                  onClick={() => setSelectedDocForReplace(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReplace}
                  className="rounded-lg bg-[#123c42] px-5 py-2 text-xs font-bold text-white hover:bg-[#1a555e] disabled:opacity-50"
                >
                  {submittingReplace ? "Processing & Activating..." : "Process & Activate"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* 4. VERSION HISTORY MODAL */}
      {/* ========================================================= */}
      {selectedDocForHistory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between border-b border-[#dfe7e7] pb-3">
              <div>
                <h3 className="text-lg font-black text-[#142b3a]">
                  Version History
                </h3>
                <p className="text-xs text-[#527278]">
                  {selectedDocForHistory.title}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDocForHistory(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            {loadingHistory ? (
              <div className="py-8 text-center text-xs text-slate-400">Loading version audit history...</div>
            ) : (
              <div className="space-y-3">
                {historyVersions.map((v) => {
                  const statusInfo = statusBadges[v.status] || {
                    label: v.status,
                    badge: "bg-slate-100 text-slate-600 border-slate-200",
                  };
                  return (
                    <div
                      key={v.id}
                      className="flex items-center justify-between rounded-xl border border-[#dfe7e7] p-3 text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-[#123c42]">Version {v.version}</span>
                          <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${statusInfo.badge}`}>
                            {statusInfo.label}
                          </span>
                        </div>
                        {v.change_summary && (
                          <div className="mt-1 text-slate-600 italic">"{v.change_summary}"</div>
                        )}
                        <div className="mt-1 text-[10px] text-slate-400">
                          Uploaded by {v.uploaded_by} on {new Date(v.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <div className="text-right text-[11px] text-slate-500">
                        {v.chunks_count} chunks
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-6 flex justify-end border-t border-[#dfe7e7] pt-4">
              <button
                type="button"
                onClick={() => setSelectedDocForHistory(null)}
                className="rounded-lg bg-[#123c42] px-4 py-2 text-xs font-bold text-white hover:bg-[#1a555e]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
