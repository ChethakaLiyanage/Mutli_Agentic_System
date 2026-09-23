import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import { useAuth } from "../context/auth-context";

type LoginLocationState = {
  registrationComplete?: boolean;
};

export const LoginPage = () => {
  const { login } = useAuth();
  const location = useLocation();
  const state = location.state as LoginLocationState | null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login({ email, password });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "Unable to sign in."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-intro" aria-labelledby="login-heading">
        <div className="auth-brand">
          <span className="brand-mark brand-mark-large" aria-hidden="true">MI</span>
          <span>Motor Insurance Support</span>
        </div>
        <div>
          <p className="eyebrow">Customer portal</p>
          <h1 id="login-heading">Welcome back</h1>
          <p className="auth-copy">
            Sign in to access your secure claims and policy support dashboard.
          </p>
        </div>
        <div className="security-note">
          <span aria-hidden="true">✓</span>
          Your account details are sent securely to the insurance service.
        </div>
      </section>

      <section className="auth-panel" aria-label="Sign in form">
        <div className="form-heading">
          <p className="eyebrow">Account access</p>
          <h2>Sign in</h2>
          <p>Enter the email and password registered with your account.</p>
        </div>

        {state?.registrationComplete && (
          <div className="alert alert-success" role="status">
            Account created successfully. You can now sign in.
          </div>
        )}
        {error && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="customer@example.com"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <button className="button button-primary" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="auth-switch text-xs text-[#788990]">
          Customer accounts are provisioned by your insurance administrator. If you do not have credentials, please contact support.
        </p>
        <p className="auth-switch">
          Staff member? <Link to="/admin-login">Admin sign in</Link>
        </p>
      </section>
    </main>
  );
};
