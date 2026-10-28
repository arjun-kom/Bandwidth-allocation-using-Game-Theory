# Game-Theoretic Bandwidth Allocation

**Team:** Komban Arjun (24BDS0244) and Syed Arshudeen (24BCE2307)

One network link, many users with different needs. Every Mbps one user gets is taken from someone
else, so this project treats bandwidth sharing as a **game** between users and compares
game-theoretic ways of splitting the link against simple baselines.

It has a pure-Python game theory core, a time-stepped network simulator, an experiment runner that
produces the tables and charts for the report, a FastAPI server and a live React dashboard. It all
ships as one Docker container.

## Run it (Windows, PowerShell)

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) running.

```powershell
cd bandwidth-allocation
.\run.ps1                 # or: docker compose up --build
```

`run.ps1` uses port 8080, or the next free port if 8080 is taken (`.\run.ps1 -Port 9000` picks one yourself).
With plain `docker compose`, set the port first: `$env:PORT=9000; docker compose up --build`.

The first build takes a few minutes, because it runs the tests and pre-computes every experiment.
After that, open:

- Dashboard: http://localhost:8080
- API docs (Swagger): http://localhost:8080/docs

Stop it with `docker compose down`. Your run history is kept in a Docker volume.

## What you can do in the dashboard

| Tab | What it shows |
| --- | --- |
| Live simulation | Pick a scenario and a mechanism and watch the link re-balance every tick. While it runs you can switch mechanisms, add users with a priority weight, make a user lie about its demand, remove users, or shrink the link. |
| Compare mechanisms | Edit a list of users and see what all five mechanisms give each of them, side by side, with a fairness and efficiency scorecard. |
| Experiments | Every scenario run with every mechanism, plus the selfish-user and price-of-anarchy studies and the charts for the report. You can re-run them from here. |
| Run history | Every live run is saved to SQLite with its average metrics. |
| How it works | The game, the user types, the mechanisms and the metrics, explained. |

## The game

- **Players**: users on the link. Each has a demand `d`, a minimum rate `m`, a priority weight and a budget.
- **Utility** (normalised to 0..1):
  - elastic traffic (web, downloads): `log(1 + x) / log(1 + d)`, any bandwidth helps with diminishing returns;
  - inelastic traffic (video, gaming, calls): a sigmoid around `m`, almost useless below the minimum.
- **Constraint**: `x1 + ... + xn <= C`.

| User type | Traffic | Min rate | Default demand |
| --- | --- | --- | --- |
| Video streaming | inelastic | 5 Mbps | 8 Mbps |
| Online gaming | inelastic | 2 Mbps | 3 Mbps |
| Video call | inelastic | 3 Mbps | 4 Mbps |
| Web browsing | elastic | none | 2 Mbps |
| File download | elastic | none | 25 Mbps |

## Mechanisms

| Mechanism | Kind | How it works | File |
| --- | --- | --- | --- |
| Nash bargaining | cooperative | Maximises `sum log(x_i - m_i)`. Closed form `x_i = min(d_i, m_i + lambda)`: every user gets its minimum, then the spare capacity is shared equally (Yaiche, Mazumdar and Rosenberg, 2000). If the minimums do not fit, users are admitted by priority. | `core/mechanisms/nash_bargaining.py` |
| Kelly auction | non-cooperative | Users bid money and get `C * bid / sum(bids)`. Each user plays best response (payoff = budget x utility - bid) until no one wants to change: a Nash equilibrium (Kelly, 1997; Johari and Tsitsiklis, 2004). | `core/mechanisms/kelly.py` |
| Weighted priority | cooperative | Weighted Nash bargaining: `x_i = min(d_i, m_i + w_i * lambda)`, and high-weight users are admitted first. | `core/mechanisms/priority.py` |
| Max-min fair | baseline | Water-filling up to each user's demand. | `core/mechanisms/baselines.py` |
| Equal share | baseline | `C / n` each, capped at demand; the leftover is wasted. | `core/mechanisms/baselines.py` |

With sigmoid utilities a pure equilibrium of the Kelly game may not exist (users with all-or-nothing
needs can keep switching between giving up and bidding for their minimum). The solver uses a
shrinking step size, and if it still has not settled after 120 rounds it uses the time-average of the
last 20 rounds of bids. The dashboard shows whether a tick reached an equilibrium.

## Metrics

| Metric | Meaning |
| --- | --- |
| Jain fairness | `(sum s)^2 / (n * sum s^2)` over satisfaction ratios `s = x/d`; 1 means everyone gets the same share of what they need |
| Total utility | `sum U(x)`, the efficiency of the split |
| Mean / worst satisfaction | share of demand met, on average and for the worst-off user |
| Below minimum | inelastic users below their minimum rate (their app does not work) |
| Useful utilisation | share of the link that goes to real demand, not to lies or waste |
| Price of anarchy | optimal total value / value at the Kelly equilibrium |

## Results (from `python -m experiments.run_all`)

Averaged over all ticks of each run:

