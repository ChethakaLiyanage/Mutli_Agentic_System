import { useAuth } from "../context/auth-context";

const modules = [
  {
    name: "Claim Assistant",
    description: "Start and continue guided motor claim conversations.",
    accent: "blue",
  },
  {
    name: "My Claims",
    description: "Review submitted claims and their current progress.",
    accent: "indigo",
  },
  {
    name: "Policy Support",
    description: "Ask questions about motor policy information and coverage.",
    accent: "cyan",
  },
  {
    name: "Profile",
    description: "View and manage your customer account information.",
    accent: "slate",
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
          {modules.map((module, index) => (
            <article className="module-card" key={module.name}>
              <span className={`module-number module-number-${module.accent}`}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3>{module.name}</h3>
              <p>{module.description}</p>
              <span className="coming-soon">Coming soon</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
};
