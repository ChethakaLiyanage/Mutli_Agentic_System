import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { createAuthValue, customer, TestAuthProvider } from "../test/testAuth";
import { ProtectedRoute } from "./ProtectedRoute";

const renderRoute = (authValue: ReturnType<typeof createAuthValue>) =>
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <TestAuthProvider value={authValue}>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<p>Private dashboard</p>} />
          </Route>
        </Routes>
      </TestAuthProvider>
    </MemoryRouter>,
  );

describe("ProtectedRoute", () => {
  it("redirects an unauthenticated visitor to login", () => {
    renderRoute(createAuthValue());
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("renders the route for an authenticated user", () => {
    renderRoute(createAuthValue({ user: customer, token: "token" }));
    expect(screen.getByText("Private dashboard")).toBeInTheDocument();
  });

  it("shows a loading state while authentication is restored", () => {
    renderRoute(createAuthValue({ loading: true }));
    expect(screen.getByRole("status")).toHaveTextContent("Loading your account");
  });
});
