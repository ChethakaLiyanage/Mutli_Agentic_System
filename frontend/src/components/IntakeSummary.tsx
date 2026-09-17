import type { IntakeResult } from "../types/orchestrator";

const friendly = (value: string): string =>
  value
    .split(/[_\s]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export const IntakeSummary = ({ intake }: { intake: IntakeResult }) => {
  const { intent, incident, damage } = intake.data;
  const rows: Array<[string, string]> = [];

  if (intent.label) {
    rows.push([
      "Intent",
      `${friendly(intent.label)} (${Math.round(intent.confidence * 100)}% confidence)`,
    ]);
  }
  if (incident.type) rows.push(["Incident", friendly(incident.type)]);
  if (incident.date_text) {
    rows.push([
      "Date",
      incident.normalized_date
        ? `${incident.date_text} · ${incident.normalized_date}`
        : incident.date_text,
    ]);
  }
  if (incident.location) rows.push(["Location", incident.location]);
  if (damage.areas.length) {
    rows.push(["Damage", damage.areas.map(friendly).join(", ")]);
  }

  if (!rows.length) return null;

  return (
    <section className="intake-summary" aria-labelledby="intake-summary-title">
      <div>
        <p className="eyebrow">Agent 1 result</p>
        <h2 id="intake-summary-title">Intake summary</h2>
      </div>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};
