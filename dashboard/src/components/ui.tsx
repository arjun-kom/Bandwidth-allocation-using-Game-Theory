import type { ReactNode } from "react";

export function Card({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="card">
      {(title || right) && (
        <div className="card-head">
          {title && <h3>{title}</h3>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "good" | "bad" }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export const fmt = (n: number | undefined, d = 2) => (n === undefined || n === null || Number.isNaN(n) ? "–" : n.toFixed(d));
export const pct = (n: number | undefined) => (n === undefined ? "–" : `${Math.round(n * 100)}%`);

export const MECH_COLORS: Record<string, string> = {
  nash_bargaining: "#2563eb",
  kelly: "#f97316",
  weighted_priority: "#7c3aed",
  max_min: "#10b981",
  equal_share: "#9ca3af",
};
