"""Natural conversational answers about the project itself.

The live-data path already talks like a person (see ``prompts.build_fallback``).
Questions about *the project* took a different route: they were answered by
pasting raw documentation sections into the chat, prefixed with
``[docs: docs/architecture.md - Architecture]`` and followed by a disclaimer
that no language model was configured. That reads like a search result, not a
conversation, and it makes the assistant look like it cannot talk about its own
system.

This module is the offline equivalent of what the LLM path does with the same
retrieved chunks. It answers in Raga's voice, using the project's real
architecture, and it keeps the honesty rules in ``prompts.SYSTEM_PROMPT``:
demo data is called demo data, and routes are never called safe.

Everything here is grounded in ``docs/*.md`` and ``README.md`` in this
repository. Nothing is invented, and each briefing names the document it came
from so the user can go read the real thing.
"""
from __future__ import annotations

import re

# --------------------------------------------------------------------------
# Topic detection
# --------------------------------------------------------------------------

_TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "sea_ice",
        (
            "how sea-ice forecasting works", "how sea ice forecasting works",
            "sea ice forecasting", "sea-ice forecasting", "sea ice pipeline",
            "sea-ice pipeline", "explain sea-ice forecast", "explain sea ice forecast",
            "sea ice forecast model", "how does sea-ice forecasting work",
            "how does sea ice forecasting work",
        ),
    ),
    (
        "icebergs",
        (
            "iceberg tracking system", "iceberg drift model", "how are icebergs tracked",
            "how does iceberg tracking work", "explain iceberg drift",
            "trajectory prediction model", "calving mechanism",
        ),
    ),
    (
        "navigation",
        (
            "navigation algorithm", "route engine", "routing algorithm", "astar", "a*",
            "pathfind", "path planning", "route optimization", "how is the route generated",
            "route generation", "how does a* work", "navigation system",
        ),
    ),
    (
        "route_change",
        (
            "why did the route change", "route change", "why route changed",
            "recalculation work", "re-route", "reroute", "recalculate the route",
            "live route recalculation", "re-plan", "replan",
        ),
    ),
    (
        "risks",
        (
            "detect navigation risks", "navigation risk", "hazard detection",
            "how does the system detect navigation risks", "detect risk",
            "risk detection", "risk scoring", "risk grid", "hazard envelope",
        ),
    ),
    (
        "alerts",
        (
            "alert system", "how does the alert system work", "why did i receive this alert",
            "alert engine", "alert message", "how do alerts work", "hazard warning",
            "explain the current alerts",
        ),
    ),
    (
        "data",
        (
            "dataset", "datasets", "data", "datastore", "netcdf", "csv", "nc file",
            "source", "sources", "download", "acquisition", "synthetic", "demo data",
            "real data", "satellite", "nsidc", "copernicus", "oscar", "era5",
            "bathymetry", "land mask", "provenance", "freshness", "cadence",
            "what datasets", "which datasets",
        ),
    ),
    (
        "models",
        (
            "ai/ml models", "what models", "model", "models", "ml", "machine learning",
            "train", "training", "trained", "convlstm", "lstm", "random forest",
            "random_forest", "persistence", "checkpoint", "mae", "rmse", "accuracy",
            "prediction", "predict", "forecast model", "inference",
        ),
    ),
    (
        "journey",
        (
            "journey", "voyage", "simulation", "simulate", "advance", "two hours",
            "2 hours", "time step", "timestep", "rolling loop", "leg", "itinerary",
        ),
    ),
    (
        "frontend",
        (
            "frontend", "front-end", "react", "vite", "tailwind", "leaflet",
            "recharts", "component", "components", "typescript", "page", "pages",
            "ui", "interface", "map", "3d globe", "globe", "chart", "button",
        ),
    ),
    (
        "api",
        (
            "api", "endpoint", "endpoints", "rest api", "openapi", "swagger",
            "backend api", "server", "port 8000", "port 8001", "uvicorn",
            "fastapi", "request", "response", "json", "/api",
        ),
    ),
    (
        "limitations",
        (
            "limitation", "limitations", "weakness", "weaknesses", "risk of use",
            "honest", "honesty", "accurate?", "reliable", "can i trust", "trust",
            "problem", "problems", "issue", "issues", "caveat", "caveats",
            "safe to use", "production", "ready", "broken", "wrong",
        ),
    ),
    (
        "setup",
        (
            "install", "setup", "set up", "run the app", "how do i start",
            "how to start", "run it", "launch", "start the server", "localhost",
            "how do i run", "getting started", "launcher",
        ),
    ),
    (
        "architecture",
        (
            "complete architecture", "architecture", "architect", "structure",
            "system design", "how is it built", "how was it built", "codebase",
            "repo", "repository", "folder", "directory", "layout", "modules",
            "tiers", "stack", "tech stack", "technology", "designed", "organized",
        ),
    ),
)

# A question that wants the whole system described.
_OVERVIEW_RE = re.compile(
    r"^\s*(?:"
    r"(?:can\s+you\s+)?(?:tell\s+me|describe|explain|give\s+me|summar\w*|walk\s+me)"
    r"[\w\s,.'-]*?"
    r"(?:about\s+)?"
    r"|what(?:'s|\s+is|\s+are|\s+was)?\s+"
    r"|who\s+are\s+you|"
    r"introduce\s+"
    r")"
    r"(?:this|your|the|our|whole|entire|full|complete)?\s*"
    r"(?:project|system|app|application|dashboard|product|codebase|dss|software)\b"
    r"(?:.*)?\??\s*$",
    re.I,
)

_BROAD_RE = re.compile(
    r"\b(everything about|all about|whole project|entire project|overview of the project|"
    r"explain the project|describe the project|what is this project|what are you|"
    r"what can you do|help me understand the project)\b",
    re.I,
)

