"""Run every scenario with every mechanism and save the comparison.

Usage:  python -m experiments.run_all [--out results] [--no-charts]

Writes:
  results/summary.csv          one row per scenario x mechanism (metrics averaged over all ticks)
  results/ticks.csv            every tick of every run
  results/selfish_user.csv     how much the lying user gains under each mechanism
  results/price_of_anarchy.csv Kelly equilibrium vs the social optimum
  results/*.png                charts for the report
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from core import MECHANISMS
from core.mechanisms import kelly_auction
from core.metrics import price_of_anarchy
from core.optimum import social_optimum
from sim import Simulation, list_scenarios

METRIC_KEYS = ["jain_fairness", "total_utility", "mean_utility", "mean_satisfaction", "min_satisfaction",
               "starved_users", "utilization", "useful_utilization"]


def run_all(out_dir: Path | None = None, charts: bool = True, verbose: bool = True) -> dict:
    scenarios = list_scenarios()
    summary, ticks, runs = [], [], {}
    for sc in scenarios:
        for mech in MECHANISMS:
            hist = Simulation(sc["id"], mech).run()
            runs[(sc["id"], mech)] = hist
            row = {"scenario": sc["id"], "scenario_name": sc["name"], "mechanism": mech,
                   "mechanism_label": MECHANISMS[mech]["label"]}
            for k in METRIC_KEYS:
                row[k] = round(float(np.mean([h["metrics"].get(k, 0) for h in hist if h["metrics"]])), 4)
            summary.append(row)
            for h in hist:
                ticks.append({"scenario": sc["id"], "mechanism": mech, "tick": h["tick"], "capacity": h["capacity"],
                              **{k: h["metrics"].get(k) for k in METRIC_KEYS}})
            if verbose:
                print(f"{sc['id']:18s} {mech:18s} fairness={row['jain_fairness']:.3f} "
                      f"utility={row['total_utility']:.2f} starved={row['starved_users']:.2f}")

    selfish = selfish_analysis(runs)
    poa = poa_analysis(scenarios)
    result = {"summary": summary, "selfish_user": selfish, "price_of_anarchy": poa}

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(out_dir / "summary.csv", summary)
        _write_csv(out_dir / "ticks.csv", ticks)
        _write_csv(out_dir / "selfish_user.csv", selfish)
        _write_csv(out_dir / "price_of_anarchy.csv", poa)
        (out_dir / "results.json").write_text(json.dumps(result, indent=2))
        if charts:
            make_charts(out_dir, summary, runs, selfish)
        if verbose:
            print(f"\nResults written to {out_dir.resolve()}")
    return result


def selfish_analysis(runs: dict) -> list[dict]:
    """What download-1 gains by claiming 40 Mbps (it needs 4) during ticks 20-44, and what the honest users lose."""
    rows = []
    for mech in MECHANISMS:
        hist = runs.get(("selfish_user", mech))
        if not hist:
            continue
        before = [h for h in hist if h["tick"] < 20]
        lying = [h for h in hist if 20 <= h["tick"] < 45]

        def avg(hs, pick):
            return float(np.mean([pick(h) for h in hs]))

        liar = lambda h: next(u["rate"] for u in h["users"] if u["id"] == "download-1")
        others = lambda h: sum(u["rate"] for u in h["users"] if u["id"] != "download-1")
        utility_others = lambda h: sum(u["utility"] for u in h["users"] if u["id"] != "download-1")
        need = next(u["demand"] for u in hist[0]["users"] if u["id"] == "download-1")
        b, l = avg(before, liar), avg(lying, liar)
        rows.append({
            "mechanism": mech,
            "mechanism_label": MECHANISMS[mech]["label"],
            "liar_rate_honest": round(b, 3),
            "liar_rate_lying": round(l, 3),
            "liar_true_need": need,
            "wasted_mbps": round(max(0.0, l - need), 3),
            "gain_from_lying_pct": round(100 * (l - b) / b, 1) if b > 0 else 0.0,
            "honest_users_mbps_before": round(avg(before, others), 3),
            "honest_users_mbps_lying": round(avg(lying, others), 3),
            "honest_users_utility_change": round(avg(lying, utility_others) - avg(before, utility_others), 4),
        })
    return rows


def poa_analysis(scenarios: list[dict], every: int = 10) -> list[dict]:
    """Price of anarchy of the Kelly auction, sampled every `every` ticks of each scenario."""
    rows = []
    for sc in scenarios:
        sim = Simulation(sc["id"], "max_min")
        ratios = []
        while not sim.done:
            sim.step()
            if (sim.tick - 1) % every:
                continue
            users = list(sim.users.values())
            values = np.array([u.budget for u in users])
            x_eq = kelly_auction(users, sim.capacity)
            x_opt = social_optimum(users, sim.capacity, values=values, starts=[x_eq])
            ratios.append(price_of_anarchy(users, x_eq, x_opt, values))
        rows.append({"scenario": sc["id"], "samples": len(ratios), "mean_poa": round(float(np.mean(ratios)), 4),
                     "worst_poa": round(float(np.max(ratios)), 4),
                     "efficiency_pct": round(100 / float(np.max(ratios)), 1)})
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def make_charts(out_dir: Path, summary: list[dict], runs: dict, selfish: list[dict]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mechs = list(MECHANISMS)
    labels = [MECHANISMS[m]["label"] for m in mechs]
    scen = sorted({r["scenario"] for r in summary})
    names = {r["scenario"]: r["scenario_name"] for r in summary}
    colors = ["#2563eb", "#f97316", "#7c3aed", "#10b981", "#9ca3af"]

    for metric, title in [("jain_fairness", "Jain's fairness index (higher is fairer)"),
                          ("total_utility", "Total utility (higher is more efficient)"),
                          ("starved_users", "Users below their minimum rate (lower is better)")]:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        width = 0.16
        for j, m in enumerate(mechs):
            vals = [next(r[metric] for r in summary if r["scenario"] == s and r["mechanism"] == m) for s in scen]
            ax.bar(np.arange(len(scen)) + (j - 2) * width, vals, width, label=labels[j], color=colors[j])
        ax.set_xticks(np.arange(len(scen)), [names[s] for s in scen])
        ax.set_title(title)
        ax.legend(frameon=False, ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1))
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out_dir / f"{metric}.png", dpi=150)
        plt.close(fig)

    # fairness over time in the heavy-user scenario
    fig, ax = plt.subplots(figsize=(10, 4))
    for j, m in enumerate(mechs):
        hist = runs[("heavy_user_joins", m)]
        ax.plot([h["tick"] for h in hist], [h["metrics"]["min_satisfaction"] for h in hist], label=labels[j], color=colors[j])
    for t in (15, 35):
        ax.axvline(t, color="#999", ls="--", lw=0.8)
    ax.set_title("Heavy user joins: worst-off user's satisfaction over time (downloads join at 15 and 35)")
    ax.set_xlabel("tick")
    ax.set_ylabel("min satisfaction")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_dir / "heavy_user_over_time.png", dpi=150)
    plt.close(fig)

    # selfish user gain
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([r["mechanism_label"] for r in selfish], [r["gain_from_lying_pct"] for r in selfish],
           color=[colors[mechs.index(r["mechanism"])] for r in selfish])
    ax.set_title("Bandwidth gained by lying about demand (selfish user scenario)")
    ax.set_ylabel("% more bandwidth than when honest")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_dir / "selfish_gain.png", dpi=150)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="results")
    p.add_argument("--no-charts", action="store_true")
    a = p.parse_args()
    run_all(Path(a.out), charts=not a.no_charts)


if __name__ == "__main__":
    main()
