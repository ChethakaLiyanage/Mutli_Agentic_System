import {
  useCallback,
  useEffect,
  useMemo,
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
} from "../api/orchestrator";
import { CustomerWorkflowResult } from "../components/CustomerWorkflowResult";
import { IntakeSummary } from "../components/IntakeSummary";
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
  "awaiting_human_review",
  "more_information_required",
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

export const ClaimAssistantPage = () => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [trackedWorkflow, setTrackedWorkflow] = useState<WorkflowResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);

  const canClarify = workflow?.status === "awaiting_clarification";
  const canSend = !sending && !restoring && !refreshing;
  const latestIntake = workflow?.intake_result ?? null;
  const hasConversation = messages.length > 0 || workflow !== null;
  const separateTrackedWorkflow =
    trackedWorkflow &&
    trackedWorkflow.workflow_id !== workflow?.workflow_id &&
    isOrchestratorResponse(trackedWorkflow)
      ? trackedWorkflow
      : null;

  const activity = useMemo(
    () => workflow?.audit_trail ?? [],
    [workflow],
  );

  const applyWorkflow = useCallback((response: WorkflowResponse) => {
    if (isPureGreetingResponse(response)) {
      if (sessionStorage.getItem(ACTIVE_WORKFLOW_KEY) === response.workflow_id) {
        sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
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
    const storedWorkflowId = sessionStorage.getItem(ACTIVE_WORKFLOW_KEY);
    if (!storedWorkflowId) return;

    let active = true;
    const restoreWorkflow = async () => {
      setRestoring(true);
      try {
        const response = await getWorkflow(storedWorkflowId);
        if (!active) return;
        applyWorkflow(response);
        setMessages([createMessage("system", resultMessage(response))]);
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
  }, [applyWorkflow]);

  useEffect(() => {
    if (canSend && messages.length > 0) {
      messageInputRef.current?.focus();
    }
  }, [canSend, messages.length]);

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
      const request = { request_id: makeId("REQ"), text };
      const isGreeting = /^(hi|hello|hey|good morning|good afternoon|good evening)\b/i.test(text);
      const isQuestion = /^(can|does|what|where|how|tell me|is|are|why)\b/i.test(text);
      const shouldClarify = canClarify && workflow && !isGreeting && !isQuestion;
      const response = shouldClarify
        ? await clarifyWorkflow(workflow.workflow_id, request)
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

  const refreshWorkflow = async (target: OrchestratorResponse) => {
    if (refreshing) return;
    setError(null);
    setRefreshing(true);
    try {
      const response = await getWorkflow(target.workflow_id);
      applyWorkflow(response);
      setMessages((current) => [
        ...current,
        createMessage("system", resultMessage(response)),
      ]);
    } catch (requestError) {
      if (isWorkflowNotFoundError(requestError)) {
        sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
        setTrackedWorkflow(null);
        setWorkflow((current) =>
          current?.workflow_id === target.workflow_id ? null : current,
        );
      }
      setError(getOrchestratorErrorMessage(requestError));
    } finally {
      setRefreshing(false);
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
    setRefreshing(false);
    setError(null);
    sessionStorage.removeItem(ACTIVE_WORKFLOW_KEY);
  };

  return (
    <div className="claim-assistant">
      <header className="assistant-heading">
        <div>
          <p className="eyebrow">Guided intake</p>
          <h1>Claim Assistant</h1>
          <p>
            Describe your motor insurance claim or question. The assistant will
            identify the request and ask for missing intake details when needed.
          </p>
        </div>
        {hasConversation && (
          <button className="button button-secondary" onClick={resetConversation}>
            Start New Request
          </button>
        )}
      </header>

      <div className="assistant-layout">
        <div className="assistant-primary">
          <section className="conversation-card" aria-label="Claim conversation">
          <div className="conversation-scroll" aria-live="polite">
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
                    <p>{message.text}</p>
                    <time dateTime={message.timestamp}>
                      {new Date(message.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                  </article>
                ))}

                {sending && (
                  <div className="assistant-thinking" role="status">
                    <span className="loading-spinner" aria-hidden="true" />
                    Reviewing your message…
                  </div>
                )}
              </div>
            )}
          </div>

          {error && <div className="alert alert-error assistant-error" role="alert">{error}</div>}

          <form className="message-composer" onSubmit={submitMessage}>
            <label htmlFor="claim-message">Your message</label>
            <textarea
              ref={messageInputRef}
              id="claim-message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              minLength={2}
              maxLength={MAX_MESSAGE_LENGTH}
              rows={3}
              placeholder={canClarify ? "Add the missing details…" : "Describe your claim or policy question…"}
              disabled={!canSend}
            />
            <div className="composer-footer">
              <span>{input.length} / {MAX_MESSAGE_LENGTH}</span>
              <span>Enter to send · Shift+Enter for a new line</span>
              <button
                className="button button-primary"
                type="submit"
                disabled={!canSend || input.trim().length < 2}
              >
                {sending ? "Sending…" : canClarify ? "Send Details" : "Send Message"}
              </button>
            </div>
          </form>
          </section>

          {workflow && isOrchestratorResponse(workflow) && (
            <CustomerWorkflowResult
              workflow={workflow}
              refreshing={refreshing}
              onRefresh={() => void refreshWorkflow(workflow)}
            />
          )}

          {separateTrackedWorkflow && (
            <CustomerWorkflowResult
              workflow={separateTrackedWorkflow}
              refreshing={refreshing}
              onRefresh={() => void refreshWorkflow(separateTrackedWorkflow)}
            />
          )}
        </div>

        <aside className="workflow-sidebar" aria-label="Workflow information">
          <section className="workflow-card">
            <p className="eyebrow">Workflow</p>
            <h2>Current status</h2>
            {workflow ? (
              <>
                <WorkflowStatusBadge status={workflow.status} />
                <dl className="workflow-metadata">
                  <div>
                    <dt>Workflow ID</dt>
                    <dd>{workflow.workflow_id}</dd>
                  </div>
                  <div>
                    <dt>Workflow type</dt>
                    <dd>{workflow.workflow_type.replaceAll("_", " ")}</dd>
                  </div>
                  <div>
                    <dt>Clarification</dt>
                    <dd>{workflow.requires_clarification ? "Required" : "Not required"}</dd>
                  </div>
                </dl>
              </>
            ) : (
              <p className="empty-metadata">
                Insurance workflow details will appear when you ask a policy or claim question.
              </p>
            )}
          </section>

          {latestIntake && <IntakeSummary intake={latestIntake} />}

          {activity.length > 0 && (
            <details className="activity-panel">
              <summary>Workflow Activity</summary>
              <ol>
                {activity.map((event, index) => (
                  <li key={`${event.timestamp}-${event.step}-${index}`}>
                    <time dateTime={event.timestamp}>
                      {new Date(event.timestamp).toLocaleString()}
                    </time>
                    <strong>{event.step.replaceAll("_", " ")}</strong>
                    <span>{event.message}</span>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </aside>
      </div>
    </div>
  );
};
