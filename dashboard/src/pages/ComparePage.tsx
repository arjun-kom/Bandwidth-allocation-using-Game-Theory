import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type UserSpec } from "../api";
import type { AllocationResult, Meta } from "../types";
import { Card, MECH_COLORS, fmt, pct } from "../components/ui";

interface Row { id: string; type: string; demand: number; weight: number; budget: number; claims: number | "" }

const START: Row[] = [
  { id: "alice-video", type: "video", demand: 8, weight: 1, budget: 10, claims: "" },
  { id: "bob-gaming", type: "gaming", demand: 3, weight: 1, budget: 10, claims: "" },
  { id: "carol-call", type: "call", demand: 4, weight: 1, budget: 10, claims: "" },
  { id: "dan-web", type: "web", demand: 2, weight: 1, budget: 10, claims: "" },
  { id: "eve-download", type: "download", demand: 25, weight: 1, budget: 10, claims: "" },
  { id: "frank-download", type: "download", demand: 25, weight: 3, budget: 30, claims: "" },
];

export default function ComparePage({ meta }: { meta: Meta }) {
  const [rows, setRows] = useState<Row[]>(START);
  const [capacity, setCapacity] = useState(20);
  const [results, setResults] = useState<Record<string, AllocationResult> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const users: UserSpec[] = rows.map((r) => ({
        id: r.id, type: r.type, demand: r.demand, weight: r.weight, budget: r.budget,
        ...(r.claims !== "" ? { reported_demand: Number(r.claims) } : {}),
      }));
      setResults((await api.compare(capacity, users)).results);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { run(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const addRow = () => {
    const n = rows.length + 1;
    setRows([...rows, { id: `user-${n}`, type: "web", demand: meta.user_types.web.demand, weight: 1, budget: 10, claims: "" }]);
  };

  const mechs = Object.keys(meta.mechanisms);
  const chartData = rows.map((r) => ({
    id: r.id,
    demand: r.demand,
    ...Object.fromEntries(mechs.map((m) => [m, results?.[m]?.rates[r.id] ?? 0])),
  }));
  const totalDemand = rows.reduce((s, r) => s + r.demand, 0);

  return (
    <div className="grid">
      <Card title="Users on the link" right={<span className="muted small">total demand {fmt(totalDemand, 1)} Mbps</span>}>
        <div className="table-wrap">
          <table className="edit">
            <thead>
              <tr><th>Name</th><th>Type</th><th>Demand (Mbps)</th><th>Claims (lie)</th><th>Weight</th><th>Budget</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td><input value={r.id} onChange={(e) => update(i, { id: e.target.value })} /></td>
                  <td>
                    <select value={r.type} onChange={(e) => update(i, { type: e.target.value, demand: meta.user_types[e.target.value].demand })}>
                      {Object.entries(meta.user_types).map(([k, t]) => <option key={k} value={k}>{t.label}</option>)}
                    </select>
                  </td>
                  <td><input type="number" min={0.1} step={0.5} value={r.demand} onChange={(e) => update(i, { demand: Number(e.target.value) })} /></td>
                  <td><input type="number" min={0.1} placeholder="honest" value={r.claims} onChange={(e) => update(i, { claims: e.target.value === "" ? "" : Number(e.target.value) })} /></td>
                  <td><input type="number" min={0.1} step={0.5} value={r.weight} onChange={(e) => update(i, { weight: Number(e.target.value) })} /></td>
                  <td><input type="number" min={0.1} step={1} value={r.budget} onChange={(e) => update(i, { budget: Number(e.target.value) })} /></td>
                  <td><button className="small" onClick={() => setRows(rows.filter((_, j) => j !== i))}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="controls">
          <label>
            Link capacity (Mbps)
            <input type="number" min={1} value={capacity} onChange={(e) => setCapacity(Number(e.target.value))} />
          </label>
          <div className="buttons">
            <button onClick={addRow}>Add user</button>
            <button className="primary" onClick={run} disabled={busy}>{busy ? "Computing…" : "Compare all mechanisms"}</button>
          </div>
        </div>
        <p className="muted small">Weight only matters for weighted priority. Budget only matters for the Kelly auction. "Claims" lets a user lie about its demand.</p>
        {error && <div className="alert">{error}</div>}
      </Card>

      {results && (
        <>
          <Card title="Mbps each user gets under each mechanism">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={chartData} margin={{ left: 0, right: 8, top: 8, bottom: 30 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="id" angle={-25} textAnchor="end" interval={0} fontSize={11} stroke="var(--muted)" />
                <YAxis unit=" Mb" fontSize={11} stroke="var(--muted)" />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 24 }} />
                {mechs.map((m) => (
                  <Bar key={m} dataKey={m} name={meta.mechanisms[m].label} fill={MECH_COLORS[m]} isAnimationActive={false} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Scorecard">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Mechanism</th><th>Kind</th><th>Jain fairness</th><th>Total utility</th><th>Mean satisfaction</th><th>Worst-off user</th><th>Below minimum</th><th>Useful utilisation</th></tr>
                </thead>
                <tbody>
                  {mechs.map((m) => {
                    const r = results[m].metrics;
                    return (
                      <tr key={m}>
                        <td><i className="dot" style={{ background: MECH_COLORS[m] }} />{meta.mechanisms[m].label}</td>
                        <td className="muted">{meta.mechanisms[m].kind}</td>
                        <td>{fmt(r.jain_fairness, 3)}</td>
                        <td>{fmt(r.total_utility)}</td>
                        <td>{pct(r.mean_satisfaction)}</td>
                        <td>{pct(r.min_satisfaction)}</td>
                        <td className={r.starved_users ? "warn" : ""}>{r.starved_users}</td>
                        <td>{pct(r.useful_utilization)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
