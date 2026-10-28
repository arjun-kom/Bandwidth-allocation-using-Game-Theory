import { useEffect, useState } from "react";
import { api } from "./api";
import type { Meta } from "./types";
import LivePage from "./pages/LivePage";
import ComparePage from "./pages/ComparePage";
import ExperimentsPage from "./pages/ExperimentsPage";
import HistoryPage from "./pages/HistoryPage";
import AboutPage from "./pages/AboutPage";

const TABS = [
  { id: "live", label: "Live simulation" },
  { id: "compare", label: "Compare mechanisms" },
  { id: "experiments", label: "Experiments" },
  { id: "history", label: "Run history" },
  { id: "about", label: "How it works" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(() => (localStorage.getItem("tab") as Tab) || "live");

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem("tab", tab);
    } catch {
      /* ignore */
    }
  }, [tab]);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden>
            <i style={{ height: 8 }} />
            <i style={{ height: 14 }} />
            <i style={{ height: 20 }} />
          </span>
          <div>
            <h1>Game-Theoretic Bandwidth Allocation</h1>
            <p>Sharing one link among users with different needs, using Nash bargaining and auctions</p>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {error && <div className="alert">Could not reach the API: {error}</div>}
        {!meta && !error && <div className="muted pad">Loading…</div>}
        {meta && (
          <>
            {/* LivePage stays mounted so a running simulation survives tab switches */}
            <div hidden={tab !== "live"}>
              <LivePage meta={meta} />
            </div>
            {tab === "compare" && <ComparePage meta={meta} />}
            {tab === "experiments" && <ExperimentsPage meta={meta} />}
            {tab === "history" && <HistoryPage meta={meta} />}
            {tab === "about" && <AboutPage meta={meta} />}
          </>
        )}
      </main>
    </div>
  );
}
