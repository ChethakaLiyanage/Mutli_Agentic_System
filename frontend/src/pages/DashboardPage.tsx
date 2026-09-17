import { Link } from "react-router-dom";

import { useAuth } from "../context/auth-context";

const modules = [
  {
    name: "Claim Assistant",
    description: "Start and continue guided motor claim conversations.",
    accent: "blue",
    href: "/claim-assistant",
  },
  {
    name: "My Claims",
    description: "Review submitted claims and their current progress.",
    accent: "indigo",
    href: null,
  },
  {
    name: "Policy Support",
    description: "Ask questions about motor policy information and coverage.",
    accent: "cyan",
    href: null,
  },
  {
    name: "Profile",
    description: "View and manage your customer account information.",
    accent: "slate",
    href: null,
  },
] as const;

export const DashboardPage = () => {
  const { user } = useAuth();

  return (
    <div className="dashboard">
      <section className="dashboard-welcome">
        <div>
          <p className="eyebrow">Customer dashboard</p>
          <h1>Welcome, {user?.email}</h1>
          <p>
            Your account is ready. Claims and policy tools will become available in the next development step.
          </p>
        </div>
        <div className="account-summary">
          <span>Account role</span>
          <strong>{user?.role.replace("_", " ")}</strong>
          <span className="account-status"><i aria-hidden="true" /> Authenticated</span>
        </div>
      </section>

      <section aria-labelledby="services-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Portal services</p>
            <h2 id="services-heading">What you’ll be able to do</h2>
          </div>
          <span className="development-label">Foundation preview</span>
        </div>

        <div className="module-grid">
          {modules.map((module, index) => {
            const content = (
              <>
              <span className={`module-number module-number-${module.accent}`}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3>{module.name}</h3>
              <p>{module.description}</p>
              <span className={module.href ? "module-action" : "coming-soon"}>
                {module.href ? "Open assistant" : "Coming soon"}
              </span>
              </>
            );

            return module.href ? (
              <Link className="module-card module-card-link" to={module.href} key={module.name}>
                {content}
              </Link>
            ) : (
              <article className="module-card" key={module.name}>{content}</article>
            );
          })}
        </div>
      </section>
    </div>
  );
};
