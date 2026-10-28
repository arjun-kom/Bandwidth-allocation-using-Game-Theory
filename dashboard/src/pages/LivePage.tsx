import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { wsUrl } from "../api";
import type { Meta, TickRecord } from "../types";
import { Card, Stat, fmt, pct } from "../components/ui";

type Status = "idle" | "connecting" | "running" | "paused" | "done" | "closed";

export default function LivePage({ meta }: { meta: Meta }) {
  const [scenario, setScenario] = useState(meta.scenarios.find((s) => s.id === "peak_hour")?.id ?? meta.scenarios[0].id);
  const [mechanism, setMechanism] = useState("nash_bargaining");
  const [speed, setSpeed] = useState(2);
  const [status, setStatus] = useState<Status>("idle");
  const [records, setRecords] = useState<TickRecord[]>([]);
  const [totalTicks, setTotalTicks] = useState(0);
  const [log, setLog] = useState<{ tick: number; text: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [capacityInput, setCapacityInput] = useState("");
  const [newType, setNewType] = useState("video");
  const [newWeight, setNewWeight] = useState(1);
  const ws = useRef<WebSocket | null>(null);

  const send = useCallback((msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  }, []);

  const start = () => {
    ws.current?.close();
    setRecords([]);
    setLog([]);
    setError(null);
    setStatus("connecting");
    const sock = new WebSocket(wsUrl("/ws/simulate"));
    ws.current = sock;
    sock.onopen = () => sock.send(JSON.stringify({ type: "start", scenario, mechanism, speed }));
    sock.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "started") {
        setStatus("running");
        setTotalTicks(msg.ticks);
        setLog([{ tick: 0, text: `Started "${msg.name}" with ${meta.mechanisms[msg.mechanism].label}` }]);
      } else if (msg.type === "tick") {
        const r: TickRecord = msg.record;
        setTotalTicks(msg.total_ticks);
        setRecords((prev) => [...prev.slice(-299), r]);
        if (r.events.length) setLog((prev) => [...r.events.map((t) => ({ tick: r.tick, text: t })), ...prev].slice(0, 50));
      } else if (msg.type === "done") {
        setStatus("done");
        setLog((prev) => [{ tick: -1, text: `Run finished and saved${msg.run_id ? ` as run #${msg.run_id}` : ""}` }, ...prev]);
      } else if (msg.type === "error") {
        setError(msg.message);
      }
    };
    sock.onclose = () => setStatus((s) => (s === "done" ? s : "closed"));
    sock.onerror = () => setError("Lost the connection to the server.");
  };

  useEffect(() => () => ws.current?.close(), []);

  const last = records[records.length - 1];
  const live = status === "running" || status === "paused" || status === "done";

  const pause = () => { send({ type: "pause" }); setStatus("paused"); };
  const resume = () => { send({ type: "resume" }); setStatus("running"); };
  const changeMechanism = (m: string) => {
    setMechanism(m);
    if (live) {
      send({ type: "set_mechanism", mechanism: m });
      setLog((prev) => [{ tick: last?.tick ?? 0, text: `Switched to ${meta.mechanisms[m].label}` }, ...prev]);
    }
  };
  const changeSpeed = (s: number) => { setSpeed(s); send({ type: "set_speed", speed: s }); };
  const setCapacity = () => {
    const c = Number(capacityInput);
    if (c > 0) {
      send({ type: "set_capacity", capacity: c });
      setLog((prev) => [{ tick: last?.tick ?? 0, text: `Link capacity set to ${c} Mbps` }, ...prev]);
      setCapacityInput("");
    }
  };
  const addUser = () => {
    send({ type: "add_user", user_type: newType, weight: newWeight });
    setLog((prev) => [{ tick: last?.tick ?? 0, text: `Added a ${meta.user_types[newType].label.toLowerCase()} user (weight ${newWeight})` }, ...prev]);
  };

  const barData = (last?.users ?? []).map((u) => ({
    id: u.id,
    type: u.type,
    allocated: u.rate,
    demand: u.demand,
    min: u.min_rate,
    starved: u.starved,
  }));
  const lineData = records.map((r) => ({
    tick: r.tick,
    fairness: r.metrics.jain_fairness,
    satisfaction: r.metrics.mean_satisfaction,
    worst: r.metrics.min_satisfaction,
    utilisation: r.metrics.useful_utilization,
  }));
  const sc = meta.scenarios.find((s) => s.id === scenario);

  return (
    <div className="grid">
      <Card title="Simulation">
        <div className="controls">
          <label>
            Scenario
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {meta.scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          <label>
            Mechanism
            <select value={mechanism} onChange={(e) => changeMechanism(e.target.value)}>
              {Object.entries(meta.mechanisms).map(([k, m]) => (
                <option key={k} value={k}>{m.label}</option>
              ))}
            </select>
          </label>
          <label>
            Speed: {speed} ticks/s
            <input type="range" min={0.5} max={10} step={0.5} value={speed} onChange={(e) => changeSpeed(Number(e.target.value))} />
          </label>
          <div className="buttons">
            <button className="primary" onClick={start}>{live ? "Restart" : "Start"}</button>
            {status === "running" && <button onClick={pause}>Pause</button>}
            {status === "paused" && <button onClick={resume}>Resume</button>}
            {status === "paused" && <button onClick={() => send({ type: "step" })}>Step</button>}
            {status === "done" && <button onClick={() => { send({ type: "extend", ticks: 60 }); setStatus("running"); }}>Run 60 more ticks</button>}
          </div>
        </div>
        {sc && <p className="muted small">{sc.description}</p>}
        <p className="muted small">{meta.mechanisms[mechanism].description}</p>
        {error && <div className="alert">{error}</div>}
        {live && (
          <div className="progress">
            <div style={{ width: `${Math.min(100, ((last?.tick ?? 0) + 1) / Math.max(totalTicks, 1) * 100)}%` }} />
            <span>tick {last ? last.tick + 1 : 0} of {totalTicks} · {status}</span>
          </div>
        )}
      </Card>

      {last && (
        <>
          <div className="stats">
            <Stat label="Jain fairness" value={fmt(last.metrics.jain_fairness, 3)} hint="1 = everyone equally satisfied" />
            <Stat label="Total utility" value={fmt(last.metrics.total_utility)} hint={`max ${last.users.length}`} />
            <Stat label="Mean satisfaction" value={pct(last.metrics.mean_satisfaction)} hint="share of demand met" />
            <Stat label="Below minimum" value={String(last.metrics.starved_users)} hint="apps that cannot work" tone={last.metrics.starved_users ? "bad" : "good"} />
            <Stat label="Useful utilisation" value={pct(last.metrics.useful_utilization)} hint={`of ${last.capacity} Mbps`} />
            {last.extra.price !== undefined && (
              <Stat label="Kelly price" value={fmt(last.extra.price, 3)} hint={`per Mbps · ${last.extra.converged ? "equilibrium" : "time-averaged"}`} />
            )}
          </div>

          <Card title={`Allocation per user at tick ${last.tick + 1}`} right={<span className="muted small">bars = Mbps given, outline = demand, red = below minimum</span>}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={barData} barGap={-18} margin={{ left: 0, right: 8, top: 8, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="id" angle={-40} textAnchor="end" interval={0} fontSize={11} stroke="var(--muted)" />
                <YAxis unit=" Mb" fontSize={11} stroke="var(--muted)" />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} labelStyle={{ color: "var(--text)" }} itemStyle={{ color: "var(--text)" }} cursor={{ fill: "rgba(255,255,255,0.06)" }} />
                <Bar dataKey="demand" name="Demand" fill="transparent" stroke="var(--muted)" barSize={18} isAnimationActive={false} />
                <Bar dataKey="allocated" name="Allocated" barSize={18} isAnimationActive={false}>
                  {barData.map((d) => (
                    <Cell key={d.id} fill={d.starved ? "#dc2626" : meta.user_types[d.type].color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="legend">
              {Object.entries(meta.user_types).map(([k, t]) => (
                <span key={k}><i style={{ background: t.color }} />{t.label}</span>
              ))}
              <span><i style={{ background: "#dc2626" }} />Below minimum rate</span>
            </div>
          </Card>

          <Card title="Fairness and satisfaction over time">
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={lineData} margin={{ left: 0, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="tick" fontSize={11} stroke="var(--muted)" />
                <YAxis domain={[0, 1]} fontSize={11} stroke="var(--muted)" />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="fairness" name="Jain fairness" stroke="#2563eb" dot={false} isAnimationActive={false} />
                <Line dataKey="satisfaction" name="Mean satisfaction" stroke="#10b981" dot={false} isAnimationActive={false} />
                <Line dataKey="worst" name="Worst-off user" stroke="#dc2626" dot={false} isAnimationActive={false} />
                <Line dataKey="utilisation" name="Useful utilisation" stroke="#f97316" dot={false} strokeDasharray="4 3" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <div className="two">
            <Card title="Change the network">
              <div className="controls">
                <label>
                  Add a user
                  <select value={newType} onChange={(e) => setNewType(e.target.value)}>
                    {Object.entries(meta.user_types).map(([k, t]) => (
                      <option key={k} value={k}>{t.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Priority weight
                  <input type="number" min={0.1} max={100} step={0.5} value={newWeight} onChange={(e) => setNewWeight(Number(e.target.value))} />
                </label>
                <div className="buttons"><button onClick={addUser}>Add user</button></div>
              </div>
              <div className="controls">
                <label>
                  Link capacity (now {last.capacity} Mbps)
                  <input type="number" min={1} placeholder="Mbps" value={capacityInput} onChange={(e) => setCapacityInput(e.target.value)} />
                </label>
                <div className="buttons"><button onClick={setCapacity}>Set capacity</button></div>
              </div>
            </Card>
            <Card title="Event log">
              <ul className="log">
                {log.map((l, i) => (
                  <li key={i}><span className="muted">{l.tick >= 0 ? `t${l.tick + 1}` : "·"}</span> {l.text}</li>
                ))}
              </ul>
            </Card>
          </div>

          <Card title="Users">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>User</th><th>Type</th><th>Demand</th><th>Claims</th><th>Min</th><th>Weight</th>
                    <th>Allocated</th><th>Utility</th>{last.extra.bids && <th>Bid</th>}<th></th>
                  </tr>
                </thead>
                <tbody>
                  {last.users.map((u) => (
                    <tr key={u.id} className={u.starved ? "bad-row" : ""}>
                      <td>{u.id}</td>
                      <td><i className="dot" style={{ background: meta.user_types[u.type].color }} />{meta.user_types[u.type].label}</td>
                      <td>{fmt(u.demand, 1)}</td>
                      <td>{u.honest ? <span className="muted">honest</span> : <b className="warn">{fmt(u.claimed_demand, 1)}</b>}</td>
                      <td>{fmt(u.min_rate, 1)}</td>
                      <td>{u.weight}</td>
                      <td><b>{fmt(u.rate, 2)}</b></td>
                      <td>{fmt(u.utility, 2)}</td>
                      {last.extra.bids && <td>{fmt(last.extra.bids[u.id], 3)}</td>}
                      <td className="actions">
                        {u.honest ? (
                          <button className="small" title="Make this user claim 5x its real demand"
                            onClick={() => send({ type: "update_user", id: u.id, params: { reported_demand: u.demand * 5 } })}>Lie</button>
                        ) : (
                          <button className="small" onClick={() => send({ type: "update_user", id: u.id, params: { honest: true } })}>Be honest</button>
                        )}
                        <button className="small" onClick={() => send({ type: "remove_user", id: u.id })}>Remove</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
      {!last && status === "idle" && (
        <Card>
          <p>Pick a scenario and a mechanism, then press <b>Start</b>. While it runs you can switch mechanisms, add users, make a user lie about its demand or shrink the link, and watch the allocation re-balance.</p>
        </Card>
      )}
    </div>
  );
}
