import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  clarifyWorkflow,
  getOrchestratorErrorMessage,
  getWorkflow,
  isWorkflowNotFoundError,
  processRequest,
  uploadWorkflowDocument,
} from "../api/orchestrator";
import type {
  ClarificationResponse,
  IntakeResult,
  OrchestratorResponse,
  WorkflowStatus,
} from "../types/orchestrator";
import { ACTIVE_WORKFLOW_KEY, ClaimAssistantPage } from "./ClaimAssistantPage";

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
    vi.mocked(isWorkflowNotFoundError).mockReturnValue(false);
    sessionStorage.clear();
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

  it("refreshes an awaiting-review workflow through the owner endpoint", async () => {
    vi.mocked(processRequest).mockResolvedValue(workflowResponse());
    vi.mocked(getWorkflow).mockResolvedValue(workflowResponse({
      status: "approved",
      message: "Your claim has been approved by a claims officer.",
      guidance_result: {
        status: "success",
        response_type: "final_decision_explanation",
        agent: "guidance_agent",
        data: {
          message: "Your claim was approved after human review.",
          next_steps: ["Keep your claim reference for future correspondence."],
          grounded: true,
        },
      },
    }));
    render(<ClaimAssistantPage />);
    const user = await sendMessage("I want to submit my complete claim.");

    await user.click(await screen.findByRole("button", { name: "Check status" }));

    expect(getWorkflow).toHaveBeenCalledWith("WF-CLAIM");
    expect(await screen.findByText("Your claim was approved after human review.")).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: "Check status" })).toBeInTheDocument();
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

  it("restores a workflow that still needs status tracking", async () => {
    sessionStorage.setItem(ACTIVE_WORKFLOW_KEY, "WF-CLAIM");
    vi.mocked(getWorkflow).mockResolvedValue(workflowResponse());

    render(<ClaimAssistantPage />);

    expect(await screen.findByText("Awaiting Human Review")).toBeInTheDocument();
    expect(getWorkflow).toHaveBeenCalledWith("WF-CLAIM");
    expect(screen.getByRole("button", { name: "Check status" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeEnabled();
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