# Short turns that lean on the previous answer rather than naming a topic.
# Deliberately narrow: "how does the route engine work?" is a real question and
# must not be mistaken for a bare "how?".
_FOLLOWUP_RE = re.compile(
    r"^\s*(?:"
    r"(?:and|but|what about|how about|tell me more|go on|continue|anything else)\b.*"
    r"|(?:more|details?|elaborate|expand|keep going)\s*\??"
    r"|(?:why|how|really|and|so)\s*\??"
    r"|explain\s*\??"
    r")\s*$",
    re.I,
)


def detect_topic(question: str) -> str:
    """Which part of the project the user is asking about.

    Returns one of ``data``, ``models``, ``navigation``, ``journey``,
    ``frontend``, ``api``, ``limitations``, ``setup``, ``architecture``, or
    ``overview`` for "what is this thing".
    """
    return _matched_topic(question) or "overview"


def _matched_topic(question: str) -> str:
    """The topic this question names outright, or ``""`` if it names none."""
    q = (question or "").lower()
    best_topic, best_score = "", 0
    for topic, words in _TOPICS:
        score = sum(2 if " " in w else 1 for w in words if w in q)
        if score > best_score:
            best_topic, best_score = topic, score
    return best_topic


def is_followup(question: str) -> bool:
    """True for "why?", "tell me more" - a turn that leans on the last answer."""
    return bool(_FOLLOWUP_RE.match((question or "").strip()))


def looks_like_project_question(question: str, history: list[dict] | None = None) -> bool:
    """True when the user is asking about the project, not about live data.

    Covers three shapes the keyword lists miss: a request for the whole system
    ("explain everything"), a question that names one of the areas directly
    ("how does A* work", "what's in the model pipeline"), and a bare follow-up
    ("tell me more") that only makes sense against the last turn.
    """
    q = (question or "").strip()
    if not q:
        return False
    if is_followup(q):
        return _last_topic(history or []) is not None
    if _OVERVIEW_RE.match(q) or _BROAD_RE.search(q):
        return True
    return detect_topic(q) not in ("", "overview")


# --------------------------------------------------------------------------
# The briefings
# --------------------------------------------------------------------------

_OVERVIEW = """\
This is your Antarctic navigation decision-support system, and I work inside it.

It does three things. It watches the sea ice, it forecasts where icebergs are \
drifting, and it plans ship routes through both. Everything runs locally on one \
machine, and the dashboard you're looking at is the only interface.

**The stack is three tiers.** A React + TypeScript frontend with Tailwind and \
Leaflet runs on port 5173 and talks to the backend through the Vite dev proxy. A \
FastAPI backend runs the unified REST surface under `/api` on port 8000. \
Underneath both sits a local data and ML layer that holds the processed \
datasets, the route engine, and the trained model artifacts. Data lands in \
SQLite through SQLAlchemy, and the navigation engine itself is pure numpy.

**The pages**, left to right: Overview, Sea-Ice Forecast, Iceberg Tracking, \
Navigation Planner, Alerts, Analytics, and this assistant. The map component \
renders the sea-ice grid as a canvas overlay, drops iceberg markers on it, and \
draws route polylines over the top.

**The simulation is the interesting part.** You pick a port, a station and a \
vessel and start a voyage. From then on the loop runs every two simulated \
hours: the vessel advances along the route, the engine pulls the closest valid \
observation set, rebuilds the risk grid, and re-plans from the *current* \
position rather than snapping back to the departure port. Distance, fuel, \
duration and risk all get recomputed each pass, and a counter ticks up so you \
can see how often the route changed.

**On honesty, because it matters here:** the data currently shipping is \
synthetic demo data, and the app labels it as such everywhere you see it. The \
model checkpoints on disk were trained on that demo data, so their metrics are \
code-path checks, not real skill. A route from this system is decision support \
- it is never a guarantee of safety. That's not hedging, it's the actual state \
of the thing.

Want me to take any layer apart? I can go deep on the architecture, the data \
and where it comes from, the two model pipelines, the route engine and how risk \
is scored, the two-hour loop, the API surface, or the honest limitations.
"""

_SEA_ICE = """\
The Antarctic sea-ice forecasting pipeline operates across multiple spatial and temporal scales:

**1. Data Ingestion & Spatial Grid**
The system ingests gridded polar stereographic and circumpolar sea-ice concentration (SIC) fields covering latitude -50 deg S to -90 deg S at 81x1440 resolution. In operational mode, observations derive from NOAA/NSIDC Climate Data Record (CDR) passive microwave satellite sensors (SSMIS / AMSR2).

**2. Forecast Models (`backend/ml/` & `services/sea_ice_service.py`)**
The platform runs three model families to predict ice evolution:
- **Persistence Baseline**: Assumes no temporal change (SIC at t+h equals SIC at t). Highly competitive at short 6h–24h horizons and serves as the benchmark against which ML skill is evaluated.
- **Random Forest Regressor**: Tabular per-cell prediction incorporating historical concentration changes, ocean surface current velocity, sea surface temperature, and atmospheric 10m wind forcing.
- **ConvLSTM Neural Network**: Deep spatiotemporal PyTorch architecture ingesting multi-step historical frames `[batch, time, height, width, features]` to capture spatial advection and thermodynamic freezing/melting dynamics.

**3. Forecast Horizons & Derived Intelligence**
Forecasts are generated for **6, 12, 24, 48, 72, 120, and 168 hours**. From the predicted concentration grids, derived intelligence products are computed:
- Sector-wide mean and maximum sea-ice concentration.
- Spatial sea-ice extent (cells with concentration >= 15%).
- First-order ice thickness proxies and subsurface keel depth clearance against bathymetry.
- Melt pond fraction indicators and freeze/thaw transition risk zones."""

