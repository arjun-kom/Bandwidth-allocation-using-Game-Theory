import type { AllocationResult, Meta } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? r.statusText);
    throw new Error(detail);
  }
  return r.json();
}

export interface UserSpec {
  id: string;
  type: string;
  demand?: number;
  weight?: number;
  budget?: number;
  reported_demand?: number;
}

export const api = {
  meta: () => req<Meta>("/api/meta"),
  compare: (capacity: number, users: UserSpec[]) =>
    req<{ results: Record<string, AllocationResult> }>("/api/compare", {
      method: "POST",
      body: JSON.stringify({ capacity, users }),
    }),
  allocate: (capacity: number, mechanism: string, users: UserSpec[]) =>
    req<{ allocation: AllocationResult }>("/api/allocate", {
      method: "POST",
      body: JSON.stringify({ capacity, mechanism, users }),
    }),
  experiments: () => req<any>("/api/experiments"),
  runExperiments: () => req<any>("/api/experiments/run", { method: "POST" }),
  runs: () => req<any[]>("/api/runs"),
};

export function wsUrl(path: string) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}${path}`;
}
