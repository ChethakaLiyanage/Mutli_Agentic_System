import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";

import {
  clarifyWorkflow,
  getOrchestratorErrorMessage,
  processRequest,
} from "../api/orchestrator";
import { IntakeSummary } from "../components/IntakeSummary";
import { WorkflowStatusBadge } from "../components/WorkflowStatusBadge";
import type { ChatMessage } from "../types/chat";
import {
  isClarificationResponse,
  type WorkflowResponse,
} from "../types/orchestrator";
import "../claim-assistant.css";

const MAX_MESSAGE_LENGTH = 3000;

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
  if (response.status === "awaiting_clarification") {
    return "We need a little more information before the intake can continue.";
  }
  if (response.status === "manual_assistance_required") {
    return "We still need additional information to continue automatically. Please contact a claims officer or start a new request with more detail.";
  }
  if (response.status === "failed") {
    const publicError = "errors" in response ? response.errors[0]?.message : null;
    return publicError || "We could not continue this workflow. You can start a new request and try again.";
  }
  if (response.status === "intake_complete") {
    if (response.workflow_type === "information_request") {
      return "Your question has been understood. Policy retrieval is not yet connected in this prototype.";
    }
    return "Your request has been understood and the intake step is complete. Further processing is not yet connected.";
  }
  return `The workflow is now at: ${response.status.replaceAll("_", " ")}.`;
};

export const ClaimAssistantPage = () => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canClarify = workflow?.status === "awaiting_clarification";
  const canSend = !sending && (!workflowId || canClarify);
  const questions =
    workflow && isClarificationResponse(workflow) ? workflow.questions : [];

  const latestIntake = workflow?.intake_result ?? null;
  const hasConversation = messages.length > 0 || workflow !== null;

  const activity = useMemo(
    () => workflow?.audit_trail ?? [],
    [workflow],
  );

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
      const response = workflowId && canClarify
        ? await clarifyWorkflow(workflowId, request)
        : await processRequest(request);

      setWorkflowId(response.workflow_id);
      setWorkflow(response);
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

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  };

  const resetConversation = () => {
    setInput("");
    setMessages([]);
    setWorkflowId(null);
    setWorkflow(null);
    setSending(false);
    setError(null);
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
        <section className="conversation-card" aria-label="Claim conversation">
          <div className="conversation-scroll" aria-live="polite">
            {!messages.length ? (
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
                  This prototype currently understands requests and gathers intake
                  details. It does not yet decide coverage or process claims.
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

                {questions.length > 0 && canClarify && (
                  <section className="clarification-panel">
                    <h3>We need a little more information:</h3>
                    <ul>
                      {questions.map((question) => <li key={question}>{question}</li>)}
                    </ul>
                  </section>
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

          {error && <div className="alert alert-error assistant-error" role="alert">{error}</div>}

          <form className="message-composer" onSubmit={submitMessage}>
            <label htmlFor="claim-message">Your message</label>
            <textarea
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
              <p className="empty-metadata">A workflow ID will appear after your first message.</p>
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