_ICEBERGS = """\
The iceberg tracking and trajectory subsystem monitors drifting ice hazards across the Southern Ocean:

**1. Detection & Tracking Database**
Icebergs are tracked from the Antarctic Iceberg Tracking Database (National Ice Center / BYU scatterometer records). Each tracked iceberg carries an identifier (e.g., A23A, B15), timestamped GPS coordinates, estimated length and width, and historical observation trajectories.

**2. Drift Dynamics & Trajectory Models**
Iceberg drift is governed by hydrodynamic ocean drag and atmospheric wind stress:
- **Coriolis Effect**: In the Southern Hemisphere, icebergs deflect 20° to 30° to the left of the prevailing wind direction.
- **4-Model Predictive Ladder**:
  1. *Persistence*: Berg remains stationary.
  2. *Current-Drift*: Advects the iceberg at ocean surface current velocities.
  3. *Random Forest*: Predicts independent zonal (u) and meridional (v) displacement steps from environmental vectors.
  4. *Stacked LSTM*: Recurrent neural network capturing inertia and multi-step drift over 24h, 48h, and 72h horizons.

**3. Integration with Navigation Routing**
Tracked and predicted iceberg positions are projected onto the navigation risk grid. Icebergs generate dynamic **No-Go exclusion buffers** (10 km critical radius) and surrounding precautionary risk gradients, ensuring routes maintain safe navigational clearance."""

_RISKS = """\
The Antarctic Navigation DSS detects and quantifies navigation hazards through continuous multi-layer risk modeling:

**1. Sea-Ice Risk Assessment**
- Evaluates gridded concentration against vessel-specific structural capabilities (Polar Code categories PC1 to PC7).
- Estimates sea-ice thickness and subsurface keel depth clearance against shallow bathymetric features.
- Flags divergence/convergence zones where dynamic ice pressure poses besetting risks.

**2. Iceberg Hazard Envelopes**
- Maintains dynamic clearance envelopes: **Critical (<10 km)**, **Warning (<25 km)**, and **Advisory (<50 km)**.
- Combines historical positions with multi-step LSTM predicted drift trajectories to anticipate corridor intersections.

**3. Real-Time Alert Engine**
The system evaluates all active route waypoints against current and forecast hazard fields. Any threshold violation instantly generates prioritized maritime alerts with recommended avoidance actions."""

_ALERTS = """\
The DSS Alert Engine provides continuous situational awareness and hazard notifications:

**1. Hazard Classification**
- **Critical Alerts**: Hard safety threshold breaches, such as an iceberg predicted within 10 km of the route or sea-ice concentration exceeding the vessel's Polar Class limit.
- **Warning Alerts**: Moderate hazards, such as deteriorating weather or sea ice expanding into the secondary route corridor (25 km buffer).
- **Advisory Alerts**: Informational updates on newly calved icebergs, forecast model updates, or route recalculation events.

**2. Alert Content**
Each alert includes:
- Severity level (Critical, Warning, Advisory).
- Specific hazard cause and distance to the vessel/route.
- Affected route identifier.
- Recommended navigational action (e.g., speed reduction, route recalculation, course deviation)."""

_ROUTE_CHANGE = """\
Route recalculation in this system is driven by a live 2-hour operational loop:

**1. Rolling Loop Execution**
Every 2 simulated hours:
- The vessel advances along its active track toward the destination.
- Updated environmental fields (new sea-ice concentration forecasts and iceberg drift vectors) are ingested.
- The navigation risk grid is dynamically rebuilt.

**2. Re-planning from Live Position**
Crucially, recalculation is executed from the **vessel's current live coordinates** (lat, lon) rather than resetting to the departure port. If an iceberg drifts into the planned corridor or sea ice expands, the engine recalculates a detour around the hazard while continuing toward the destination.

**3. Route Update Tracking**
Each change increments the voyage's `route_update_count`, recomputing remaining distance, fuel consumption, and ETA."""

_ARCHITECTURE = """\
Three tiers, all local.

**Frontend** (`frontend/`) - React, TypeScript, Vite, Tailwind, Leaflet, \
Recharts. It runs on port 5173 and proxies `/api` to the backend. Pages are \
Overview, Sea-Ice Forecast, Iceberg Tracking, Navigation Planner, Analytics and \
the assistant. `AntarcticMap.tsx` is the one worth knowing about: it draws the \
sea-ice grid as a canvas overlay, places the iceberg markers, and draws the \
route polylines.

**Backend** - and this is the slightly unusual part, there are two FastAPI \
applications. `backend/main.py` is the unified REST API on port 8000 under \
`/api`; it's what the dashboard actually calls, and it's what `run.ps1` starts. \
`backend/app/main.py` is a second, legacy application on port 8001 under \
`/api/v1`, and it owns the voyage lifecycle - start, advance, recalculate, \
status. They share the same services in the same process space, they're just \
separate uvicorn entry points.

**Shared core**, used by both: `navigation/` is the pure-numpy engine (grid, \
risk engine, A* planner, route optimizer, fuel estimator, geodesy, land mask). \
`services/` holds the sea-ice, iceberg, navigation, dataset, analytics and \
provenance services. `ml/` holds the two forecasting pipelines. `data_pipeline/` \
does acquisition, validation and reporting. `database/` is SQLAlchemy over \
SQLite, storing dataset inventory, analytics metrics and route snapshots.

At runtime it reads artifacts off disk: processed datasets under \
`backend/datasets/`, trained checkpoints under `backend/models/`, and JSON \
config in `backend/app/data/config/`.

The layering rule is that the frontend never computes anything the backend can \
compute - routes, risk and analytics all come from services, not from hard-coded \
values in the UI."""

