export interface UserType {
  label: string;
  elastic: boolean;
  min_rate: number;
  demand: number;
  steepness: number;
  color: string;
}

export interface Mechanism {
  label: string;
  kind: string;
  description: string;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  capacity: number;
  ticks: number;
}

export interface Meta {
  user_types: Record<string, UserType>;
  mechanisms: Record<string, Mechanism>;
  scenarios: Scenario[];
}

export interface Metrics {
  jain_fairness: number;
  total_utility: number;
  mean_utility: number;
  mean_satisfaction: number;
  min_satisfaction: number;
  starved_users: number;
  utilization: number;
  useful_utilization: number;
  users: number;
}

export interface SimUser {
  id: string;
  type: string;
  demand: number;
  min_rate: number;
  weight: number;
  budget: number;
  reported_demand: number | null;
  claimed_demand: number;
  honest: boolean;
  rate: number;
  utility: number;
  starved: boolean;
}

export interface TickRecord {
  tick: number;
  mechanism: string;
  capacity: number;
  events: string[];
  users: SimUser[];
  metrics: Metrics;
  extra: { price?: number; iterations?: number; converged?: boolean; not_admitted?: string[]; bids?: Record<string, number> };
}

export interface AllocationResult {
  mechanism: string;
  capacity: number;
  rates: Record<string, number>;
  metrics: Metrics;
  extra: Record<string, unknown>;
}
