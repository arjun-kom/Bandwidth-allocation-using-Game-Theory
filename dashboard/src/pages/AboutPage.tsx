import type { Meta } from "../types";
import { Card, MECH_COLORS } from "../components/ui";

export default function AboutPage({ meta }: { meta: Meta }) {
  return (
    <div className="grid">
      <Card title="The game">
        <p>
          One link of capacity <b>C</b> Mbps is shared by <b>n</b> users. Each user is a player with its own <b>utility</b>: how useful
          x Mbps is to it, from 0 (useless) to 1 (demand fully met). Every Mbps one user gets is taken from someone else, so the
          question is not "how much does each user want" but "what split is fair and efficient when everyone wants more".
        </p>
        <ul>
          <li><b>Elastic</b> traffic (web, downloads) uses log utility: any extra bandwidth helps, with diminishing returns.</li>
          <li><b>Inelastic</b> traffic (video, gaming, calls) uses a sigmoid: almost useless below its minimum rate, then quickly fine.</li>
        </ul>
      </Card>
      <Card title="User types">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Type</th><th>Traffic</th><th>Minimum rate</th><th>Default demand</th></tr></thead>
            <tbody>
              {Object.entries(meta.user_types).map(([k, t]) => (
                <tr key={k}>
                  <td><i className="dot" style={{ background: t.color }} />{t.label}</td>
                  <td>{t.elastic ? "elastic (log)" : "inelastic (sigmoid)"}</td>
                  <td>{t.min_rate ? `${t.min_rate} Mbps` : "none"}</td>
                  <td>{t.demand} Mbps</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Mechanisms">
        {Object.entries(meta.mechanisms).map(([k, m]) => (
          <div key={k} className="mech">
            <h4><i className="dot" style={{ background: MECH_COLORS[k] }} />{m.label} <span className="tag">{m.kind}</span></h4>
            <p>{m.description}</p>
          </div>
        ))}
      </Card>
      <Card title="Metrics">
        <ul>
          <li><b>Jain fairness</b> of satisfaction ratios x/d: (Σs)² / (n·Σs²). 1 means everyone gets the same share of what they need.</li>
          <li><b>Total utility</b>: Σ U(x). Higher means the link is used where it helps most.</li>
          <li><b>Below minimum</b>: inelastic users that get less than their minimum rate, so their app does not work.</li>
          <li><b>Useful utilisation</b>: share of the link that goes to real demand (not to lies or waste).</li>
          <li><b>Price of anarchy</b>: optimal value ÷ value at the Kelly equilibrium; how much selfish bidding costs.</li>
        </ul>
      </Card>
    </div>
  );
}
