import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  clarifyWorkflow,
  getOrchestratorErrorMessage,
  processRequest,
} from "../api/orchestrator";
import type {
  ClarificationResponse,
  IntakeResult,
  OrchestratorResponse,
} from "../types/orchestrator";
import { ClaimAssistantPage } from "./ClaimAssistantPage";

vi.mock("../api/orchestrator", () => ({
  processRequest: vi.fn(),
  clarifyWorkflow: vi.fn(),
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

const completeResponse: OrchestratorResponse = {
  request_id: "REQ-1",
  workflow_id: "WF-COMPLETE",
  status: "intake_complete",
  workflow_type: "claim_submission",
  intake_result: intakeResult,
  retrieval_result: null,
  fraud_result: null,
  human_review_result: null,
  guidance_result: null,
  missing_fields: [],
  requires_clarification: false,
  errors: [],
  audit_trail: [],
};

const clarificationResponse = (
  questions = [
    "What happened to your vehicle?",
    "When did the incident happen?",
    "Where did the incident happen?",
  ],
): ClarificationResponse => ({
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
  questions,
  reason: "Additional claim information is required",
  requires_clarification: true,
  audit_trail: [],
});

const manualResponse: OrchestratorResponse = {
  ...completeResponse,
  workflow_id: "WF-MANUAL",
  status: "manual_assistance_required",
  workflow_type: "clarification",
  intake_result: clarificationResponse().intake_result,
  missing_fields: ["incident_type", "location"],
  requires_clarification: true,
  errors: [
    {
      code: "CLARIFICATION_LIMIT_REACHED",
      message: "Additional information is still required.",
      step: "clarification",
    },
  ],
};

const sendMessage = async (text: string) => {
  const user = userEvent.setup();
  const input = screen.getByRole("textbox", { name: "Your message" });
  await user.clear(input);
  await user.type(input, text);
  await user.click(screen.getByRole("button", { name: /send message|send details/i }));
  return user;
};

describe("ClaimAssistantPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a complete claim, workflow metadata, and structured intake summary", async () => {
    vi.mocked(processRequest).mockResolvedValue(completeResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("A bus hit my car yesterday near Kandy and damaged the left door.");

    expect(await screen.findByText("Intake Complete")).toBeInTheDocument();
    expect(screen.getByText("WF-COMPLETE")).toBeInTheDocument();
    expect(screen.getByText(/Claim Submission \(94% confidence\)/)).toBeInTheDocument();
    expect(screen.getByText("Vehicle Collision")).toBeInTheDocument();
    expect(screen.getByText("Kandy")).toBeInTheDocument();
    expect(screen.getByText("Left Door")).toBeInTheDocument();
    expect(processRequest).toHaveBeenCalledWith({
      request_id: expect.stringMatching(/^REQ-/),
      text: "A bus hit my car yesterday near Kandy and damaged the left door.",
    });
  });

  it("retains an incomplete workflow and sends the reply to the clarification endpoint", async () => {
    vi.mocked(processRequest).mockResolvedValue(clarificationResponse());
    vi.mocked(clarifyWorkflow).mockResolvedValue(completeResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("My car was damaged and I want to claim.");

    expect(await screen.findByText("What happened to your vehicle?")).toBeInTheDocument();
    expect(screen.getByText("WF-CLARIFY")).toBeInTheDocument();

    await sendMessage("A bus hit it yesterday in Kandy.");

    expect(clarifyWorkflow).toHaveBeenCalledWith("WF-CLARIFY", {
      request_id: expect.stringMatching(/^REQ-/),
      text: "A bus hit it yesterday in Kandy.",
    });
    expect(await screen.findByText("Intake Complete")).toBeInTheDocument();
  });

  it("uses the same workflow ID across multiple clarification turns", async () => {
    vi.mocked(processRequest).mockResolvedValue(clarificationResponse());
    vi.mocked(clarifyWorkflow)
      .mockResolvedValueOnce(
        clarificationResponse([
          "What happened to your vehicle?",
          "Where did the incident happen?",
        ]),
      )
      .mockResolvedValueOnce(completeResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("My car was damaged and I want to claim.");
    await screen.findByText("When did the incident happen?");

    await sendMessage("It happened yesterday.");
    await screen.findByText("Where did the incident happen?");

    await sendMessage("A bus hit it in Kandy.");

    expect(clarifyWorkflow).toHaveBeenCalledTimes(2);
    expect(vi.mocked(clarifyWorkflow).mock.calls[0][0]).toBe("WF-CLARIFY");
    expect(vi.mocked(clarifyWorkflow).mock.calls[1][0]).toBe("WF-CLARIFY");
    expect(await screen.findByText("Intake Complete")).toBeInTheDocument();
  });

  it("stops submission and offers reset when manual assistance is required", async () => {
    vi.mocked(processRequest).mockResolvedValue(manualResponse);
    render(<ClaimAssistantPage />);

    await sendMessage("I still need help with my damaged car.");

    expect(await screen.findByText("Manual Assistance Required")).toBeInTheDocument();
    expect(screen.getByText(/contact a claims officer or start a new request/i)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Start New Request" })).toBeInTheDocument();
  });

  it("shows a safe HTTP error without exposing internal details", async () => {
    vi.mocked(processRequest).mockRejectedValue(new Error("private stack detail"));
    render(<ClaimAssistantPage />);

    await sendMessage("I want to make a claim.");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The workflow service is temporarily unavailable. Please try again.",
    );
    expect(screen.queryByText(/private stack detail/i)).not.toBeInTheDocument();
    expect(getOrchestratorErrorMessage).toHaveBeenCalled();
  });

  it("does not fabricate a policy answer for an information request", async () => {
    vi.mocked(processRequest).mockResolvedValue({
      ...completeResponse,
      workflow_id: "WF-POLICY",
      workflow_type: "information_request",
      intake_result: {
        ...intakeResult,
        data: {
          ...intakeResult.data,
          intent: { label: "coverage_question", confidence: 0.91 },
          incident: { ...intakeResult.data.incident, type: "flood_damage" },
        },
      },
    });
    render(<ClaimAssistantPage />);

    await sendMessage("Does my policy cover flood damage?");

    expect(
      await screen.findByText(/Policy retrieval is not yet connected/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/your policy covers/i)).not.toBeInTheDocument();
  });

  it("resets the active workflow without logging out or deleting backend state", async () => {
    vi.mocked(processRequest).mockResolvedValue(clarificationResponse());
    render(<ClaimAssistantPage />);

    const user = await sendMessage("My car was damaged and I want to claim.");
    expect(await screen.findByText("WF-CLARIFY")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Start New Request" }));

    expect(screen.getByText("How can we help?")).toBeInTheDocument();
    expect(screen.queryByText("WF-CLARIFY")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your message" })).toBeEnabled();
  });
});
