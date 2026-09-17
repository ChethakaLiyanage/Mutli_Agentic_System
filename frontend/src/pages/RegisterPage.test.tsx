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
  it("rejects an invalid email before calling the API", async () => {
    const register = renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email address"), "not-an-email");
    await user.type(screen.getByLabelText("Password"), "securepass123");
    await user.type(screen.getByLabelText("Confirm password"), "securepass123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("valid email");
    expect(register).not.toHaveBeenCalled();
  });

  it("rejects short and mismatched passwords", async () => {
    const register = renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email address"), "customer@example.com");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.type(screen.getByLabelText("Confirm password"), "different");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("at least 8 characters");
    expect(register).not.toHaveBeenCalled();
  });

  it("submits a valid customer registration without a role", async () => {
    const register = renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email address"), "customer@example.com");
    await user.type(screen.getByLabelText("Password"), "securepass123");
    await user.type(screen.getByLabelText("Confirm password"), "securepass123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(register).toHaveBeenCalledWith({
      email: "customer@example.com",
      password: "securepass123",
    });
  });
});
