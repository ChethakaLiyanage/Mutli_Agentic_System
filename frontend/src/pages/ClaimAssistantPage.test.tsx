import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  clarifyWorkflow,
  getOrchestratorErrorMessage,
  getWorkflow,
  isWorkflowNotFoundError,
  processRequest,
  submitClaim,
} from "../api/orchestrator";
import { useAuth, type AuthContextValue } from "../context/auth-context";
import type { User } from "../types/auth";
import type {
  ClarificationResponse,
  IntakeResult,
  OrchestratorResponse,
  WorkflowStatus,
} from "../types/orchestrator";
import { ACTIVE_WORKFLOW_KEY, ClaimAssistantPage } from "./ClaimAssistantPage";
import { chatHistoryStorageKey } from "../utils/chatHistoryStorage";

vi.mock("../context/auth-context", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../api/orchestrator", () => ({
  processRequest: vi.fn(),
  clarifyWorkflow: vi.fn(),
  getWorkflow: vi.fn(),
  uploadWorkflowDocument: vi.fn(),
  submitClaim: vi.fn(),
  isWorkflowNotFoundError: vi.fn(() => false),
  getOrchestratorErrorMessage: vi.fn(
    () => "The workflow service is temporarily unavailable. Please try again.",
  ),
}));

const customerUser = (userId: string): User => ({
  user_id: userId,
  email: `${userId.toLowerCase()}@example.com`,
  role: "customer",
  created_at: "2026-09-17T10:00:00Z",
});

const authValue = (userId: string): AuthContextValue => ({
  user: customerUser(userId),
  token: "test-token",
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshCurrentUser: vi.fn(),
});

const intakeResult: IntakeResult = {
  request_id: "REQ-1",
  agent: "claim_intake",
  status: "success",
  data: {
    intent: { label: "claim_submission", confidence: 0.94 },
    insurance_type: "motor",
    incident: {
      type: "vehicle_collision",
      date_text: "yesterday",
      normalized_date: "2026-09-16",
      location: "Kandy",
    },
    damage: { areas: ["left door"], description: null },
    entities: [],
    missing_fields: [],
    requires_clarification: false,
  },
  errors: [],
};

const workflowResponse = (
  overrides: Partial<OrchestratorResponse> = {},
): OrchestratorResponse => ({
  request_id: "REQ-1",
  workflow_id: "WF-CLAIM",
  status: "awaiting_human_review",
  workflow_type: "claim_submission",
  intake_result: intakeResult,
  retrieval_status: "success",
  warnings: [],
  evidence_summary: [],
  message: "Your claim is awaiting review by a claims officer.",
  guidance_result: null,
  missing_fields: [],
  requires_clarification: false,
  errors: [],
  audit_trail: [],
  ...overrides,
});

const completedInformationResponse = workflowResponse({
  workflow_id: "WF-POLICY",
  status: "completed",
  workflow_type: "information_request",
  intake_result: {
    ...intakeResult,
    data: {
      ...intakeResult.data,
      intent: { label: "coverage_question", confidence: 0.91 },
      incident: { ...intakeResult.data.incident, type: "flood_damage" },
    },
  },
  message: "Grounded policy guidance is ready.",
  warnings: ["The available information may not confirm your specific policy."],
  evidence_summary: [
    {
      evidence_id: "EVID-1",
      source_title: "Motor Policy Manual",
      section: "Flood Cover",
      content: "Flood claims are assessed against the insured policy terms.",
      score: 0.88,
    },
  ],
  guidance_result: {
    status: "success",
    response_type: "coverage_explanation",
    agent: "guidance_agent",
    data: {
      message: "The available policy evidence describes how flood claims are assessed.",
      next_steps: ["Check the cover listed on your policy schedule."],
      evidence_used: ["EVID-1"],
      insufficient_evidence: false,
      grounded: true,
    },
    warnings: [],
    created_at: "2026-09-18T09:00:00Z",
  },
});

const greetingResponse = workflowResponse({
  request_id: "REQ-GREETING",
  workflow_id: "WF-GREETING",
  status: "completed",
  workflow_type: "unknown",
  intake_result: {
    ...intakeResult,
    request_id: "REQ-GREETING",
    data: {
      ...intakeResult.data,
      intent: { label: "greeting", confidence: 0.98 },
      missing_fields: [],
      requires_clarification: false,
    },
  },
  retrieval_status: null,
  message: "Hi! I can help with claims, policy questions, coverage, required documents, or claim status. What can I help you with?",
  guidance_result: {
    status: "success",
    response_type: "greeting",
    agent: "guidance_agent",
    data: {
      message: "Hi! I can help with claims, policy questions, coverage, required documents, or claim status. What can I help you with?",
      grounded: true,
    },
  },
});

