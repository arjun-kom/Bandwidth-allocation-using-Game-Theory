import { useEffect, useState } from "react";
import { api } from "../api";
import type { Meta } from "../types";
import { Card, fmt } from "../components/ui";

export default function HistoryPage({ meta }: { meta: Meta }) {
  const [runs, setRuns] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.runs().then(setRuns).catch((e) => setError(String(e))); }, []);
  const name = (id: string) => meta.scenarios.find((s) => s.id === id)?.name ?? id;
  const mech = (ids: string) => ids.split(",").map((m) => meta.mechanisms[m]?.label ?? m).join(", ");

  return (
    <Card title="Saved live runs">
      {error && <div className="alert">{error}</div>}
      {runs && runs.length === 0 && <p className="muted">No runs yet. Every live simulation is saved here when it finishes or when you close it.</p>}
      {runs && runs.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>When</th><th>Scenario</th><th>Mechanism(s)</th><th>Ticks</th><th>Mean fairness</th><th>Mean utility</th><th>Mean below minimum</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{new Date(r.started_at * 1000).toLocaleString()}</td>
                  <td>{name(r.scenario)}</td>
                  <td>{mech(r.mechanisms)}</td>
                  <td>{r.ticks}</td>
                  <td>{fmt(r.mean_fairness, 3)}</td>
                  <td>{fmt(r.mean_utility)}</td>
                  <td>{fmt(r.mean_starved)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