_DATA = """\
Everything lands in `backend/datasets/processed/` and the running services read \
it from there directly.

**The real sources**, when credentials are configured: NSIDC Sea Ice Index and \
Copernicus Marine for concentration, NSIDC G00803 and the US National Ice \
Center for iceberg tracks, NASA OSCAR and Copernicus Marine for ocean surface \
fields, and ECMWF ERA5 for weather. The Antarctic land mask is the one piece \
that ships real - a pre-aligned numpy `.npy` used to exclude land cells from \
navigation.

**When there are no credentials**, the pipeline generates synthetic demo data \
instead. This is what your app is running on right now, and it's stamped \
`classification: synthetic_demo` on every artifact. A `real` or `auto` run will \
never silently reuse a demo file - it logs a warning and regenerates from the \
real source.

**The files themselves**: `sea_ice.nc` holds concentration over time, latitude \
and longitude. `ocean_surface.nc` has the currents and temperature. \
`weather_surface.nc` has wind and pressure. Icebergs come in as `icebergs.csv` \
when real, with `icebergs_demo.*` as the fallback - the service layer prefers \
the real CSV whenever it's present.

One thing worth knowing: the observation cadence doesn't match the simulation. \
Real fields are daily for sea ice and ocean, 6-hourly for ERA5. But the voyage \
loop advances every 2 hours. So the accessor serves the *closest* valid \
observation and carries provenance metadata about which one it picked and how \
far off the timestamp was. It never claims a daily field is 2-hourly.

`GET /api/datasets/status` tells you what's actually loaded per domain, and the \
aggregate `real_data_available` flag is false until genuine data is serving \
something."""

_MODELS = """\
Two pipelines, both in `backend/ml/`, both writing to `backend/models/`.

**Sea ice** reads `sea_ice.nc` and has three models. Persistence is the baseline \
- tomorrow equals today. Random Forest works per cell on tabular features: SIC \
history and change, ocean temperature and currents, wind, and time. ConvLSTM is \
the PyTorch one, taking `[batch, time, height, width, features]` and predicting \
the next concentration field. Training is strictly chronological, scalers are fit \
on train only and saved with the model, invalid grid cells are masked out of the \
loss, and there's early stopping and a reproducibility seed.

At runtime `SeaIceRuntime.grid_predict()` serves the model's native **24 hour** \
step through `/api/sea-ice/predict` and `/api/sea-ice/forecast`. If the \
checkpoint is missing or malformed it reports `available: false` and everything \
falls back to persistence rather than failing.

**Icebergs** is a four-model ladder. Persistence leaves the berg where it is. \
Current-drift advects it at the observed ocean current. Random Forest runs two \
independent forests, one for X and one for Y. LSTM is a stacked recurrent model \
with a fully-connected head doing recursive multi-step forecasting. Features per \
timestep are position, velocity, ocean currents, wind, berg length and width, \
and day-of-year as sine and cosine. `IcebergRuntime` does this recursively at a \
**6 hour** reference step.

The honesty part matters here. The checkpoints currently on disk were trained on \
synthetic demo data and are flagged `trained_on_demo: true`. Their metrics are \
code-path checks - they prove the training path runs, nothing more. On this demo \
data persistence frequently beats the ML models at multi-step horizons, because \
the synthetic tracks don't drift realistically. Nothing gets fabricated to hide \
that: `/api/models/status` lists exactly what's on disk, and the Analytics page \
renders only what the registry reports."""

_NAVIGATION = """\
The engine is `backend/navigation/`, and it's deliberately dependency-light - \
pure numpy, no solver library.

**The grid** covers latitude −85° to −55° and all longitudes, at 0.5° \
resolution, in an equirectangular projection called `AntarcticGrid`. Land cells \
are excluded up front using the numpy mask.

**Risk** is built by `RiskEngine` from four layers. Sea-ice concentration maps \
to a risk weight against the vessel's ice class - a PC5 vessel, for example, has \
a 60% concentration ceiling. Icebergs contribute *hard* No-Go blocks rather than \
weights: if a known berg's closest approach falls below a threshold, those cells \
become impassable, not merely expensive. Then weather severity, then the vessel's \
own constraint layers.

**Pathfinding** is A* over that risk-weighted cost field, treating the No-Go \
cells as obstacles. When there's genuinely no path it raises \
`NoPathFoundError` rather than returning something bad.

`RouteOptimizer` produces the four route types you see in the UI - shortest, \
safest, fuel-efficient, and the recommended blend - and distances are summed \
haversine between waypoints. `RouteValidator` checks the result. Fuel and \
duration come from `FuelEstimator` reading the actual vessel record (ice class, \
speed, fuel model) rather than any hard-coded rate, which is why a different \
ship gets a different number.

Thresholds and the objective weights live in \
`backend/app/data/config/navigation.json` and `simulation.json`, so you can tune \
the trade-off without touching code."""

_JOURNEY = """\
The voyage lifecycle lives in the legacy `/api/v1` surface, and it's the part of \
the system that makes the dashboard feel alive.

`POST /api/v1/navigation/journey` starts one. You give it a departure port, a \
destination, a `journey_mode` of `outbound` (port to centre) or `return` (centre \
to port), and a `position_mode`. Simulation mode is self-contained. Live mode \
refuses with a 400 until you feed it an actual fix through the recalculate \
endpoint - there is no GPS feed wired up.

Then there's the **two-hour rolling loop**. At every \
`SIMULATION_TIME_STEP_HOURS = 2` boundary, five things happen in order: the \
vessel advances along the current route, the closest valid observation set is \
reloaded with its provenance, the risk grid is rebuilt, the route is re-planned \
**from wherever the vessel actually is now**, and distance, fuel, duration and \
risk are recomputed while a `route_update_count` ticks up.

That third-from-last point is the one that matters. The re-plan never resets to \
the departure port. It treats the current position as the new origin and keeps \
the destination fixed. That's why the route visibly bends as the voyage goes on, \
and it's also why a route can change even in demo mode where the environmental \
fields are static - you're watching recalculation, not a genuinely changing risk \
field.

`GET .../status` gives you position, elapsed `current_time_hours`, \
`remaining_distance_nm`, `progress_percent`, fuel, and `is_complete`. One quirk to \
know about: because a destination snaps to the centre of its 0.5° cell, an \
arriving vessel keeps a small residual distance while `is_complete` is true."""