const clarificationResponse = (): ClarificationResponse => ({
  request_id: "REQ-1",
  workflow_id: "WF-CLARIFY",
  status: "awaiting_clarification",
  workflow_type: "clarification",
  intake_result: {
    ...intakeResult,
    data: {
      ...intakeResult.data,
      incident: {
        type: null,
        date_text: null,
        normalized_date: null,
        location: null,
      },
      missing_fields: ["incident_type", "incident_date", "location"],
      requires_clarification: true,
    },
  },
  missing_fields: ["incident_type", "incident_date", "location"],
  questions: ["I need a few more details: What happened to your vehicle? When did the incident happen? Where did it happen?"],
  reason: "I need a few more details: What happened to your vehicle? When did the incident happen? Where did it happen?",
  message: "I need a few more details: What happened to your vehicle? When did the incident happen? Where did it happen?",
  guidance_result: {
    status: "success",
    response_type: "clarification_question",
    agent: "guidance_agent",
    data: {
      message: "I need a few more details: What happened to your vehicle? When did the incident happen? Where did it happen?",
      grounded: true,
    },
  },
  requires_clarification: true,
  audit_trail: [],
});

const sendMessage = async (text: string) => {
  const user = userEvent.setup();
  const input = screen.getByRole("textbox", { name: "Your message" });
  await user.clear(input);
  await user.type(input, text);
  await user.click(screen.getByRole("button", { name: "Send message" }));
  return user;
};

