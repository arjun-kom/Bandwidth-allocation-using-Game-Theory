import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Meta } from "../types";
import { Card, MECH_COLORS, fmt } from "../components/ui";

export default function ExperimentsPage({ meta }: { meta: Meta }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api.experiments().then(setData).catch((e) => setError(String(e))), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!data?.running) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [data?.running, load]);

  const rerun = async () => { await api.runExperiments(); load(); };
  const res = data?.results;
  const mechs = Object.keys(meta.mechanisms);
  const scenarios = meta.scenarios;
  const cell = (sc: string, m: string, k: string) => res?.summary.find((r: any) => r.scenario === sc && r.mechanism === m)?.[k];

  const best = (sc: string, k: string, higher = true) => {
    const vals = mechs.map((m) => cell(sc, m, k) as number);
    return higher ? Math.max(...vals) : Math.min(...vals);
  };

  const pivot = (k: string, title: string, digits: number, higher: boolean) => (
    <Card title={title}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Scenario</th>{mechs.map((m) => <th key={m}><i className="dot" style={{ background: MECH_COLORS[m] }} />{meta.mechanisms[m].label}</th>)}</tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                {mechs.map((m) => {
                  const v = cell(s.id, m, k);
                  return <td key={m} className={v === best(s.id, k, higher) ? "best" : ""}>{fmt(v, digits)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );

  return (
    <div className="grid">
      <Card title="Experiments" right={<button onClick={rerun} disabled={data?.running}>{data?.running ? "Running… (about a minute)" : "Re-run all experiments"}</button>}>
        <p className="muted small">Every scenario is run with every mechanism using fixed random seeds. Values are averaged over all ticks of the run. The best value in each row is highlighted.</p>
        {error && <div className="alert">{error}</div>}
        {data?.error && <div className="alert">Last run failed: {data.error}</div>}
        {data && !res && !data.running && <p>No results yet. Press <b>Re-run all experiments</b>.</p>}
      </Card>
      {res && (
        <>
          {pivot("jain_fairness", "Jain fairness index (higher is fairer)", 3, true)}
          {pivot("total_utility", "Total utility (higher is more efficient)", 2, true)}
          {pivot("starved_users", "Average users below their minimum rate (lower is better)", 2, false)}

          <Card title="Does lying about demand pay? (selfish user scenario)">
            <p className="muted small">download-1 really needs {res.selfish_user[0]?.liar_true_need} Mbps but claims 40 Mbps between ticks 20 and 44.</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Mechanism</th><th>Liar's Mbps when honest</th><th>Liar's Mbps when lying</th><th>Gain from lying</th><th>Wasted Mbps</th><th>Honest users' utility change</th></tr></thead>
                <tbody>
                  {res.selfish_user.map((r: any) => (
                    <tr key={r.mechanism}>
                      <td><i className="dot" style={{ background: MECH_COLORS[r.mechanism] }} />{r.mechanism_label}</td>
                      <td>{fmt(r.liar_rate_honest)}</td>
                      <td>{fmt(r.liar_rate_lying)}</td>
                      <td className={r.gain_from_lying_pct > 1 ? "warn" : "best"}>{fmt(r.gain_from_lying_pct, 1)}%</td>
                      <td>{fmt(r.wasted_mbps)}</td>
                      <td>{fmt(r.honest_users_utility_change, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Price of anarchy of the Kelly auction">
            <p className="muted small">Optimal total value divided by the value at the selfish equilibrium (1.00 = selfishness costs nothing). Theory bounds it at 1.33 for concave utilities.</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Scenario</th><th>Samples</th><th>Mean PoA</th><th>Worst PoA</th><th>Efficiency</th></tr></thead>
                <tbody>
                  {res.price_of_anarchy.map((r: any) => (
                    <tr key={r.scenario}>
                      <td>{scenarios.find((s) => s.id === r.scenario)?.name ?? r.scenario}</td>
                      <td>{r.samples}</td><td>{fmt(r.mean_poa, 3)}</td><td>{fmt(r.worst_poa, 3)}</td><td>{fmt(r.efficiency_pct, 1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {data.charts?.length > 0 && (
            <Card title="Charts for the report">
              <div className="charts">
                {data.charts.map((c: string) => (
                  <a key={c} href={`/api/experiments/charts/${c}`} target="_blank" rel="noreferrer">
                    <img src={`/api/experiments/charts/${c}?t=${data.finished_at ?? 0}`} alt={c} />
                  </a>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