_FRONTEND = """\
The frontend is React with TypeScript, built by Vite, styled with Tailwind, and \
it maps with Leaflet. It runs on port 5173 in dev and forwards `/api` to the \
backend through the Vite proxy, so there are no CORS problems to think about.

The pages are Overview, Sea-Ice Forecast, Iceberg Tracking, Navigation Planner, \
Alerts, Analytics, and the assistant you're talking to. Sidebar navigation \
switches between them - it's a state-driven shell, not a router, which is why \
page changes are instant.

`AntarcticMap.tsx` is the component that does the real work. It renders the \
sea-ice concentration grid as a canvas overlay rather than thousands of DOM \
nodes, places the iceberg markers with their drift trajectories, and draws the \
route polylines. `Antarctic3DGlobe.tsx` is the heavier optional view.

State that more than one page needs - the forecast horizon, which iceberg is \
selected, which vessel is active - lives in `AppContext` so the assistant, the \
planner and the map always agree. Page-local state stays local.

Worth flagging: the alert log is generated in the browser from live state, not \
by a backend endpoint. That's why I can explain an alert to you but there's no \
`/api/alerts` to point at."""

_API = """\
Two surfaces, and the dashboard only uses one of them.

**The unified API** is `backend/main.py` on port 8000 under `/api`. This is the \
primary one - what the React app actually calls. The routers cover health, \
datasets, sea-ice, icebergs, routes, vessels, analytics, models/status and the \
assistant. Everything it returns is honest about provenance: demo responses are \
flagged `demo=true` with a warning, model responses say whether the model was \
trained on real data, and the analytics summary carries `real_data_available`.

**The legacy journey API** is `backend/app/main.py` on port 8001 under \
`/api/v1`. It exists for the voyage lifecycle - journey start, advance, \
recalculate, status - plus its own sea-ice, iceberg and route modules. It's kept \
for compatibility.

Both share the same service layer in the same process, they're just separate \
uvicorn entry points. `run.ps1` starts the unified one.

The routes you'll actually hit from the dashboard: `/api/health`, \
`/api/datasets`, `/api/datasets/status`, `/api/sea-ice/current`, \
`/api/sea-ice/forecast`, `/api/sea-ice/intelligence/*`, `/api/icebergs`, \
`/api/icebergs/predict`, `/api/routes/optimize`, `/api/vessels`, \
`/api/analytics/summary`, `/api/models/status`, and `/api/assistant/chat`.

Interactive docs are at `http://localhost:8000/docs`, and the raw schema at \
`/openapi.json`."""

_LIMITATIONS = """\
I'd rather you hear these from me than find them later.

**The data is synthetic.** Every observation currently feeding the app is \
labelled demo data, and `real_data_available` is false. No real navigation \
decision should come out of this. Real sources (NSIDC, Copernicus, OSCAR, ERA5) \
are wired up and will be used the moment credentials exist, but they aren't being \
ingested right now.

**The models prove nothing about skill.** The checkpoints are trained on that \
demo data. On synthetic tracks, persistence often beats Random Forest and LSTM at \
multi-step horizons because the demo drift is unrealistic. The metrics are \
code-path checks, and the app says so rather than dressing them up.

**The grid clamps northern ports.** It only covers −85° to −55° latitude. Hobart \
at −42.9°, Cape Town at −33.9° and Ushuaia at −54.8° all sit outside it, so a \
route from those ports starts at the grid edge instead. The reported \
`total_distance_nm` is the in-grid length, which is *shorter* than the true \
great-circle distance - Hobart to McMurdo reads about 1,483 nm when the real \
distance is around 2,151 nm. That gap is a grid artifact, not a shortcut.

**Destinations snap to cell centres.** A 0.5° cell is roughly 30 nm across, so \
an arriving vessel keeps a small residual distance while `is_complete` is true. \
Recalculating exactly at the destination can produce a zero-distance \
single-waypoint route reading 0% progress on a finished journey.

**No GPS.** `position_mode: "live"` returns a 400 until a real fix is supplied \
through the recalculate endpoint. Simulation mode is the only fully working path.

**Demo fields don't change.** Between 2-hour steps the demo sea-ice and iceberg \
fields are static, so the re-routing you see in the demo is recalculation from a \
new position rather than a response to genuinely changing risk. Live fields would \
re-route on change; that's untested against real data.

**Single machine.** SQLite, in-memory journey state (a restart loses your \
voyages), no auth, no horizontal scaling. And the A* planner runs synchronously \
over a 61 × 721 cell grid, which is fine locally and would not be fine under
concurrent load.

The bottom line: this is a decision-support tool with an honest labelling \
system, not a certified navigation system. Real voyages need qualified crew, \
official charts and ice briefings."""