| Scenario | Best fairness | Best total utility | Users below minimum, Nash bargaining vs max-min |
| --- | --- | --- | --- |
| Light load | all tie at 1.00 | all tie at 7.00 | 0 vs 0 |
| Peak hour | Max-min 0.83 | Kelly 15.2 | **0 vs 7.8** |
| Heavy user joins | Kelly 0.90 | Nash bargaining 9.39 | 0 vs 0 |
| Selfish user | Max-min 0.90 | Kelly 8.21 | 0 vs 0 |
| Priority traffic | Max-min 0.76 | Kelly 8.46 | **0 vs 4.3** |

Selfish user (download-1 needs 4 Mbps but claims 40):

| Mechanism | Extra bandwidth the liar gets |
| --- | --- |
| Kelly auction | **0%**, because the bid depends only on what the user really values |
| Equal share | 11% |
| Nash bargaining / weighted priority | 17% |
| Max-min fair | 50% |

Findings in one line each:

1. **Nash bargaining never leaves an inelastic app below its minimum rate** while capacity allows it, whereas max-min and equal share break up to 8 video or gaming users at peak hour.
2. **The Kelly auction is the most efficient and cannot be gamed by lying**, but at peak hour it lets about 3 low-budget users fall below their minimum.
3. **Selfishness is cheap here.** The measured price of anarchy is between 1.00 and 1.02 (at least 97.8% efficiency), well inside the theoretical 1.33 bound.
4. Max-min looks fairest on Jain's index but is the easiest to cheat, and its "fair" split often gives video users too little to play anything.

## Run without Docker

Python 3.11 or newer, and Node 20 or newer.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest                              # 48 tests
python -m experiments.run_all --out results   # tables + charts into results/
uvicorn api.main:app --reload                 # API on http://localhost:8000

# in a second terminal, for the dashboard with hot reload
cd dashboard
npm install
npm run dev                                   # http://localhost:5173 (proxies to the API)
```

## Project layout

```
bandwidth-allocation/
  core/                 game theory core (no web code)
    models.py           user types, utility functions
    mechanisms/         nash_bargaining.py, kelly.py, priority.py, baselines.py, waterfill.py
    metrics.py          fairness, utility, satisfaction, price of anarchy
    optimum.py          social optimum (yardstick for the price of anarchy)
    allocate.py         allocate(users, capacity, mechanism) -> Allocation
  sim/
    engine.py           time-stepped simulator: join, leave, change demand, lie
    scenarios/          light_load, peak_hour, heavy_user_joins, selfish_user, priority_traffic
  experiments/
    run_all.py          every scenario x every mechanism -> CSV, JSON, PNG charts
  api/
    main.py             FastAPI: REST + WebSocket /ws/simulate, serves the dashboard
    storage.py          SQLite run history
  dashboard/            React + TypeScript + Vite + Recharts
  tests/                pytest: core, simulator, API
  docs/                 API and team notes
  Dockerfile            node build stage + python runtime
  docker-compose.yml
  run.ps1
```

## API at a glance

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/health` | health check |
| GET | `/api/meta` | user types, mechanisms, scenarios |
| POST | `/api/allocate` | one allocation: `{capacity, mechanism, users:[{id, type, demand?, weight?, budget?, reported_demand?}]}` |
| POST | `/api/compare` | the same users under every mechanism |
| GET | `/api/experiments` | cached experiment results and chart names |
| POST | `/api/experiments/run` | re-run all experiments in the background |
| GET | `/api/runs`, `/api/runs/{id}` | saved live runs |
| WS | `/ws/simulate` | live simulation; see `docs/api.md` for the messages |

## Adding a scenario

Drop a JSON file into `sim/scenarios/` and it shows up in the dashboard and the experiments:

```json
{
  "name": "My scenario", "description": "...", "capacity": 50, "ticks": 60,
  "demand_noise": 0.1, "seed": 7,
  "users": [{"type": "video", "count": 4}, {"type": "download", "count": 2, "budget": 30}],
  "events": [
    {"tick": 10, "action": "join", "type": "call", "weight": 5},
    {"tick": 20, "action": "set", "id": "download-1", "params": {"reported_demand": 100}},
    {"tick": 30, "action": "leave", "type": "video", "count": 2},
    {"tick": 40, "action": "capacity", "value": 30}
  ]
}
```

## Team split

| Member 1: Komban Arjun (24BDS0244), game theory core | Member 2: Syed Arshudeen (24BCE2307), simulation and dashboard |
| --- | --- |
| `core/` (models, mechanisms, metrics, optimum) | `sim/` (engine, scenarios) |
| `experiments/` and the report charts | `api/` (REST, WebSocket, SQLite) |
| unit tests for every mechanism | `dashboard/` (React) |
| theory and results chapters | architecture and demo chapters, Docker |

## References

- F. Kelly, "Charging and rate control for elastic traffic", European Transactions on Telecommunications, 1997.
- R. Johari and J. Tsitsiklis, "Efficiency loss in a network resource allocation game", Mathematics of Operations Research, 2004.
- H. Yaiche, R. Mazumdar and C. Rosenberg, "A game theoretic framework for bandwidth allocation and pricing in broadband networks", IEEE/ACM Transactions on Networking, 2000.
- R. Jain, D. Chiu and W. Hawe, "A quantitative measure of fairness and discrimination for resource allocation in shared computer systems", DEC TR-301, 1984.
