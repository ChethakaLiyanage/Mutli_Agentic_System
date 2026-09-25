import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import {
  clarifyWorkflow,
  getWorkflow,
  getOrchestratorErrorMessage,
  isWorkflowNotFoundError,
  processRequest,
  submitClaim,
  uploadWorkflowDocument,
} from "../api/orchestrator";
import { DocumentUploadModal } from "../components/DocumentUploadModal";
import { WorkflowStatusBadge } from "../components/WorkflowStatusBadge";
import type { ChatMessage } from "../types/chat";
import {
  isOrchestratorResponse,
  type OrchestratorResponse,
  type WorkflowStatus,
  type WorkflowResponse,
} from "../types/orchestrator";
import "../claim-assistant.css";

const MAX_MESSAGE_LENGTH = 3000;
export const ACTIVE_WORKFLOW_KEY = "motor_insurance_active_workflow_id";

const TRACKED_WORKFLOW_STATUSES = new Set<WorkflowStatus>([
  "awaiting_clarification",
  "awaiting_documents",
  "documents_submitted",
  "fraud_triage",
  "fraud_triage_complete",
  "review_summary_generation",
  "awaiting_assignment",
  "under_human_review",
  "awaiting_human_review",
  "more_information_required",
]);

const SUBMITTED_CLAIM_STATUSES = new Set<WorkflowStatus>([
  "documents_submitted",
  "fraud_triage",
  "fraud_triage_complete",
  "review_summary_generation",
  "awaiting_assignment",
  "under_human_review",
  "awaiting_human_review",
  "more_information_required",
  "escalated",
  "approved",
  "rejected",
  "completed",
]);

const isPureGreetingResponse = (response: WorkflowResponse): boolean =>
  isOrchestratorResponse(response) &&
  response.status === "completed" &&
  response.workflow_type === "unknown" &&
  response.intake_result?.data.intent.label === "greeting";

const needsWorkflowTracking = (response: WorkflowResponse): boolean =>
  TRACKED_WORKFLOW_STATUSES.has(response.status);

const examples = [
  "I want to make an insurance claim.",
  "My windscreen was damaged yesterday.",
  "Does my policy cover flood damage?",
];

