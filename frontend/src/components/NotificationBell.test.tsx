import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { fetchNotifications, markNotificationRead } from "../api/notifications";
import { NotificationBell } from "./NotificationBell";

const navigate = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigate };
});

vi.mock("../api/notifications", () => ({
  fetchNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}));

describe("NotificationBell decision navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(markNotificationRead).mockResolvedValue({
      id: "NOTIF-1",
      user_id: "CUSTOMER-A",
      workflow_id: "WF-DECISION",
      claim_id: "CLM-1",
      notification_type: "claim_rejected",
      title: "Claim Rejected",
      message: "Your claim review is complete.",
      is_read: true,
    });
  });

  it.each([
    "claim_approved",
    "claim_rejected",
    "more_information_required",
    "claim_escalated",
  ])("opens Claim Assistant for a %s decision", async (notificationType) => {
    vi.mocked(fetchNotifications).mockResolvedValue({
      unread_count: 1,
      notifications: [{
        id: "NOTIF-1",
        user_id: "CUSTOMER-A",
        workflow_id: "WF-DECISION",
        claim_id: "CLM-1",
        notification_type: notificationType,
        title: "Claim decision updated",
        message: "Open Claim Assistant for details.",
        is_read: false,
      }],
    });
    const user = userEvent.setup();
    const view = render(<NotificationBell />);

    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(await screen.findByText("Claim decision updated"));

    expect(markNotificationRead).toHaveBeenCalledWith("NOTIF-1");
    expect(navigate).toHaveBeenCalledWith(
      "/claim-assistant?workflowId=WF-DECISION",
    );
    view.unmount();
  });
});
