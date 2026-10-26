"use client";
import { useEffect, useState } from "react";
type State = { state: string; title: string; description: string; renewal: string };
const scenarios = { active: "Active subscription", canceling: "Cancellation scheduled", pending: "Payment pending", expired: "Access expired", canceled: "Subscription canceled", unavailable: "Service unavailable" };
export default function Portal() {
  const [scenario, setScenario] = useState("active");
  const [status, setStatus] = useState<State | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    setStatus(null); setError("");
    fetch("/api/preview/status?scenario=" + scenario, { cache: "no-store" })
      .then(response => { if (!response.ok) throw Error(); return response.json() as Promise<State>; })
      .then(value => { if (current) setStatus(value); })
      .catch(() => { if (current) setError("The access preview is temporarily unavailable."); });
    return () => { current = false; };
  }, [scenario]);
  return <div className="workspace">
    <aside className="workspace-side">
      <span className="pill">DEMONSTRATION</span><h2>Sample account</h2>
      <label htmlFor="scenario">Explore an access state</label>
      <select id="scenario" value={scenario} onChange={event => setScenario(event.target.value)}>
        {Object.entries(scenarios).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <a className="button full" href="/account">Manage account →</a>
      <a className="textlink" href="/preview/checkout">Subscription walkthrough →</a>
    </aside>
    <section className="workspace-status" aria-label="Sample access status" aria-live="polite">
      <div className="status-card"><span className="eyebrow">ACCESS STATUS</span>
        <h3>{error ? "Status unavailable" : status?.title || "Checking status…"}</h3>
        {status && <><p>{status.description}</p><small>{status.renewal}</small></>}
        {error && <p role="alert">{error}</p>}
      </div>
    </section>
  </div>;
}
