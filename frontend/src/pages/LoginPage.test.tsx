import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { createAuthValue, TestAuthProvider } from "../test/testAuth";
import { LoginPage } from "./LoginPage";

const renderPage = (login = vi.fn()) => {
  render(
    <MemoryRouter>
      <TestAuthProvider value={createAuthValue({ login })}>
        <LoginPage />
      </TestAuthProvider>
    </MemoryRouter>,
  );
  return login;
};

describe("LoginPage", () => {
  it("submits valid credentials through the auth context", async () => {
    const login = renderPage();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email address"), "customer@example.com");
    await user.type(screen.getByLabelText("Password"), "securepass123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(login).toHaveBeenCalledWith({
      email: "customer@example.com",
      password: "securepass123",
    });
  });

  it("shows a safe login failure", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Invalid email or password"));
    renderPage(login);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email address"), "customer@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });
});