_SETUP = r"""
From the project root, one command:

```powershell
.\run.ps1
```

It creates or refreshes the Python virtual environment in `.venv`, installs the backend dependencies from `backend/requirements.txt` if needed, installs the frontend packages from `frontend/package.json` if needed, then starts both servers. After the first run you can skip the install step:

```powershell
.\run.ps1 -SkipInstall
```

The backend comes up on `http://localhost:8000` and the frontend on `http://localhost:5173`. The frontend reaches the backend through the Vite proxy, so open the frontend URL, not the backend one. Backend initialises the database and seeds resources on startup.

To run them separately, the backend is `python -m uvicorn main:app --reload --port 8000` from `backend/`, and the frontend is `npm run dev` from `frontend/`.

For real-data evaluation there's `.\run_accuracy.ps1`, which drives the evaluation and reporting pipeline. Dataset work has its own scripts under `backend/scripts/` - `create_demo_data.py` for the offline synthetic bundle, `download_sea_ice.py`, `download_ocean.py` and `download_weather.py` for provider fetches, and `validate_datasets.py` to write the dataset report.

One config note: `DATA_MODE` in `backend/config.py` decides whether the app prefers real or synthetic data, and `DEMO_MODE` controls how demo labelling is reported. Defaults are set to work with whatever is in the repo and fall back to
demo data where needed."""

