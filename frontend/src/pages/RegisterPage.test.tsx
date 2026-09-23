import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { createAuthValue, TestAuthProvider } from "../test/testAuth";
import { RegisterPage } from "./RegisterPage";

const renderPage = (register = vi.fn()) => {
  render(
    <MemoryRouter>
      <TestAuthProvider value={createAuthValue({ register })}>
        <RegisterPage />
      </TestAuthProvider>
    </MemoryRouter>,
  );
  return register;
};

describe("RegisterPage", () => {
  it("renders the registration closed notice", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Registration is Closed" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Public account creation has been deactivated");
  });

  it("provides a link returning to the sign-in page", () => {
    renderPage();
    const loginLink = screen.getByRole("link", { name: "Return to Sign In" });
    expect(loginLink).toBeInTheDocument();
    expect(loginLink).toHaveAttribute("href", "/login");
  });
});
