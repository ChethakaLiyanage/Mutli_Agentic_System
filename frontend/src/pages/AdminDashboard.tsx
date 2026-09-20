import { useEffect, useState } from "react";

import { fetchReviewQueue } from "../api/review";
import type { ReviewQueueItem } from "../types/review";

type Section = "overview" | "analytics" | "claims" | "rules" | "users" | "documents" | "settings";

const sections: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "analytics", label: "Risk analytics" },
  { id: "claims", label: "Claims management" },
  { id: "rules", label: "Rules & models" },
  { id: "users", label: "Users & access" },
  { id: "documents", label: "Policy documents" },
  { id: "settings", label: "Settings" },
];

const colors: Record<string, string> = {
  High: "bg-[#fff0ed] text-[#bd3e2b]",
  Medium: "bg-[#fff5df] text-[#a66800]",
  Low: "bg-[#e8f7ee] text-[#17734c]",
  "Under review": "bg-[#e8f4ff] text-[#1967a3]",
};

const Badge = ({ value }: { value: string }) => (
  <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${colors[value] ?? "bg-slate-100 text-slate-600"}`}>
    {value}
  </span>
);

const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <article className={`rounded-xl border border-[#dfe7e7] bg-white p-5 shadow-[0_5px_18px_rgba(20,43,58,0.04)] ${className}`}>
    {children}
  </article>
);

const riskLabel = (level: string | null) => level ? `${level[0].toUpperCase()}${level.slice(1)}` : "Unknown";

const averageRisk = (items: ReviewQueueItem[]) => items.length
  ? items.reduce((sum, item) => sum + (item.risk_score ?? 0), 0) / items.length
  : 0;

export const AdminDashboard = () => {
  const [section, setSection] = useState<Section>("overview");
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchReviewQueue()
      .then((response) => {
        if (active) setItems(response.items);
      })
      .catch(() => {
        if (active) setError("Risk data is unavailable. Check the reviewer service and try again.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="min-h-screen bg-[#f5f7f7] font-[Inter,ui-sans-serif,system-ui,sans-serif] text-[#142b3a]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[244px] border-r border-[#dbe5e5] bg-[#123c42] px-4 py-5 text-[#d7e8e5] lg:block">
        <div className="mb-10 px-2"><p className="text-sm font-black tracking-wide text-white">claim<span className="text-[#f18a62]">flow</span></p><p className="text-[10px] uppercase tracking-[0.18em] text-[#91b5b0]">operations</p></div>
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-[#729a96]">Workspace</p>
        <nav className="space-y-1" aria-label="Admin workspace">
          {sections.map((item) => <button key={item.id} onClick={() => setSection(item.id)} className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition ${section === item.id ? "bg-[#e86d45] text-white" : "text-[#b7d0cc] hover:bg-[#1d4d52] hover:text-white"}`}>{item.label}</button>)}
        </nav>
      </aside>
      <main className="lg:ml-[244px]">
        <header className="sticky top-0 z-10 flex min-h-[72px] items-center justify-between border-b border-[#dbe5e5] bg-[#f5f7f7]/95 px-5 backdrop-blur md:px-9">
          <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-[#819198]">Admin workspace</p><p className="text-sm font-bold text-[#365363]">Production risk operations</p></div>
          <span className="rounded-full bg-[#e8f7ee] px-3 py-1 text-[11px] font-bold text-[#17734c]">Page-load data</span>
        </header>
        <div className="mx-auto max-w-[1450px] p-5 md:p-9">
          {error && <div role="alert" className="mb-5 rounded-lg border border-[#f1d7cd] bg-[#fffaf7] px-4 py-3 text-sm font-bold text-[#bd3e2b]">{error}</div>}
          {section === "overview" && <Overview items={items} loading={loading} onAnalytics={() => setSection("analytics")} />}
          {section === "analytics" && <Analytics items={items} loading={loading} />}
          {section === "claims" && <Claims items={items} loading={loading} />}
          {!(["overview", "analytics", "claims"] as Section[]).includes(section) && <Card><h2 className="text-2xl font-black">{sections.find((item) => item.id === section)?.label}</h2><p className="mt-2 text-sm text-[#778590]">This workspace section is not connected to production data yet.</p></Card>}
        </div>
      </main>
    </div>
  );
};

function Overview({ items, loading, onAnalytics }: { items: ReviewQueueItem[]; loading: boolean; onAnalytics: () => void }) {
  const high = items.filter((item) => item.risk_level === "high").length;
  const medium = items.filter((item) => item.risk_level === "medium").length;
  const low = items.filter((item) => item.risk_level === "low").length;
  const average = averageRisk(items);
  const observations = items.flatMap((item) => item.reviewer_summary?.risk_observations ?? []).slice(0, 3);
  const total = items.length;
  const highEnd = total ? high / total * 100 : 0;
  const mediumEnd = total ? (high + medium) / total * 100 : 0;

  return <>
    <Header title="Claims command center" detail="Live fraud assessments with reviewer guidance context." />
    <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[["Assessed claims", total], ["High risk", high], ["Average risk score", `${Math.round(average * 100)}%`], ["Missing documents", items.reduce((sum, item) => sum + item.missing_documents.length, 0)]].map(([label, value]) => <Card key={label}><p className="text-xs font-bold text-[#788990]">{label}</p><p className="mt-3 text-3xl font-black">{loading ? "..." : value}</p><p className="mt-1 text-[11px] text-[#9aa8ac]">Persisted production values</p></Card>)}
    </div>
    <div className="grid gap-6 xl:grid-cols-2">
      <Card><h3 className="font-black">Risk distribution</h3><p className="mt-1 text-xs text-[#8b9a9f]">Fraud assessment levels in the current reviewer queue</p><div className="mt-6 flex items-center gap-6"><div className="grid h-32 w-32 place-items-center rounded-full" style={{ background: `conic-gradient(#e86d45 0 ${highEnd}%, #f1c66a ${highEnd}% ${mediumEnd}%, #82cbb5 ${mediumEnd}% 100%)` }}><div className="grid h-20 w-20 place-items-center rounded-full bg-white"><span className="text-xl font-black">{Math.round(average * 100)}</span></div></div><div className="space-y-3 text-xs">{[["Low risk", low], ["Medium risk", medium], ["High risk", high]].map(([label, value]) => <div key={label} className="flex items-center gap-2"><span className="w-24 text-[#788990]">{label}</span><strong>{value}</strong></div>)}</div></div></Card>
      <Card><div className="flex items-center justify-between"><div><h3 className="font-black">Reviewer guidance</h3><p className="mt-1 text-xs text-[#8b9a9f]">Risk observations from Agent 4</p></div><button onClick={onAnalytics} className="text-xs font-bold text-[#d75b36]">View analytics</button></div><div className="mt-5 space-y-3">{observations.length ? observations.map((item) => <p key={item} className="rounded-lg bg-[#f5f8f8] p-3 text-xs font-semibold text-[#526b75]">{item}</p>) : <p className="text-xs text-[#8b9a9f]">No reviewer summary is available yet.</p>}</div></Card>
    </div>
  </>;
}

function Analytics({ items, loading }: { items: ReviewQueueItem[]; loading: boolean }) {
  const buckets = Array.from({ length: 10 }, (_, index) => items.filter((item) => Math.min(9, Math.floor((item.risk_score ?? 0) * 10)) === index).length);
  const rules = items.flatMap((item) => item.reviewer_summary?.risk_observations ?? []);
  const ruleCounts = rules.reduce<Record<string, number>>((counts, rule) => ({ ...counts, [rule]: (counts[rule] ?? 0) + 1 }), {});
  const average = averageRisk(items);
  return <>
    <Header title="Risk analytics" detail="Metrics are calculated from persisted production fraud assessments." />
    <div className="grid gap-6 xl:grid-cols-2">
      <Card><h3 className="font-black">Risk score distribution</h3><div className="mt-6 flex h-52 items-end gap-1 border-b border-l border-[#e6eded] px-2">{buckets.map((count, index) => <div key={index} className="flex-1 rounded-t bg-[#e86d45]" style={{ height: `${loading ? 0 : Math.max(4, count / Math.max(1, ...buckets) * 100)}%` }} />)}</div><div className="mt-2 flex justify-between text-[10px] text-[#9aa8ac]"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div></Card>
      <Card><h3 className="font-black">Model and hybrid score</h3><div className="mt-6 grid grid-cols-2 gap-3"><Metric label="Average hybrid risk" value={`${Math.round(average * 100)}%`} /><Metric label="Assessed claims" value={String(items.length)} /><Metric label="High risk claims" value={String(items.filter((item) => item.risk_level === "high").length)} /><Metric label="ML scores available" value={"Stored with assessment"} /></div></Card>
      <Card><h3 className="mb-4 font-black">Reviewer risk observations</h3>{Object.entries(ruleCounts).length ? Object.entries(ruleCounts).map(([label, count]) => <div key={label} className="mb-4 flex items-center justify-between rounded-lg bg-[#f5f8f8] p-3 text-xs"><span className="font-bold text-[#526b75]">{label}</span><strong>{count}</strong></div>) : <p className="text-xs text-[#8b9a9f]">No reviewer observations are available yet.</p>}</Card>
    </div>
  </>;
}

function Claims({ items, loading }: { items: ReviewQueueItem[]; loading: boolean }) {
  return <><Header title="Claims management" detail="Claims currently awaiting human review, sourced from production fraud assessments." /><Card><div className="overflow-x-auto"><table className="w-full min-w-[800px] text-left"><thead className="border-b border-[#edf1f1] text-[10px] uppercase tracking-wider text-[#8b9a9f]"><tr>{["Claim", "Type", "Risk score", "Risk", "Action", "Missing documents"].map((heading) => <th key={heading} className="px-3 py-3">{heading}</th>)}</tr></thead><tbody className="divide-y divide-[#edf1f1]">{loading ? <tr><td colSpan={6} className="px-3 py-6 text-sm text-[#8b9a9f]">Loading production assessments...</td></tr> : items.map((item) => <tr key={item.workflow_id}><td className="px-3 py-4 text-xs font-black text-[#d75b36]">{item.claim_id}</td><td className="px-3 py-4 text-xs font-semibold text-[#526b75]">{item.incident_type ?? "Claim"}</td><td className="px-3 py-4 text-xs font-semibold">{item.risk_score == null ? "—" : `${Math.round(item.risk_score * 100)}%`}</td><td className="px-3 py-4"><Badge value={riskLabel(item.risk_level)} /></td><td className="px-3 py-4 text-xs font-semibold text-[#526b75]">{item.recommended_action ?? "Review"}</td><td className="px-3 py-4 text-xs text-[#788990]">{item.missing_documents.length || "None"}</td></tr>)}</tbody></table></div></Card></>;
}

function Header({ title, detail }: { title: string; detail: string }) { return <div className="mb-6"><p className="mb-2 text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#d75b36]">Admin risk operations</p><h2 className="text-2xl font-black tracking-[-0.03em] text-[#142b3a]">{title}</h2><p className="mt-1 text-sm text-[#778590]">{detail}</p></div>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-[#f5f8f8] p-3"><p className="text-[10px] font-bold uppercase tracking-wider text-[#8b9a9f]">{label}</p><p className="mt-2 text-xl font-black">{value}</p></div>; }
