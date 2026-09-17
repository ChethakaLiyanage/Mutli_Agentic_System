import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import * as authApi from "../api/auth";
import { ACCESS_TOKEN_KEY } from "../api/client";
import { customer } from "../test/testAuth";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./auth-context";

vi.mock("../api/auth");

const AuthProbe = () => {
  const { user, loading, logout } = useAuth();
  return (
    <div>
      <span>{loading ? "loading" : user?.email ?? "anonymous"}</span>
      <button onClick={logout}>Log out</button>
    </div>
  );
};

const renderProvider = () =>
  render(
    <MemoryRouter>
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    </MemoryRouter>,
  );

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("restores the current user when a token exists", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "saved-token");
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(customer);

    renderProvider();

    expect(await screen.findByText(customer.email)).toBeInTheDocument();
    expect(authApi.getCurrentUser).toHaveBeenCalledOnce();
  });

  it("clears an invalid stored session", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "expired-token");
    vi.mocked(authApi.getCurrentUser).mockRejectedValue(new Error("expired"));

    renderProvider();

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it("clears the token and user on logout", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "saved-token");
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(customer);
    const user = userEvent.setup();
    renderProvider();

    await screen.findByText(customer.email);
    await act(async () => user.click(screen.getByRole("button", { name: "Log out" })));

    await waitFor(() => expect(screen.getByText("anonymous")).toBeInTheDocument());
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });
});