#: What a follow-up ("tell me more") adds on top of the briefing just given.
#: Repeating the same paragraphs back would read like a stuck loop, so each one
#: moves a level down instead - the concrete numbers, the files to open, the
#: thing that usually surprises people.
_DEEPER: dict[str, str] = {
    "overview": """\
Let me get specific about the two things that trip people up.

**Why there are two backends.** `backend/main.py` on port 8000 is the unified \
REST API the dashboard calls. `backend/app/main.py` on port 8001 is older and \
owns the voyage lifecycle - start, advance, recalculate, status. They import the \
same services in the same process, so it's not duplicated logic, just two \
entry points that grew at different times. Everything you click in the UI goes \
through port 8000.

**Why the route keeps changing.** The re-plan runs from the vessel's *current* \
position, not the departure port. So on each two-hour step the engine treats \
"wherever I am now" as the new origin and re-solves to the same destination. \
That single design choice is what makes the simulation feel like navigation \
rather than a route that redraws itself from scratch.

**Where the numbers come from, end to end.** Real observations land in \
`backend/datasets/processed/` as NetCDF and CSV, the ML runtimes load trained \
checkpoints from `backend/models/`, the navigation engine turns all of it into a \
risk grid, and A* solves a path across that grid. The frontend never computes \
any of it - it renders what the services return.

**What I'd read first if I were you.** `docs/architecture.md` for the shape of \
it, `docs/navigation.md` for the route engine, and `docs/limitations.md` for \
what it can't do yet. That last one is the most useful document in the repo.""",
    "architecture": """\
A few details the diagram doesn't show you.

**Why the frontend has a Vite proxy.** `/api` requests from the browser get \
forwarded to :8000 at dev time, so there's no CORS configuration anywhere and no \
absolute backend URL baked into the client.

**Why SQLite and not Postgres.** It's a single-machine decision-support tool. \
Journeys live in memory, not in the database, so a restart clears them. \
SQLAlchemy holds the dataset inventory, analytics ingest metrics and route \
snapshots - the things you want to keep across restarts.

**The boundary that matters.** The rule is that the frontend never computes \
anything the backend can compute. Routes, risk, fuel and analytics all come from \
`services/`. That's why the numbers agree between the map, the planner and what \
I tell you - there's one source for each of them.

**Where new code would go.** A new endpoint goes in `backend/api/` and gets \
mounted under `/api`. A new page goes in `frontend/src/pages/`. A new model goes \
in `backend/ml/<domain>/` with a runtime loader, so it degrades to a fallback \
instead of erroring when the checkpoint is missing.""",
    "data": """\
The part worth understanding is provenance, because it's what makes the rest of \
the honesty story work.

**The accessor sits between the files and the app.** Real observations are daily \
or 6-hourly, but the simulation steps every 2 hours. So `accessor.py` picks the \
closest valid observation and returns metadata about it - the original \
timestamp, whether it matched exactly or was interpolated, and how stale it is. \
The app can therefore say "this is the 06:00 field, you're at 10:00" instead of \
pretending there's a 10:00 observation.

**The demo/real boundary is enforced, not just labelled.** A `real` or `auto` \
run will not reuse an existing `synthetic_demo` file - it warns and regenerates. \
That matters, because a stale demo file silently shadowing a real source is \
exactly the failure mode that would make this system lie.

**What you'd need for real data.** Credentials for NSIDC, Copernicus Marine, \
NASA OSCAR and ECMWF ERA5 in `.env`, then the download scripts. The pipeline, \
the validation and the labelling are already in place - that part isn't stubbed.

**The one real artifact already shipped** is the Antarctic land mask, a numpy \
`.npy` of land cells. It's used to exclude land from navigation, and it is \
genuine geography rather than generated.""",
    "models": """\
Let me get into the details that matter for judging them.

**Why sea ice and icebergs use different architectures.** Sea ice is a dense \
grid field, so ConvLSTM over the whole `[time, height, width]` block makes sense. \
Icebergs are sparse individual objects, so each one is a track problem and a \
recurrent model over a 12-feature timestep vector fits better than a conv net \
over a grid.

**The 24-hour versus 6-hour split is real.** The sea-ice checkpoint serves its \
native 24-hour step. The iceberg runtime does recursive multi-step at a 6-hour \
reference interval. Neither one pretends it can interpolate finer than it was \
trained to.

**Why fallback instead of error.** Both runtimes check the checkpoint at load. \
Missing or malformed means `available: false` and the caller drops to \
persistence. A dashboard that hard-fails because a model file is absent is \
useless for a planning aid.

**The honest bit, plainly.** These are trained on synthetic data. The iceberg \
demo tracks don't drift the way real bergs do, so at multi-step horizons \
persistence frequently wins. That is the expected result of training on fake \
physics, not a bug in the models. `/api/models/status` is the source of truth \
for what's actually on disk, and it reports `trained_on_demo` so the UI can say \
so.""",
    "navigation": """\
The details that explain the numbers you see in the UI.

**Why icebergs are obstacles but sea ice is a cost.** A berg inside your safety \
radius makes a cell impassable - there's no partial credit, you either clear it \
or you don't. Sea ice just raises the price of crossing. Treating them the same \
way would produce routes that thread between bergs at close quarters, which is \
precisely the behaviour you don't want.

**Why the vessel changes the answer.** Sea-ice risk is scored against the \
vessel's ice class. A PC5 vessel has a 60% concentration ceiling, so cells above \
that are effectively blocked for it - but the same cell is merely expensive for \
a lower class. The grid is built per-vessel, which is why switching ships
changes the route.

**Where the weights live.** Objective weights and thresholds are in \
`navigation.json` and `simulation.json`. The 0.6 safety against 0.4 fuel blend \
you see quoted is configured, not hard-coded, and you can shift it.

**What `route_update_count` is telling you.** It increments each time the \
two-hour loop produces a different path. A count climbing every step means the \
engine keeps finding a better way from the new position; a count stuck at zero \
means the current path is still optimal.

**One real caveat:** A* runs synchronously over a 61 × 721 cell grid. Locally \
that's fine. It would not be fine under concurrent load, which is why the \
production-readiness notes flag it.""",
    "journey": """\
The mechanics that make the loop behave the way it does.

**Why the position never resets.** This is the single most important behaviour \
in the simulation. Each step re-solves from the vessel's current cell with the \
destination held fixed. If it re-solved from the port each time you'd get the \
same route forever and the simulation would be theatre.

**Why `live` mode returns a 400.** There's no GPS feed implemented. Rather than \
invent a position, the endpoint refuses until you supply a real fix through the \
recalculate call. Simulation mode advances along the planned route instead, which \
is honest about where the position is coming from.

**Why the destination is a point on the route and not an arrival.** The \
destination snaps to the centre of its 0.5° grid cell, so an arriving vessel \
keeps a small residual distance while `is_complete` is true. That's a grid \
artifact, and it's documented in the limitations rather than hidden.

**Where the state lives.** Journeys are in-memory, managed by the simulator, so \
a backend restart loses them. The database stores route snapshots but not the \
live journey.

**What re-planning actually costs.** Each step rebuilds the risk grid and runs \
A* across ~44,000 cells. On a local machine that's comfortably fast enough to
feel live, which is why the demo feels responsive.""",
    "frontend": """\
The implementation details that shape what you can do in the UI.

**Why the sea-ice grid is canvas, not DOM.** A 0.5° grid over the Southern Ocean \
is tens of thousands of cells. Rendering that as elements would kill the browser,
so it's drawn to a canvas layer under the Leaflet tiles.

**How page switching works.** The shell is state-driven, not router-driven - \
`setPage` swaps the rendered component. That's why navigation is instant and why
there's no URL to bookmark for a given panel.

**Why state got lifted into context.** The forecast horizon, the selected \
iceberg and the active vessel are all needed by more than one page, and by me. \
Keeping them in `AppContext` is what stops the map, the planner and my answers
disagreeing about the current selection.

**The alert log is browser-side.** Alerts are generated from live state in \
`routeAlerts.ts`, not fetched from an endpoint. So I can explain an alert in
full detail, but there is no `/api/alerts` behind it - that's by design at this
stage.

**Build setup.** Vite with TypeScript, Tailwind for styling, Recharts for the
plots, Leaflet for the map and a heavier 3D globe as an optional view.""",
    "api": """\
A few things worth knowing before you integrate against it.

**Everything is provenance-aware.** Responses carry `demo`, `classification`, \
`model_used_real` and `real_data_available`. You can build UI that refuses to
present synthetic data as real by checking those flags rather than by trusting
the numbers.

**The intelligence endpoints are sea-ice specific.** Under \
`/api/sea-ice/intelligence/` there are ten routes for concentration, growth, melt,
drift, accessibility, hazards and sharing. The spectral one reports itself
unavailable when no imagery is configured, rather than returning a fabricated
reading.

**Where the assistant fits.** `/api/assistant/chat` takes the question, the
session history and a dashboard snapshot of what the user is currently looking
at. It returns an answer, sources, warnings and - when relevant - validated
actions the frontend then executes. It never executes anything itself.

**Interactivity at the docs.** `/docs` and `/openapi.json` are both live, so the
schema is always current with the code.

**Legacy compatibility.** The `/api/v1` journey routes are kept deliberately, so
older callers don't break. New work should target `/api`.""",
    "limitations": """\
If you only remember one thing: nothing here should be used to make a real \
navigational decision yet. Everything else is a smaller version of that.

**The grid clamp is the most misleading number.** Routes from Hobart, Cape Town \
or Ushuaia start at the grid edge because those ports sit north of −55°. The \
reported `total_distance_nm` is the in-grid length, so it reads *shorter* than \
truth - about 1,483 nm against a real 2,151 nm for Hobart to McMurdo. If you \
show that number to anyone, show the caveat with it.

**Demo re-routing is not the same as real re-routing.** Between steps the demo
fields don't change, so what you're watching is recalculation from a new
position. With live fields the risk field would change too and the route would
respond to that. That path is untested against real data.

**The models are the weakest link for real use.** Trained on synthetic tracks
that don't drift realistically, they lose to persistence at multi-step horizons.
The fix isn't tuning - it's real training data, and the pipeline for that is
already built.

**Operational gaps.** No auth, no multi-user support, journeys lost on restart,
A* synchronous on the request path. All fine for a local decision-support tool;
all blocking for anything operational.

**What would make it genuinely usable.** Real credentials through the existing
pipeline, real training runs, a GPS feed for live mode, and a qualified crew
sign-off on the risk model. The architecture supports all four - they're
data and integration problems, not redesign problems.""",
    "setup": r"""
The bits that save you time on a fresh machine.

**Use the skip flag.** After the first run, `.\run.ps1 -SkipInstall` skips both the venv refresh and the npm install. The full script re-checks them every time, which is slow if nothing changed.

**Open the frontend, not the backend.** `http://localhost:5173` is the dashboard. `http://localhost:8000` is the API and shows JSON. That trips up everyone once.

**Interactive API docs are at** `http://localhost:8000/docs` once the backend is up - the fastest way to see what the API actually returns.

**Environment.** Copy `.env.example` to `.env` before adding any provider credentials. Without them the app runs on demo data, which is a supported mode, not a broken one.

**Python version.** The venv is created by the launcher, so you don't need to provision one yourself. Requirements come from `backend/requirements.txt`.

**Regenerating demo data.** If the datasets folder gets into a weird state, `python scripts/create_demo_data.py --days 30` rebuilds the synthetic bundle from scratch without needing any credentials.

**Validation.** `python scripts/validate_datasets.py` writes a dataset report to
`backend/datasets/reports/` and is worth running after any data change.""",
}