const makeId = (prefix: string): string => {
  const value = globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${value}`;
};

const createMessage = (
  sender: ChatMessage["sender"],
  text: string,
): ChatMessage => ({
  id: makeId("MSG"),
  sender,
  text,
  timestamp: new Date().toISOString(),
});

const resultMessage = (response: WorkflowResponse): string => {
  const backendMessage = response.guidance_result?.data.message || response.message;
  if (backendMessage) return backendMessage;
  return "We couldn't display the assistant's response. Please try again.";
};

const submittedClaimMessage = (response: OrchestratorResponse): string => {
  const currentMessage = resultMessage(response);
  if (!SUBMITTED_CLAIM_STATUSES.has(response.status)) return currentMessage;
  return [
    "Current claim status",
    currentMessage,
    "",
    "Status updates",
    "You can check your claim status through your profile, or simply ask me here in chat.",
  ].join("\n");
};

export const ClaimAssistantPage = () => {
  const searchParams = new URLSearchParams(window.location.search);
  const requestedWorkflowId = searchParams.get("workflowId");
  const requestedAction = searchParams.get("action");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [trackedWorkflow, setTrackedWorkflow] = useState<WorkflowResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [submittingClaim, setSubmittingClaim] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeClaimWf =
    workflow && needsWorkflowTracking(workflow)
      ? workflow
      : trackedWorkflow && needsWorkflowTracking(trackedWorkflow)
        ? trackedWorkflow
        : workflow;
  const canClarify = activeClaimWf?.status === "awaiting_clarification";
  const canSend = !sending && !restoring;
  const hasConversation = messages.length > 0 || workflow !== null;

  const applyWorkflow = useCallback((response: WorkflowResponse) => {
    if (isPureGreetingResponse(response)) {
      if (sessionStorage.getItem(ACTIVE_WORKFLOW_KEY) === response.workflow_id) {
        sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
      }
      return;
    }

    if (
      isOrchestratorResponse(response) &&
      response.workflow_type === "information_request"
    ) {
      if (response.pending_claim_workflow_id) {
        sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, response.pending_claim_workflow_id);
      }
      return;
    }

    setWorkflow(response);
    if (needsWorkflowTracking(response)) {
      setTrackedWorkflow(response);
      sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, response.workflow_id);
      return;
    }

    setTrackedWorkflow((current) => {
      if (current?.workflow_id === response.workflow_id) return null;
      return current;
    });
    if (sessionStorage.getItem(ACTIVE_WORKFLOW_KEY) === response.workflow_id) {
      sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
    }
  }, []);

  useEffect(() => {
    const storedWorkflowId = requestedWorkflowId || sessionStorage.getItem(ACTIVE_WORKFLOW_KEY);
    if (!storedWorkflowId) return;

    let active = true;
    const restoreWorkflow = async () => {
      setRestoring(true);
      try {
        const response = await getWorkflow(storedWorkflowId);
        if (!active) return;
        applyWorkflow(response);
        setMessages([createMessage("system", resultMessage(response))]);
        if (
          requestedAction === "upload-documents" &&
          isOrchestratorResponse(response) &&
          response.status === "awaiting_documents"
        ) {
          setUploadModalOpen(true);
        }
      } catch (requestError) {
        if (!active) return;
        sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
        if (!isWorkflowNotFoundError(requestError)) {
          setError(getOrchestratorErrorMessage(requestError));
        }
      } finally {
        if (active) setRestoring(false);
      }
    };

    void restoreWorkflow();
    return () => {
      active = false;
    };
  }, [applyWorkflow, requestedAction, requestedWorkflowId]);

  useEffect(() => {
    if (canSend && messages.length > 0) {
      messageInputRef.current?.focus();
    }
  }, [canSend, messages.length]);

  /* Auto-scroll to bottom when new messages arrive */
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const submitMessage = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!canSend) return;

    const text = input.trim();
    if (text.length < 2) {
      setError("Enter at least 2 characters before sending.");
      return;
    }
    if (text.length > MAX_MESSAGE_LENGTH) {
      setError(`Messages must contain at most ${MAX_MESSAGE_LENGTH} characters.`);
      return;
    }

    setError(null);
    setSending(true);
    setMessages((current) => [...current, createMessage("user", text)]);
    setInput("");

    try {
      const contextWorkflowId =
        workflow && isOrchestratorResponse(workflow) && workflow.claim_id
          ? workflow.workflow_id
          : undefined;
      const request = {
        request_id: makeId("REQ"),
        text,
        ...(contextWorkflowId
          ? { context_workflow_id: contextWorkflowId }
          : {}),
      };
      const isGreeting = /^(hi|hello|hey|good morning|good afternoon|good evening)\b/i.test(text);
      const isQuestion = /^(can|does|what|where|how|tell me|is|are|why)\b/i.test(text);
      const targetWorkflow = activeClaimWf;
      const shouldClarify = canClarify && targetWorkflow && !isGreeting && !isQuestion;
      const response = shouldClarify
        ? await clarifyWorkflow(targetWorkflow.workflow_id, request)
        : await processRequest(request);

      applyWorkflow(response);
      setMessages((current) => [
        ...current,
        createMessage("system", resultMessage(response)),
      ]);
    } catch (requestError) {
      setError(getOrchestratorErrorMessage(requestError));
    } finally {
      setSending(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const fileList = Array.from(files);
    const targetWf = workflow && isOrchestratorResponse(workflow) ? workflow : null;
    for (const file of fileList) {
      if (targetWf && targetWf.status === "awaiting_documents") {
        try {
          await uploadWorkflowDocument(targetWf.workflow_id, file);
        } catch (uploadErr) {
          setError(getOrchestratorErrorMessage(uploadErr));
        }
      }
    }

    const fileNames = fileList.map((f) => f.name).join(", ");
    setMessages((prev) => [
      ...prev,
      createMessage("user", `Uploaded ${fileList.length} document(s): ${fileNames}`),
      createMessage(
        "system",
        `Thank you. We have received your uploaded document(s): ${fileNames}. They are attached to your claim draft. You can now press "Submit Claim" below to finalize your submission.`,
      ),
    ]);

    event.target.value = "";
  };

  const handleModalUploadComplete = (files: Array<{ name: string; size: string }>) => {
    const fileNames = files.map((f) => f.name).join(", ");
    setMessages((prev) => [
      ...prev,
      createMessage("user", `Uploaded ${files.length} document(s): ${fileNames}`),
      createMessage(
        "system",
        `Thank you. We have received your uploaded document(s): ${fileNames}. They are attached to your claim draft. You can now press "Submit Claim" below to finalize your submission.`,
      ),
    ]);
    if (activeOrchWf) {
      void refreshWorkflow(activeOrchWf);
    }
  };

  const handleSubmitClaim = async () => {
    if (!workflow || !isOrchestratorResponse(workflow) || submittingClaim) return;
    setSubmittingClaim(true);
    setError(null);
    try {
      const response = await submitClaim(workflow.workflow_id);
      applyWorkflow(response);
      setMessages((prev) => [
        ...prev,
        createMessage("system", submittedClaimMessage(response)),
      ]);
    } catch (submitErr) {
      setError(getOrchestratorErrorMessage(submitErr));
    } finally {
      setSubmittingClaim(false);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  };

  const resetConversation = () => {
    setInput("");
    setMessages([]);
    setWorkflow(null);
    setTrackedWorkflow(null);
    setSending(false);
    setRestoring(false);
    setError(null);
    sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
  };

  /* Resolve the active orchestrator response for inline action buttons */
  const effectiveWf = activeClaimWf || workflow;
  const activeOrchWf =
    effectiveWf && isOrchestratorResponse(effectiveWf) ? effectiveWf : null;
  const trackedOrchWf =
    trackedWorkflow &&
    trackedWorkflow.workflow_id !== activeOrchWf?.workflow_id &&
    isOrchestratorResponse(trackedWorkflow)
      ? trackedWorkflow
      : null;

  return (
    <div className="claim-assistant">
      {/* Scrollable chat area */}
      <div className="conversation-scroll" ref={scrollRef} aria-live="polite">
        {restoring && !messages.length ? (
          <div className="assistant-welcome" role="status">
            <span className="loading-spinner" aria-hidden="true" />
            <h2>Restoring your workflow…</h2>
            <p>Please wait while we retrieve its latest status.</p>
          </div>
        ) : !messages.length ? (
          <div className="assistant-welcome">
            <span className="assistant-symbol" aria-hidden="true">CA</span>
            <h2>How can we help?</h2>
            <p>Choose an example or write your own message below.</p>
            <div className="example-list">
              {examples.map((example) => (
                <button key={example} onClick={() => setInput(example)}>
                  {example}
                </button>
              ))}
            </div>
            <p className="prototype-note">
              Answers use controlled policy evidence. Claim decisions are made
              only by an authorized claims officer.
            </p>
          </div>
        ) : (
          <div className="message-list">
            {messages.map((message) => (
              <article
                className={`chat-message chat-message-${message.sender}`}
                key={message.id}
              >
                <span>{message.sender === "user" ? "You" : "Assistant"}</span>
                <p style={{ whiteSpace: "pre-line" }}>{message.text}</p>
                <time dateTime={message.timestamp}>
                  {new Date(message.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </article>
            ))}

            {/* Inline workflow action buttons (rendered as chat-like cards) */}
            {activeOrchWf && activeOrchWf.status === "awaiting_documents" && (
              <div className="chat-action-card">
                {activeOrchWf.missing_required_documents &&
                  activeOrchWf.missing_required_documents.length > 0 && (
                    <p className="chat-action-detail">
                      <strong>Missing documents:</strong>{" "}
                      {activeOrchWf.missing_required_documents
                        .map((d) => d.replace(/_/g, " "))
                        .join(", ")}
                    </p>
                  )}
                <div className="chat-action-buttons">
                  <button
                    type="button"
                    className="upload-docs-btn"
                    data-testid="upload-documents-btn"
                    onClick={() => setUploadModalOpen(true)}
                  >
                    <span className="upload-icon">📤</span>
                    Upload Documents
                  </button>
                  <button
                    className="button button-primary"
                    type="button"
                    onClick={handleSubmitClaim}
                    disabled={submittingClaim}
                  >
                    {submittingClaim ? "Submitting Claim…" : "Submit Claim"}
                  </button>
                </div>
              </div>
            )}

            {activeOrchWf &&
              (activeOrchWf.status === "documents_submitted" ||
                activeOrchWf.status === "fraud_triage" ||
                activeOrchWf.status === "fraud_triage_complete" ||
                activeOrchWf.status === "review_summary_generation" ||
                activeOrchWf.status === "awaiting_assignment") && (
                <div className="chat-action-card">
                  <WorkflowStatusBadge status={activeOrchWf.status} />
                </div>
              )}

            {activeOrchWf &&
              (activeOrchWf.status === "under_human_review" ||
                activeOrchWf.status === "awaiting_human_review") && (
                <div className="chat-action-card">
                  <WorkflowStatusBadge status={activeOrchWf.status} />
                  <p className="chat-action-detail">
                    Your claim is assigned to a claims officer.
                  </p>
                </div>
              )}

            {/* Tracked workflow (separate from current conversation) */}
            {trackedOrchWf && (
              <div className="chat-action-card">
                <WorkflowStatusBadge status={trackedOrchWf.status} />
                <p className="chat-action-detail">
                  Tracked workflow: {trackedOrchWf.workflow_id}
                </p>
              </div>
            )}

            {sending && (
              <div className="assistant-thinking" role="status">
                <span className="loading-spinner" aria-hidden="true" />
                Reviewing your message…
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && <div className="alert alert-error assistant-error" role="alert">{error}</div>}

      {/* Sticky input bar */}
      <form className="message-composer" onSubmit={submitMessage}>
        <div className="composer-input-row">
          <textarea
            ref={messageInputRef}
            id="claim-message"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            minLength={2}
            maxLength={MAX_MESSAGE_LENGTH}
            rows={2}
            placeholder={canClarify ? "Add the missing details…" : "Describe your claim or policy question…"}
            disabled={!canSend}
            aria-label="Your message"
          />
          <button
            className="composer-send-btn button button-primary"
            type="submit"
            disabled={!canSend || input.trim().length < 2}
            aria-label="Send message"
          >
            {sending ? (
              <span className="loading-spinner loading-spinner-sm" aria-hidden="true" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <div className="composer-footer">
          <span>{input.length} / {MAX_MESSAGE_LENGTH}</span>
          <span>Enter to send · Shift+Enter for a new line</span>
          {hasConversation && (
            <button
              className="button button-secondary button-small"
              type="button"
              onClick={resetConversation}
            >
              New Chat
            </button>
          )}
        </div>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
          style={{ display: "none" }}
        />
      </form>

      {/* Document upload modal */}
      {uploadModalOpen && activeOrchWf && (
        <DocumentUploadModal
          workflowId={activeOrchWf.workflow_id}
          missingDocuments={activeOrchWf.missing_required_documents ?? []}
          onClose={() => setUploadModalOpen(false)}
          onUploadComplete={handleModalUploadComplete}
        />
      )}
    </div>
  );
};