describe("ClaimAssistantPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue(authValue("CUSTOMER-A"));
    vi.mocked(isWorkflowNotFoundError).mockReturnValue(false);
    localStorage.clear();
    sessionStorage.clear();
    window.history.replaceState({}, "", "/claim-assistant");
  });

  it("preserves claim intake details and stores an awaiting-review workflow in clean chat", async () => {
    vi.mocked(processRequest).mockResolvedValue(workflowResponse());
    render(<ClaimAssistantPage />);

    await sendMessage("A bus hit my car yesterday near Kandy and damaged the left door.");

    expect(await screen.findByText("Awaiting Human Review")).toBeInTheDocument();
    expect(screen.getByText("Your claim is awaiting review by a claims officer.")).toBeInTheDocument();
    expect(screen.getByText("Your claim is assigned to a claims officer.")).toBeInTheDocument();
    expect(sessionStorage.getItem(ACTIVE_WORKFLOW_KEY)).toBe("WF-CLAIM");
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeEnabled();
  });

  it("opens document upload modal when workflow requires documents", async () => {
    const awaitingDocsWf = workflowResponse({
      status: "awaiting_documents",
      workflow_type: "claim_submission",
      claim_id: "CLM-123",
      missing_required_documents: ["repair_estimate", "police_report"],
      message: "Please upload the required documents to proceed with your claim.",
    });
    vi.mocked(processRequest).mockResolvedValue(awaitingDocsWf);
    render(<ClaimAssistantPage />);

    const user = await sendMessage("I want to submit documents for my claim.");

    expect(await screen.findByTestId("upload-documents-btn")).toBeInTheDocument();
    expect(screen.getByText(/Missing documents:/)).toBeInTheDocument();
    expect(screen.getByText(/repair estimate, police report/)).toBeInTheDocument();

    await user.click(screen.getByTestId("upload-documents-btn"));

    expect(screen.getByRole("heading", { name: "Upload Claim Documents" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close upload dialog" })).toBeInTheDocument();
  });

  it("keeps chat active after a greeting and starts insurance as a new workflow", async () => {
    vi.mocked(processRequest)
      .mockResolvedValueOnce(greetingResponse)
      .mockResolvedValueOnce(completedInformationResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("hi");

    expect(await screen.findByText(/Hi! I can help/i)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeEnabled();
    expect(sessionStorage.getItem(ACTIVE_WORKFLOW_KEY)).toBeNull();

    await sendMessage("Does my policy cover flood damage?");

    expect(processRequest).toHaveBeenCalledTimes(2);
    expect(clarifyWorkflow).not.toHaveBeenCalled();
    expect(await screen.findByText("The available policy evidence describes how flood claims are assessed.")).toBeInTheDocument();
    expect(screen.getByText("hi")).toBeInTheDocument();
    expect(screen.getByText("Does my policy cover flood damage?")).toBeInTheDocument();
  });

  it("starts another workflow after a completed information question", async () => {
    const documentsResponse = workflowResponse({
      ...completedInformationResponse,
      request_id: "REQ-DOCUMENTS",
      workflow_id: "WF-DOCUMENTS",
      message: "The available guide lists the required theft documents.",
      guidance_result: {
        ...completedInformationResponse.guidance_result!,
        response_type: "required_documents",
        data: {
          message: "The available guide lists the required theft documents.",
          grounded: true,
        },
      },
    });
    vi.mocked(processRequest)
      .mockResolvedValueOnce(completedInformationResponse)
      .mockResolvedValueOnce(documentsResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("Does my policy cover flood damage?");
    await screen.findByText("The available policy evidence describes how flood claims are assessed.");
    await sendMessage("What documents are required for theft?");

    expect(processRequest).toHaveBeenCalledTimes(2);
    expect(clarifyWorkflow).not.toHaveBeenCalled();
    expect(await screen.findByText("The available guide lists the required theft documents.")).toBeInTheDocument();
    expect(screen.getByText("Does my policy cover flood damage?")).toBeInTheDocument();
    expect(screen.getByText("What documents are required for theft?")).toBeInTheDocument();
  });

  it("continues clarification through the same workflow", async () => {
    vi.mocked(processRequest).mockResolvedValue(clarificationResponse());
    vi.mocked(clarifyWorkflow).mockResolvedValue(workflowResponse());
    render(<ClaimAssistantPage />);

    await sendMessage("My car was damaged and I want to claim.");
    expect(
      await screen.findAllByText(/I need a few more details: What happened/),
    ).toHaveLength(1);

    await sendMessage("A bus hit it yesterday in Kandy.");
    expect(clarifyWorkflow).toHaveBeenCalledWith("WF-CLARIFY", {
      request_id: expect.stringMatching(/^REQ-/),
      text: "A bus hit it yesterday in Kandy.",
    });
    expect(await screen.findByText("Awaiting Human Review")).toBeInTheDocument();
  });

  it("preserves the manual-assistance terminal state", async () => {
    vi.mocked(processRequest).mockResolvedValue(workflowResponse({
      workflow_id: "WF-MANUAL",
      status: "manual_assistance_required",
      workflow_type: "clarification",
      intake_result: clarificationResponse().intake_result,
      missing_fields: ["incident_type", "location"],
      requires_clarification: true,
      message: "A claims officer needs to help with the next step of your claim.",
      guidance_result: {
        status: "success",
        response_type: "claim_progress",
        agent: "guidance_agent",
        data: {
          message: "A claims officer needs to help with the next step of your claim.",
          grounded: true,
        },
      },
      errors: [
        {
          code: "CLARIFICATION_LIMIT_REACHED",
          message: "Additional information is still required.",
          step: "clarification",
        },
      ],
    }));
    render(<ClaimAssistantPage />);

    await sendMessage("I still need help with my damaged car.");

    expect(await screen.findByText(/claims officer needs to help/i)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeEnabled();
  });

  it("renders completed grounded guidance directly in chat", async () => {
    vi.mocked(processRequest).mockResolvedValue(completedInformationResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("Does my policy cover flood damage?");

    expect(await screen.findByText("The available policy evidence describes how flood claims are assessed.")).toBeInTheDocument();
  });

  it("sends the owned claim workflow as context for a natural coverage follow-up", async () => {
    const claimDetailResponse = workflowResponse({
      workflow_id: "WF-CLAIM-DETAIL",
      claim_id: "CLM-OWN-TEST",
      status: "completed",
      workflow_type: "claim_status",
      message: "Claim CLM-OWN-TEST records windscreen damage.",
      guidance_result: {
        status: "success",
        response_type: "claim_information",
        agent: "guidance_agent",
        data: {
          message: "Claim CLM-OWN-TEST records windscreen damage.",
          grounded: true,
        },
      },
    });
    vi.mocked(processRequest)
      .mockResolvedValueOnce(claimDetailResponse)
      .mockResolvedValueOnce(completedInformationResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("Show me claim CLM-OWN-TEST");
    await screen.findByText("Claim CLM-OWN-TEST records windscreen damage.");
    await sendMessage("Is that damage covered by my policy?");

    expect(processRequest).toHaveBeenLastCalledWith({
      request_id: expect.stringMatching(/^REQ-/),
      text: "Is that damage covered by my policy?",
      context_workflow_id: "WF-CLAIM-DETAIL",
    });
  });

  it("shows a safe insufficient-evidence response without inventing an answer", async () => {
    vi.mocked(processRequest).mockResolvedValue(workflowResponse({
      ...completedInformationResponse,
      guidance_result: {
        ...completedInformationResponse.guidance_result!,
        status: "insufficient_evidence",
        data: {
          message: "We couldn't find enough policy information to answer this reliably.",
          insufficient_evidence: true,
          grounded: false,
        },
      },
      evidence_summary: [],
    }));
    render(<ClaimAssistantPage />);

    await sendMessage("Is this unusual modification covered?");

    expect(await screen.findByText("We couldn't find enough policy information to answer this reliably.")).toBeInTheDocument();
    expect(screen.queryByText(/your policy covers/i)).not.toBeInTheDocument();
  });

  it("shows the current workflow status without an in-chat status button", async () => {
    vi.mocked(processRequest).mockResolvedValue(workflowResponse());
    render(<ClaimAssistantPage />);
    await sendMessage("I want to submit my complete claim.");

    expect(await screen.findByText("Awaiting Human Review")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check status/i })).not.toBeInTheDocument();
  });

  it("renders the fresh backend submission guidance instead of document instructions", async () => {
    vi.mocked(processRequest).mockResolvedValue(workflowResponse({
      status: "awaiting_documents",
      message: "Please upload the required documents.",
      guidance_result: {
        status: "success",
        response_type: "claim_document_requirements",
        agent: "guidance_agent",
        data: { message: "Please upload the required documents." },
      },
    }));
    vi.mocked(submitClaim).mockResolvedValue(workflowResponse({
      status: "awaiting_assignment",
      message: "Your claim has been submitted successfully and is waiting to be assigned.",
      guidance_result: {
        status: "success",
        response_type: "claim_progress",
        agent: "guidance_agent",
        data: {
          message: "Your claim has been submitted successfully and is waiting to be assigned.",
        },
      },
    }));
    render(<ClaimAssistantPage />);
    const user = await sendMessage("My car was stolen yesterday in Kandy.");

    await user.click(await screen.findByRole("button", { name: "Submit Claim" }));

    expect(submitClaim).toHaveBeenCalledWith("WF-CLAIM");
    expect(await screen.findByText(/Current claim status/)).toBeInTheDocument();
    expect(screen.getByText(/check your claim status through your profile, or simply ask me here in chat/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check status/i })).not.toBeInTheDocument();
  });

  it("keeps a pending claim trackable while a new policy workflow runs", async () => {
    vi.mocked(processRequest)
      .mockResolvedValueOnce(workflowResponse())
      .mockResolvedValueOnce(completedInformationResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("I want to submit my complete claim.");
    await screen.findByText("Awaiting Human Review");
    await sendMessage("Does my policy cover flood damage?");

    expect(processRequest).toHaveBeenCalledTimes(2);
    expect(clarifyWorkflow).not.toHaveBeenCalled();
    expect(await screen.findByText("The available policy evidence describes how flood claims are assessed.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check status/i })).not.toBeInTheDocument();
    expect(sessionStorage.getItem(ACTIVE_WORKFLOW_KEY)).toBe("WF-CLAIM");
  });

  it.each([
    ["approved"],
    ["rejected"],
    ["more_information_required"],
    ["escalated"],
  ] satisfies Array<[WorkflowStatus]>) (
    "renders the %s customer outcome in chat",
    async (status) => {
      vi.mocked(processRequest).mockResolvedValue(workflowResponse({
        status,
        message: `Customer-safe ${status} explanation.`,
        guidance_result: {
          event_id: `human-decision:DEC-${status}`,
          status: "success",
          response_type: "final_decision_explanation",
          agent: "guidance_agent",
          data: { message: `Customer-safe ${status} explanation.` },
        },
      }));
      render(<ClaimAssistantPage />);

      await sendMessage("Please show the latest result for my claim.");

      expect(await screen.findByText(`Customer-safe ${status} explanation.`)).toBeInTheDocument();
    },
  );

  it("appends a new decision to preserved history and keeps one copy after remount", async () => {
    const storageKey = chatHistoryStorageKey("CUSTOMER-A");
    localStorage.setItem(storageKey, JSON.stringify([
      {
        id: "MSG-EXISTING",
        sender: "system",
        text: "Your claim is awaiting review by a claims officer.",
        timestamp: "2026-09-27T08:00:00.000Z",
      },
    ]));
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-CLAIM");
    const decisionResponse = workflowResponse({
      status: "rejected",
      message: "Your claim was rejected. Reason: Required evidence did not match.",
      guidance_result: {
        event_id: "human-decision:DEC-REJECT-1",
        status: "success",
        response_type: "final_decision_explanation",
        agent: "guidance_agent",
        data: {
          message: "Your claim was rejected. Reason: Required evidence did not match.",
        },
      },
    });
    vi.mocked(getWorkflow).mockResolvedValue(decisionResponse);

    const view = render(<ClaimAssistantPage />);

    expect(await screen.findByText(decisionResponse.message!)).toBeInTheDocument();
    expect(screen.getAllByText(decisionResponse.message!)).toHaveLength(1);
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(storageKey) || "[]");
      expect(stored.at(-1).eventId).toBe("human-decision:DEC-REJECT-1");
    });

    view.unmount();
    render(<ClaimAssistantPage />);
    expect(screen.getAllByText(decisionResponse.message!)).toHaveLength(1);
    expect(getWorkflow).toHaveBeenCalledOnce();
  });

  it("deduplicates repeated status responses for the same human decision", async () => {
    const decisionResponse = workflowResponse({
      status: "approved",
      message: "Your claim has been approved by a claims officer.",
      guidance_result: {
        event_id: "human-decision:DEC-APPROVE-1",
        status: "success",
        response_type: "final_decision_explanation",
        agent: "guidance_agent",
        data: { message: "Your claim has been approved by a claims officer." },
      },
    });
    vi.mocked(processRequest).mockResolvedValue(decisionResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("What is my claim status?");
    await screen.findByText(decisionResponse.message!);
    await sendMessage("What is my claim status now?");

    expect(screen.getAllByText(decisionResponse.message!)).toHaveLength(1);
    expect(processRequest).toHaveBeenCalledTimes(2);
  });

  it("polls an active review and appends the resulting decision only once", async () => {
    vi.useFakeTimers();
    try {
      sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-CLAIM");
      const awaitingReview = workflowResponse();
      const decisionResponse = workflowResponse({
        status: "more_information_required",
        message: "Additional information is required: provide a clearer photograph.",
        guidance_result: {
          event_id: "human-decision:DEC-INFO-1",
          status: "success",
          response_type: "final_decision_explanation",
          agent: "guidance_agent",
          data: {
            message: "Additional information is required: provide a clearer photograph.",
          },
        },
      });
      vi.mocked(getWorkflow)
        .mockResolvedValueOnce(awaitingReview)
        .mockResolvedValue(decisionResponse);
      render(<ClaimAssistantPage />);
      await act(async () => {
        await Promise.resolve();
      });
      expect(getWorkflow).toHaveBeenCalledOnce();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(15_000);
      });

      expect(screen.getAllByText(decisionResponse.message!)).toHaveLength(1);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(45_000);
      });
      expect(screen.getAllByText(decisionResponse.message!)).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("restores a workflow that still needs status tracking", async () => {
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-CLAIM");
    vi.mocked(getWorkflow).mockResolvedValue(workflowResponse());

    render(<ClaimAssistantPage />);

    expect(await screen.findByText("Awaiting Human Review")).toBeInTheDocument();
    expect(getWorkflow).toHaveBeenCalledWith("WF-CLAIM");
    expect(screen.queryByRole("button", { name: /check status/i })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeEnabled();
  });

  it("resumes a missing-document workflow from a notification link", async () => {
    const awaitingDocsWf = workflowResponse({
      status: "awaiting_documents",
      claim_id: "CLM-123",
      missing_required_documents: ["police_report"],
      message: "Please upload the required documents to proceed with your claim.",
    });
    window.history.replaceState(
      {},
      "",
      "/claim-assistant?workflowId=WF-CLAIM&action=upload-documents",
    );
    vi.mocked(getWorkflow).mockResolvedValue(awaitingDocsWf);

    render(<ClaimAssistantPage />);

    expect(await screen.findByRole("heading", { name: "Upload Claim Documents" })).toBeInTheDocument();
    expect(getWorkflow).toHaveBeenCalledWith("WF-CLAIM");
    expect(sessionStorage.getItem(ACTIVE_WORKFLOW_KEY)).toBe("WF-CLAIM");
  });

  it("clears an unavailable restored workflow and returns to the empty assistant", async () => {
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-MISSING");
    vi.mocked(getWorkflow).mockRejectedValue(new Error("not found"));
    vi.mocked(isWorkflowNotFoundError).mockReturnValue(true);

    render(<ClaimAssistantPage />);

    expect(await screen.findByText("How can we help?")).toBeInTheDocument();
    expect(sessionStorage.getItem(ACTIVE_WORKFLOW_KEY)).toBeNull();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("new chat clears only the active workflow state", async () => {
    vi.mocked(processRequest).mockResolvedValue(clarificationResponse());
    render(<ClaimAssistantPage />);

    const user = await sendMessage("My car was damaged and I want to claim.");
    expect(await screen.findByText(/I need a few more details/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "New Chat" }));

    expect(sessionStorage.getItem(ACTIVE_WORKFLOW_KEY)).toBeNull();
    expect(screen.getByText("How can we help?")).toBeInTheDocument();
  });

  it("restores the same visible messages after remount without replaying them", async () => {
    vi.mocked(processRequest).mockResolvedValue(completedInformationResponse);
    const view = render(<ClaimAssistantPage />);

    await sendMessage("What is my coverage?");
    await screen.findByText(
      "The available policy evidence describes how flood claims are assessed.",
    );
    await waitFor(() => {
      const stored = localStorage.getItem(chatHistoryStorageKey("CUSTOMER-A"));
      expect(stored).toContain("What is my coverage?");
    });
    expect(processRequest).toHaveBeenCalledOnce();

    view.unmount();
    render(<ClaimAssistantPage />);

    expect(screen.getByText("What is my coverage?")).toBeInTheDocument();
    expect(screen.getByText(
      "The available policy evidence describes how flood claims are assessed.",
    )).toBeInTheDocument();
    expect(processRequest).toHaveBeenCalledOnce();
    expect(getWorkflow).not.toHaveBeenCalled();
  });

  it("does not replace preserved history during independent workflow restoration", async () => {
    localStorage.setItem(chatHistoryStorageKey("CUSTOMER-A"), JSON.stringify([
      {
        id: "MSG-PRESERVED",
        sender: "user",
        text: "My preserved question",
        timestamp: "2026-09-27T08:00:00.000Z",
      },
      {
        id: "MSG-PRESERVED-REPLY",
        sender: "system",
        text: "My preserved answer",
        timestamp: "2026-09-27T08:00:01.000Z",
      },
    ]));
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-CLAIM");
    vi.mocked(getWorkflow).mockResolvedValue(workflowResponse());

    render(<ClaimAssistantPage />);

    expect(screen.getByText("My preserved question")).toBeInTheDocument();
    expect(screen.getByText("My preserved answer")).toBeInTheDocument();
    await waitFor(() => expect(getWorkflow).toHaveBeenCalledWith("WF-CLAIM"));
    expect(screen.queryByText(
      "Your claim is awaiting review by a claims officer.",
    )).not.toBeInTheDocument();
  });

  it("appends new messages after restoring a preserved conversation", async () => {
    const storageKey = chatHistoryStorageKey("CUSTOMER-A");
    localStorage.setItem(storageKey, JSON.stringify([
      {
        id: "MSG-OLD-USER",
        sender: "user",
        text: "Hello",
        timestamp: "2026-09-27T08:00:00.000Z",
      },
      {
        id: "MSG-OLD-SYSTEM",
        sender: "system",
        text: "Hello. How can I help?",
        timestamp: "2026-09-27T08:00:01.000Z",
      },
    ]));
    vi.mocked(processRequest).mockResolvedValue(completedInformationResponse);
    render(<ClaimAssistantPage />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    await sendMessage("What is my coverage?");
    await screen.findByText(
      "The available policy evidence describes how flood claims are assessed.",
    );

    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(storageKey) || "[]");
      expect(stored.map((message: { text: string }) => message.text)).toEqual([
        "Hello",
        "Hello. How can I help?",
        "What is my coverage?",
        "The available policy evidence describes how flood claims are assessed.",
      ]);
    });
  });

  it("New Chat removes only the current customer's preserved history", async () => {
    const storageKey = chatHistoryStorageKey("CUSTOMER-A");
    vi.mocked(processRequest).mockResolvedValue(completedInformationResponse);
    const view = render(<ClaimAssistantPage />);
    const user = await sendMessage("What is my coverage?");
    await waitFor(() => expect(localStorage.getItem(storageKey)).not.toBeNull());

    await user.click(screen.getByRole("button", { name: "New Chat" }));

    expect(localStorage.getItem(storageKey)).toBeNull();
    expect(screen.getByText("How can we help?")).toBeInTheDocument();
    view.unmount();
    render(<ClaimAssistantPage />);
    expect(screen.queryByText("What is my coverage?")).not.toBeInTheDocument();
  });

  it("isolates preserved chat history by authenticated customer", async () => {
    vi.mocked(processRequest).mockResolvedValue(completedInformationResponse);
    const customerAView = render(<ClaimAssistantPage />);
    await sendMessage("Customer A question");
    await screen.findByText(
      "The available policy evidence describes how flood claims are assessed.",
    );
    await waitFor(() => {
      expect(localStorage.getItem(chatHistoryStorageKey("CUSTOMER-A"))).not.toBeNull();
    });
    customerAView.unmount();

    vi.mocked(useAuth).mockReturnValue(authValue("CUSTOMER-B"));
    const customerBView = render(<ClaimAssistantPage />);
    expect(screen.queryByText("Customer A question")).not.toBeInTheDocument();
    expect(screen.getByText("How can we help?")).toBeInTheDocument();
    await sendMessage("Customer B question");
    await waitFor(() => {
      expect(localStorage.getItem(chatHistoryStorageKey("CUSTOMER-B"))).toContain(
        "Customer B question",
      );
    });
    customerBView.unmount();

    vi.mocked(useAuth).mockReturnValue(authValue("CUSTOMER-A"));
    render(<ClaimAssistantPage />);
    expect(screen.getByText("Customer A question")).toBeInTheDocument();
    expect(screen.queryByText("Customer B question")).not.toBeInTheDocument();
  });

  it("ignores malformed stored chat history without crashing", () => {
    localStorage.setItem(chatHistoryStorageKey("CUSTOMER-A"), "not-json");

    render(<ClaimAssistantPage />);

    expect(screen.getByText("How can we help?")).toBeInTheDocument();
    expect(processRequest).not.toHaveBeenCalled();
    expect(getWorkflow).not.toHaveBeenCalled();
  });

  it("never renders fraud or reviewer internals from a malformed response", async () => {
    const malformedResponse = {
      ...workflowResponse(),
      fraud_result: { anomaly_score: 0.99, indicators: ["SECRET_RISK_FLAG"] },
      fraud_risk_level: "high",
      recommended_next_action: "investigate customer",
      human_review_result: {
        reviewer_id: "REVIEWER-SECRET",
        notes: "INTERNAL_REVIEW_NOTE",
      },
    } as OrchestratorResponse;
    vi.mocked(processRequest).mockResolvedValue(malformedResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("I want to submit my claim.");
    await screen.findByText("Awaiting Human Review");

    expect(screen.queryByText(/SECRET_RISK_FLAG/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/REVIEWER-SECRET/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/INTERNAL_REVIEW_NOTE/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/0\.99/)).not.toBeInTheDocument();
  });

  it("shows a safe network error without exposing internal details", async () => {
    vi.mocked(processRequest).mockRejectedValue(new Error("private stack detail"));
    render(<ClaimAssistantPage />);

    await sendMessage("I want to make a claim.");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The workflow service is temporarily unavailable. Please try again.",
    );
    expect(screen.queryByText(/private stack detail/i)).not.toBeInTheDocument();
    expect(getOrchestratorErrorMessage).toHaveBeenCalled();
  });

  it("prevents duplicate input while workflow restoration is in progress", async () => {
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-POLICY");
    vi.mocked(getWorkflow).mockReturnValue(new Promise(() => undefined));
    render(<ClaimAssistantPage />);

    expect(await screen.findByText("Restoring your workflow…")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeDisabled();
    await waitFor(() => expect(getWorkflow).toHaveBeenCalledOnce());
  });
});
