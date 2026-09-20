import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "../api/client";
import { useAuth } from "../context/auth-context";

export const AdminLoginPage = () => {
  const { login } = useAuth();
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
      <section className="auth-intro" aria-labelledby="admin-login-heading">
        <div className="auth-brand">
          <span className="brand-mark brand-mark-large" aria-hidden="true">MI</span>
          <span>Motor Insurance Support</span>
        </div>
        <div>
          <p className="eyebrow">Staff portal</p>
          <h1 id="admin-login-heading">Admin sign in</h1>
          <p className="auth-copy">
            Sign in with an authorized staff account to manage claims and risk reviews.
          </p>
        </div>
      </section>

      <section className="auth-panel" aria-label="Admin sign in form">
        <div className="form-heading">
          <p className="eyebrow">Administrator access</p>
          <h2>Sign in</h2>
          <p>Use your staff email and password.</p>
        </div>

        {error && <div className="alert alert-error" role="alert">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="admin-email">Staff email address</label>
          <input
            id="admin-email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="admin@example.com"
            required
          />

          <label htmlFor="admin-password">Password</label>
          <input
            id="admin-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <button className="button button-primary" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in as admin"}
          </button>
        </form>

        <p className="auth-switch">
          Customer? <Link to="/login">Customer sign in</Link>
        </p>
      </section>
    </main>
  );
};