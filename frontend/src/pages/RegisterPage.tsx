import { Link } from "react-router-dom";

export const RegisterPage = () => {
  return (
    <main className="auth-page">
      <section className="auth-intro" aria-labelledby="register-heading">
        <div className="auth-brand">
          <span className="brand-mark brand-mark-large" aria-hidden="true">MI</span>
          <span>Motor Insurance Support</span>
        </div>
        <div>
          <p className="eyebrow">Customer registration</p>
          <h1 id="register-heading">Create your account</h1>
          <p className="auth-copy">
            Set up secure access to the motor insurance support portal.
          </p>
        </div>
        <div className="security-note">
          <span aria-hidden="true">✓</span>
          Public registration creates a customer account. Staff roles are managed separately.
        </div>
      </section>

      <section className="auth-panel" aria-label="Registration disabled notice">
        <div className="form-heading">
          <p className="eyebrow">Account access notice</p>
          <h2>Registration is Closed</h2>
          <p>Customer self-registration is disabled.</p>
        </div>

        <div className="alert alert-error" role="alert">
          Public account creation has been deactivated. Customer accounts are created and configured with binding motor-policy categories exclusively by authorized insurance administrators.
        </div>

        <div className="mt-4 rounded-lg bg-[#f8fafb] border border-[#e5ecec] p-4 text-xs text-[#4b5563] space-y-2">
          <p className="font-semibold text-[#142b3a]">How do I get an account?</p>
          <p>
            Please contact your insurance representative or claims administrator. They will provision your account credentials and bind your motor insurance policy to your portal profile.
          </p>
        </div>

        <div className="mt-6">
          <Link to="/login" className="button button-primary w-full text-center block">
            Return to Sign In
          </Link>
        </div>

        <p className="auth-switch">
          Staff member? <Link to="/admin-login">Admin sign in</Link>
        </p>
      </section>
    </main>
  );
};
