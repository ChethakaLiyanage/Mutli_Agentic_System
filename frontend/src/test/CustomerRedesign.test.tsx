import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import * as claimsApi from "../api/claims";
import * as policiesApi from "../api/policies";
import * as orchApi from "../api/orchestrator";
import { AppLayout } from "../components/AppLayout";
import { DocumentUploadModal } from "../components/DocumentUploadModal";
import { ProfilePage } from "../pages/ProfilePage";
import { createAuthValue, customer, TestAuthProvider } from "./testAuth";

vi.mock("../api/auth");
vi.mock("../api/claims");
vi.mock("../api/policies");
vi.mock("../api/orchestrator");

const adminUser = {
  user_id: "ADM-001",
  email: "officer@example.com",
  role: "admin" as const,
  created_at: "2026-09-17T10:00:00Z",
};

describe("Customer Redesign — Layout and Components", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("AppLayout Navbar", () => {
    it("renders 'Motor Insurance Assistant' brand title and profile link for customers", () => {
      render(
        <MemoryRouter initialEntries={["/claim-assistant"]}>
          <TestAuthProvider value={createAuthValue({ user: customer })}>
            <AppLayout />
          </TestAuthProvider>
        </MemoryRouter>,
      );

      expect(screen.getByText("Motor Insurance Assistant")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Your profile" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Dashboard" })).not.toBeInTheDocument();
    });

    it("renders 'Motor Insurance' and Dashboard link for admin users", () => {
      render(
        <MemoryRouter initialEntries={["/admin-dashboard"]}>
          <TestAuthProvider value={createAuthValue({ user: adminUser })}>
            <AppLayout />
          </TestAuthProvider>
        </MemoryRouter>,
      );

      expect(screen.getByText("Motor Insurance")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Your profile" })).not.toBeInTheDocument();
      expect(screen.getByText("admin")).toBeInTheDocument();
    });
  });

  describe("DocumentUploadModal", () => {
    it("renders missing documents and allows document type selection", async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const onUploadComplete = vi.fn();

      render(
        <DocumentUploadModal
          workflowId="WF-123"
          missingDocuments={["police_report", "repair_estimate"]}
          onClose={onClose}
          onUploadComplete={onUploadComplete}
        />,
      );

      expect(screen.getByRole("heading", { name: "Upload Claim Documents" })).toBeInTheDocument();

      const select = screen.getByLabelText("Document Type");
      expect(select).toBeInTheDocument();

      await user.selectOptions(select, "police_report");
      expect(select).toHaveValue("police_report");

      // Close modal via close button
      await user.click(screen.getByRole("button", { name: "Close upload dialog" }));
      expect(onClose).toHaveBeenCalledOnce();
    });

    it("uploads selected file successfully", async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const onUploadComplete = vi.fn();

      vi.mocked(orchApi.uploadWorkflowDocument).mockResolvedValue({
        document_id: "DOC-1",
        claim_id: "CLM-123",
        document_type: "police_report",
        original_filename: "police_report.pdf",
      });

      render(
        <DocumentUploadModal
          workflowId="WF-123"
          missingDocuments={["police_report"]}
          onClose={onClose}
          onUploadComplete={onUploadComplete}
        />,
      );

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = new File(["dummy content"], "police_report.pdf", { type: "application/pdf" });
      await user.upload(fileInput, file);

      expect(screen.getByText(/police_report\.pdf/)).toBeInTheDocument();

      const uploadBtn = screen.getByRole("button", { name: "Upload" });
      await user.click(uploadBtn);

      expect(await screen.findByText(/Successfully uploaded 1 document\(s\)/)).toBeInTheDocument();
      expect(orchApi.uploadWorkflowDocument).toHaveBeenCalledWith("WF-123", file, "police_report");
    });
  });

  describe("ProfilePage", () => {
    it("renders personal details, policies, and claims without password editing", async () => {
      vi.mocked(policiesApi.fetchMyPolicies).mockResolvedValue({
        policies: [
          {
            policy_id: "POL-001",
            policy_number: "POL-2026-001",
            insurance_type: "motor",
            coverage_type: "Comprehensive",
            status: "active",
            start_date: "2026-01-01",
            end_date: "2026-12-31",
            coverage_details: {
              accidental_damage: true,
              theft: true,
            },
            exclusions: ["Racing"],
          },
        ],
        total: 1,
      });

      vi.mocked(claimsApi.fetchMyClaims).mockResolvedValue({
        claims: [
          {
            claim_id: "claim-1",
            policy_id: "POL-001",
            incident_type: "Collision",
            incident_date: "2026-09-15",
            incident_location: "Colombo",
            incident_description: "Front bumper damaged",
            claim_status: "approved",
            claimed_amount: 15000,
            created_at: "2026-09-15T10:00:00Z",
            claim_reference: "CLM-2026-001",
          },
        ],
        total: 1,
      });

      render(
        <MemoryRouter>
          <TestAuthProvider value={createAuthValue({ user: customer })}>
            <ProfilePage />
          </TestAuthProvider>
        </MemoryRouter>,
      );

      // Personal Details
      expect(screen.getByRole("heading", { name: "Profile" })).toBeInTheDocument();
      expect(screen.getByText("Personal Details")).toBeInTheDocument();
      expect(screen.getByText(customer.email)).toBeInTheDocument();
      expect(screen.getByText("customer")).toBeInTheDocument();

      // No password edit controls
      expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /change password|save password/i })).not.toBeInTheDocument();

      // Policies
      expect(await screen.findByText("POL-2026-001")).toBeInTheDocument();
      expect(screen.getByText(/Comprehensive coverage/)).toBeInTheDocument();
      expect(screen.getByText(/Accidental Damage: Included/)).toBeInTheDocument();
      expect(screen.getByText(/Theft: Included/)).toBeInTheDocument();

      // Claims
      expect(await screen.findByText("CLM-2026-001")).toBeInTheDocument();
      expect(screen.getByText("Collision")).toBeInTheDocument();
      expect(screen.getByText("Approved")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "View details →" })).toHaveAttribute(
        "href",
        "/dashboard/claims/claim-1",
      );
    });
  });
});
