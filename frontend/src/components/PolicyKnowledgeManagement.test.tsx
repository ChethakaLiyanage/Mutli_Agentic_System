import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  deletePolicyDocument,
  fetchPolicyDocuments,
  type PolicyDocumentItem,
} from "../api/admin";
import { PolicyKnowledgeManagement } from "./PolicyKnowledgeManagement";

vi.mock("../api/admin", () => ({
  fetchPolicyDocuments: vi.fn(),
  fetchPolicyDocumentDetail: vi.fn(),
  fetchPolicyDocumentVersions: vi.fn(),
  uploadPolicyDocument: vi.fn(),
  replacePolicyDocument: vi.fn(),
  deletePolicyDocument: vi.fn(),
}));

const policyDocument: PolicyDocumentItem = {
  id: "doc-policy-1",
  root_document_id: "doc-policy-1",
  title: "Full Comprehensive Policy",
  document_type: "policy_document",
  policy_type: "full_comprehensive",
  audience: "customer",
  version: "1.0",
  original_filename: "full_comprehensive_policy.txt",
  status: "active",
  chunks_count: 3,
  uploaded_by: "admin@example.com",
  created_at: "2026-09-27T08:00:00.000Z",
  updated_at: "2026-09-27T08:00:00.000Z",
  metadata: {},
};

describe("PolicyKnowledgeManagement delete policy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchPolicyDocuments).mockResolvedValue({
      documents: [policyDocument],
      total: 1,
    });
  });

  it("requires confirmation and allows cancellation", async () => {
    const user = userEvent.setup();
    render(<PolicyKnowledgeManagement />);
    await screen.findByText(policyDocument.title);

    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(screen.getByRole("dialog", { name: "Delete Policy?" })).toBeInTheDocument();
    expect(screen.getByText(/historical records will be preserved/i)).toBeInTheDocument();
    expect(deletePolicyDocument).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog", { name: "Delete Policy?" })).not.toBeInTheDocument();
    expect(deletePolicyDocument).not.toHaveBeenCalled();
  });

  it("removes the policy only after backend confirmation", async () => {
    vi.mocked(deletePolicyDocument).mockResolvedValue({
      success: true,
      message: "Policy document deleted successfully.",
      document: { ...policyDocument, status: "archived" },
      chunks_indexed: 0,
    });
    const user = userEvent.setup();
    render(<PolicyKnowledgeManagement />);
    await screen.findByText(policyDocument.title);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Delete Policy" }));

    await waitFor(() => {
      expect(deletePolicyDocument).toHaveBeenCalledWith(policyDocument.id);
    });
    expect(await screen.findByText("Policy deleted successfully.")).toBeInTheDocument();
    expect(screen.queryByText(policyDocument.title)).not.toBeInTheDocument();
  });

  it("keeps the policy visible when deletion fails", async () => {
    vi.mocked(deletePolicyDocument).mockRejectedValue(
      new Error("Policy archive failed safely."),
    );
    const user = userEvent.setup();
    render(<PolicyKnowledgeManagement />);
    await screen.findByText(policyDocument.title);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Delete Policy" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Policy archive failed safely.",
    );
    expect(screen.getAllByText(policyDocument.title).length).toBeGreaterThan(0);
  });
});