# Extra depth the user can ask for after a briefing.
_FOLLOW_UPS: dict[str, str] = {
    "overview": "the architecture, the data and where it comes from, the two model "
                "pipelines, how the route engine scores risk, the two-hour loop, the "
                "API surface, or the honest limitations",
    "architecture": "the data layer, the models, the route engine's risk scoring, the "
                    "API surface, or the honest limitations",
    "sea_ice": "how the models are trained, how ice thickness and keel depth are estimated, "
               "or how sea-ice risk enters the routing engine",
    "icebergs": "the 4-model drift ladder, how the No-Go buffers are enforced in A*, "
                "or how trajectory forecasts are updated",
    "navigation": "the two-hour rolling loop, the fuel and duration model, the API "
                  "surface, or the honest limitations",
    "journey": "how the route is re-planned each step, the risk scoring behind it, "
               "or the honest limitations",
    "route_change": "the 2-hour rolling simulation loop, how live position re-planning works, "
                    "or the alert engine",
    "risks": "how sea ice and iceberg buffers combine into the composite risk score, "
             "or how vessel ice class limits are enforced",
    "alerts": "how alerts are classified, how distance thresholds trigger warnings, "
              "or the recommended avoidance actions",
    "frontend": "the backend services behind each page, the API surface, or the "
                "honest limitations",
    "data": "the two model pipelines, how the route engine uses this data, or the "
            "honest limitations of the current demo state",
    "models": "how the route engine consumes their output, what the real sources "
              "would look like, or the honest limitations",
    "api": "what the route engine actually does, the two-hour loop, or the data "
           "layer underneath",
    "limitations": "the architecture behind any of it, the data pipeline, or the "
                   "model training - I can go deeper on any one",
    "setup": "the architecture behind the app, the data pipeline, or the models",
}

_BRIEFINGS: dict[str, str] = {
    "overview": _OVERVIEW,
    "architecture": _ARCHITECTURE,
    "sea_ice": _SEA_ICE,
    "icebergs": _ICEBERGS,
    "navigation": _NAVIGATION,
    "journey": _JOURNEY,
    "route_change": _ROUTE_CHANGE,
    "risks": _RISKS,
    "alerts": _ALERTS,
    "data": _DATA,
    "models": _MODELS,
    "frontend": _FRONTEND,
    "api": _API,
    "limitations": _LIMITATIONS,
    "setup": _SETUP,
}

_TOPIC_LABELS: dict[str, str] = {
    "overview": "the whole system",
    "architecture": "the architecture",
    "sea_ice": "sea-ice forecasting",
    "icebergs": "iceberg tracking",
    "navigation": "the route engine",
    "journey": "the voyage simulation",
    "route_change": "route recalculation",
    "risks": "navigation risk detection",
    "alerts": "the alert system",
    "data": "the data layer",
    "models": "the models",
    "frontend": "the frontend",
    "api": "the API surface",
    "limitations": "the limitations",
    "setup": "running it",
}


def build_answer(question: str, history: list[dict] | None = None) -> str:
    """A conversational answer about the project.

    Used when no language model is configured. It answers in Raga's voice from
    the project's real architecture, and it ends by offering somewhere to go
    next rather than stopping dead.
    """
    named = _matched_topic(question)
    topic = named or "overview"
    follow_up = is_followup(question)

    # "Why?" and "tell me more" lean on the previous turn rather than naming a
    # topic, so pick up whatever we were last talking about. A follow-up that
    # does name a subject ("and the models?") is switching topics, not asking
    # for more of the same thing.
    previous = _last_topic(history) if (follow_up and history) else None
    if previous:
        if not named or named == previous:
            topic = previous
            follow_up = True
        else:
            follow_up = False

    # A follow-up on the topic we just covered should go a level deeper, not
    # replay the same paragraphs.
    if follow_up and _DEEPER.get(topic):
        return _DEEPER[topic].strip()

    body = _BRIEFINGS.get(topic, _OVERVIEW)
    if topic == "overview":
        return body.strip()
    options = _FOLLOW_UPS.get(topic, _FOLLOW_UPS["overview"])
    return f"{body.strip()}\n\nWant me to go into any of {options}?"


def _last_topic(history: list[dict]) -> str | None:
    """Recover the topic of the most recent real question in the history."""
    for entry in reversed(history or []):
        if entry.get("role") != "user":
            continue
        content = str(entry.get("content", "")).strip()
        if not content or is_followup(content):
            continue
        return detect_topic(content)
    return None


def topics() -> list[str]:
    """Every topic the assistant can brief the user on."""
    return list(_BRIEFINGS)


def label(topic: str) -> str:
    """Human name for a topic, used in follow-up offers."""
    return _TOPIC_LABELS.get(topic, "that")
