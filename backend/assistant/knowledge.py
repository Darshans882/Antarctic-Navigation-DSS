"""Curated knowledge base for the DSS assistant.

The assistant needs to answer three families of questions, and only one of
them needs live data:

1. **How do I use the dashboard?** - navigation, page-by-page controls, and
   the step-by-step voyage workflow. Served from ``SECTIONS`` below.
2. **What does this data mean?** - sea ice, icebergs, routes, the models and
   the underlying observations. Served from ``SECTIONS`` + ``GLOSSARY``.
3. **What is happening right now?** - current conditions. Served from the
   live tools in ``assistant.tools``.

Everything in this module is static, hand-written and reviewed. Nothing here
is generated from data, so it is safe to hand to the LLM verbatim and it never
fights with the CONTEXT block.

Retrieval is keyword-scored rather than embedded: the corpus is small enough
that scoring is predictable, has no new dependencies, and cannot fail at
runtime. ``build_knowledge_context`` always returns the overview so the model
never loses its bearings, then appends the highest-scoring sections.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    """One retrievable chunk of static knowledge."""

    id: str
    title: str
    body: str
    keywords: tuple[str, ...] = ()
    pages: tuple[str, ...] = ()
    always: bool = False
    #: Tie-breaker between equally-scoring sections. Page walkthroughs win over
    #: reference sections, because "what does the horizon dropdown do" wants the
    #: page, not the glossary.
    priority: int = 0

    def matches(self, question: str) -> int:
        """Crude overlap score. 0 means "not obviously about this"."""
        score = 0
        for keyword in self.keywords:
            if " " in keyword:
                if keyword in question:
                    score += 3
            elif re.search(rf"\b{re.escape(keyword)}\b", question):
                score += 1
        return score


_SECTIONS: tuple[Section, ...] = (
    Section(
        id="overview",
        title="What this app is",
        always=True,
        body=(
            "The dashboard is called Cryosphere Routing Optimization. It is an Antarctic "
            "navigation decision support system: it reads satellite and weather observations, "
            "analyses sea ice and icebergs, plans a route around the hazards, and raises alerts "
            "as conditions change.\n"
            "It has five pages, all reachable from the left sidebar: Home, Sea-Ice Forecast, "
            "Iceberg Tracking, Navigation Dashboard, and Alert Message. There is a sixth view, "
            "the AI Assistant, reachable from the Home page or by clicking the penguin in the "
            "bottom-right corner - that is me.\n"
            "The workflow the whole thing is built around is: observe, analyse, plan, navigate, alert."
        ),
        keywords=("what is this", "what is the app", "tell me about", "overview", "introduce"),
    ),
    Section(
        id="global-navigation",
        title="Getting around the dashboard",
        keywords=(
            "navigate", "navigation bar", "sidebar", "menu", "switch page", "go to",
            "layout", "where is", "find the", "how do i move", "change page", "tabs",
        ),
        body=(
            "Everything lives behind the sidebar on the left. Click the logo to go home, or click "
            "any item in the list. The chevron button at the top of the sidebar collapses it down to "
            "a narrow icon strip so the map gets more room; click it again to widen it back. On a "
            "phone the sidebar slides in and out instead.\n"
            "The footer under every page repeats the safety note, and every data panel that could be "
            "synthetic is labelled. Read those labels - they are the difference between a real "
            "observation and a placeholder."
        ),
    ),
    Section(
        id="page-home",
        title="Home page",
        pages=("home",),
        priority=1,
        keywords=("home", "homepage", "overview page", "landing", "first page", "simulator"),
        body=(
            "Home is the front door. At the top is an animated 3D view of the Southern Ocean. Below "
            "it is a five-step diagram of how the system works - Observe, Analyse, Plan, Navigate, "
            "Alert - which is a good mental model for the whole product.\n"
            "At the bottom is a 'System Modules' grid with a card per page: Sea-Ice Forecast, "
            "Iceberg Tracking, Navigation Dashboard, Alert Message and AI Assistant. Each card has "
            "an Open button that jumps straight there. That grid, plus the sidebar, is the whole "
            "navigation model - there is nothing hidden behind a menu."
        ),
    ),
    Section(
        id="page-sea-ice",
        title="Sea-Ice Forecast page - what each control and panel does",
        pages=("sea-ice",),
        priority=1,
        keywords=(
            "sea-ice page", "sea ice page", "concentration map", "horizon dropdown",
            "ice thickness", "types of ice", "keel", "melt", "climate trend", "ice cover over time",
            "ice conditions risk", "change detection", "legend",
        ),
        body=(
            "This page answers 'what does the ice look like right now, and where is it going'.\n\n"
            "Top row: four stat tiles - mean concentration, max concentration, coverage and which "
            "model produced the forecast. To their right is the Horizon dropdown (6, 12, 24, 48, 72, "
            "120 or 168 hours). Changing it re-fetches the forecast and every panel below recomputes.\n\n"
            "Concentration Map: the big 3D globe with the ice field painted on it. The colour ramp "
            "under the title is the legend - it runs from open water (pale) to fully consolidated "
            "ice (dark). The timestamp underneath is when the forecast is valid, not when it was made.\n\n"
            "Skill note: a blue strip below the map. It says how much to trust the forecast, and "
            "whether the model has been trained on real observations. If it is not there, there is "
            "no skill statement to show.\n\n"
            "Sea-Ice Details - four panels, all estimates derived from the concentration field:\n"
            "- Types of Ice: a donut of how much of the field is open water, first-year ice (fyi), "
            "mixed, or multi-year ice (myi). fyi is ice that formed this winter; myi is ice that has "
            "survived at least one summer and is far stronger.\n"
            "- Ice Thickness: min / average / max in metres. This is concentration times three "
            "metres, a first-order proxy - not a sonar measurement.\n"
            "- Ice Below the Waterline: mean and deepest keel depth, plus the clearance between the "
            "ice keel and the seabed. Keel depth is what actually decides whether a ship clears.\n"
            "- How Ice Cover Is Changing: now versus the selected forecast horizon, split into cells "
            "that are increasing, decreasing or stable.\n\n"
            "Long-Term Ice Cover and Risk (collapsible): a trend chart of ice cover over the stored "
            "history with a baseline line, and a risk panel scoring current conditions out of 100 "
            "with the four factors that produced the score."
        ),
    ),
    Section(
        id="page-icebergs",
        title="Iceberg Tracking page - what each control and panel does",
        pages=("icebergs",),
        priority=1,
        keywords=(
            "iceberg page", "iceberg list", "search iceberg", "nearest 10", "largest 10",
            "distance between icebergs", "trajectory", "historical", "predicted", "iceberg map",
            "select an iceberg",
        ),
        body=(
            "This page answers 'where are the icebergs and where are they going'.\n\n"
            "Top left: an 'Iceberg List' panel. Every row shows an iceberg ID, its distance from the "
            "reference vessel position, and its latitude and longitude. Click a row to select that "
            "iceberg - the map, the detail card and the distance readout all follow your selection.\n\n"
            "Above the list there are two controls. The search box filters by iceberg ID as you type. "
            "The dropdown next to it has three modes: All, Nearest 10 (the ten closest to the vessel) "
            "and Largest 10 (the ten biggest, by length in km).\n\n"
            "Below the list: 'Distance Between Icebergs'. Pick two IDs from the two dropdowns, press "
            "Calculate, and you get the great-circle distance in both km and nautical miles.\n\n"
            "Right side: the 3D map. The vessel marker is fixed at 68 degrees south, 147 degrees east. "
            "The legend under the map matters - the indigo line is the iceberg's observed history, "
            "the amber dashed line is the model's prediction. Those are different kinds of evidence "
            "and you should keep them apart. The 'N obs' / 'N pred' counter tells you how much of "
            "each exists.\n\n"
            "Bottom card: the selected iceberg's latitude, longitude, length, observation count and "
            "distance from the vessel in nautical miles."
        ),
    ),
    Section(
        id="page-planner",
        title="Navigation Dashboard page - the voyage workflow",
        pages=("planner",),
        priority=1,
        keywords=(
            "planner page", "navigation dashboard page", "journey controls", "start journey",
            "advance 2 hours", "advance", "recalculate", "recalculate route", "live position",
            "fix", "departure port", "research center", "journey mode", "outbound", "return",
            "reset details", "route set", "alternative route", "journey timeline", "voyage map",
        ),
        body=(
            "This is the page where you actually plan and run a voyage. Here is the whole loop.\n\n"
            "1. Set up. In 'Journey Controls' pick a Departure Port, a Research Center (the "
            "destination), a Vessel, and a Journey Mode - Outbound or Return. All four are locked "
            "once the journey starts.\n"
            "2. Press 'Start Journey'. The vessel is placed at the port, the system generates a "
            "recommended route plus alternatives, and the map, metrics and alerts all populate.\n"
            "3. Step time forward with 'Advance 2 Hours'. Each press moves the vessel two hours "
            "along the route and recomputes the route from the new position, because the ice will "
            "have moved too. This is the intended loop: advance, look, decide.\n"
            "4. If you get a real position fix, type it into the two latitude/longitude boxes under "
            "'Recalculate from fix' and press 'Recalculate Route'. Accepts decimal degrees or "
            "compact notation like 68.1S and 147.4E. The route is rebuilt from that point.\n"
            "5. Compare routes. In 'Route Details' the 'Active route set' shows the recommended route "
            "and each alternative with distance, ETA and risk. Click any card to make it the route "
            "drawn on the map; click the recommended card to go back.\n"
            "6. 'Reset Details' clears the journey and unlocks the dropdowns so you can start over.\n\n"
            "Alongside that: the metric strip at the top (current location, destination, journey "
            "mode, last and next update, remaining distance, fuel, risk level), the Voyage Map, and "
            "the Journey Timeline showing departure, the previous update, current position, current "
            "route, next update and destination.\n\n"
            "The amber note about the destination being on land is normal. Antarctic stations are "
            "coastal or inland, so the router approaches the nearest navigable ocean cell and keeps "
            "the station's own coordinates for display."
        ),
    ),
    Section(
        id="page-alerts",
        title="Alert Message page",
        pages=("alerts",),
        priority=1,
        keywords=(
            "alert page", "alert message page", "notifications page", "mark all as read",
            "clear all", "severity filter", "unread", "view details", "search alerts",
        ),
        body=(
            "This page is the alert log. Alerts are generated automatically by the route engine - "
            "iceberg proximity, sea-ice crossings, severe weather, and every route recompute.\n\n"
            "Four counters at the top: total alerts, unread, critical, and warnings (medium and "
            "above). Below them is a search box and a row of filter chips: All, Unread, then each "
            "severity (critical, high, medium, low, info) and each type (route, sea-ice, iceberg, "
            "weather, system).\n\n"
            "Each alert card shows a title, message, severity badge, type, timestamp and the route "
            "it applies to. The chevron on the right expands the full detail: the reason it fired, "
            "the selected route, the iceberg ID, distance from the route, exact location, the "
            "recommended action, and the previous-versus-new route comparison. The check and "
            "trash icons mark it read and delete it. 'Mark All as Read' and 'Clear All' sit at the "
            "top-right.\n\n"
            "Inside an expanded alert, 'View location on navigation map' jumps you straight to the "
            "Navigation Dashboard with the map centred on that hazard. Unread alerts have a blue bar "
            "down the left edge; the word Unread is shown next to the timestamp."
        ),
    ),
    Section(
        id="page-assistant",
        title="AI Assistant (me) - how to use me",
        pages=("assistant",),
        priority=1,
        keywords=(
            "assistant page", "how do i use you", "how do i use the assistant", "chat window",
            "ask you", "penguin", "horizon selector", "suggested questions", "context badge",
        ),
        body=(
            "I am the penguin in the bottom-right corner of every page. Click me and a chat panel "
            "opens; the same assistant also has a full page you can reach from the Home page if you "
            "want more room.\n\n"
            "The panel has three parts. The header shows which page you are on, so I know what you "
            "are looking at - that context label is why I can answer 'why did this alert fire' "
            "without you repeating yourself. Just under it is the Forecast Horizon selector (24, 48, "
            "72 or 120 hours) - set that first and any forecast question I get will use that horizon. "
            "At the bottom is the message box; Enter sends.\n\n"
            "On an empty conversation I suggest questions relevant to the page you are on. Click one "
            "or type your own. The refresh icon clears the chat.\n\n"
            "Every reply I give shows a small chip underneath naming the data source I used, coloured "
            "green for real data and amber for synthetic demo data. If something I say is a model "
            "estimate, I say so in the reply itself.\n\n"
            "Things I can do: explain any panel or button, define any term, and read you live numbers "
            "- current ice concentration, iceberg positions and drift, distances, route distance / "
            "time / fuel / risk, and the reasoning behind an alert."
        ),
    ),
    Section(
        id="end-to-end-workflow",
        title="The end-to-end voyage workflow",
        keywords=(
            "full workflow", "end to end", "how does the whole thing work", "step by step",
            "walk me through", "getting started", "first time", "tutorial", "demo", "how do i start",
        ),
        body=(
            "A full pass through the system takes about two minutes:\n\n"
            "1. Home - read the workflow diagram, open Sea-Ice Forecast.\n"
            "2. Sea-Ice Forecast - set the horizon to 48 hours and read the four stat tiles and the "
            "risk panel. That is your picture of the ice.\n"
            "3. Iceberg Tracking - filter to 'Nearest 10' and select the closest berg. Compare its "
            "indigo history line against the amber prediction line.\n"
            "4. Navigation Dashboard - pick a port, a station and a vessel, press Start Journey. The "
            "recommended route appears with its alternatives.\n"
            "5. Press Advance 2 Hours a couple of times. Watch the route change and the alert count "
            "climb as hazards appear.\n"
            "6. Alert Message - expand the newest alert, read the reason and the recommended action, "
            "and click 'View location on navigation map'.\n"
            "7. Come back to me at any point and ask what any of it means."
        ),
    ),
    Section(
        id="data-labels",
        title="How to read the data labels",
        keywords=(
            "demo data", "synthetic", "real data", "demo mode", "badge", "label", "is this real",
            "trust", "reliable", "accurate", "source", "provenance", "data quality",
        ),
        body=(
            "Every panel that can be synthetic is labelled. 'Synthetic demo data' means the numbers "
            "are generated placeholders and tell you nothing about the real Southern Ocean - the "
            "layout and the workflow are still real, the values are not. 'Real observations' or "
            "'processed pipeline data' means the value came from the observation pipeline.\n\n"
            "Assistant replies carry the same distinction as coloured chips: green for real data, "
            "amber for demo. If everything behind an answer is synthetic, the app also shows a "
            "banner saying the answer must not be used for real navigation.\n\n"
            "Separately, observed and predicted are always different things. Concentration right now "
            "is observed. Concentration in 48 hours is a forecast. An iceberg's past is observed; "
            "where it will be is predicted. This system never blurs that line and neither should you."
        ),
    ),
    Section(
        id="route-engine",
        title="How routes and risk are actually calculated",
        keywords=(
            "risk score", "how is risk calculated", "how does routing work", "route engine",
            "algorithm", "optimisation", "optimization", "waypoint", "why is this route",
            "why was this route", "risk level", "risk weight", "safety threshold",
        ),
        body=(
            "The router scores every grid cell on a 0.5 degree Antarctic grid and searches for the "
            "path that balances risk against fuel. The per-cell risk score is a weighted blend:\n"
            "- sea-ice concentration: 0.35\n"
            "- iceberg proximity: 0.30\n"
            "- weather severity: 0.20\n"
            "- distance penalty: 0.15\n\n"
            "Safety thresholds it will not cross by default:\n"
            "- sea-ice concentration above 0.6\n"
            "- within 20 km of a tracked iceberg\n"
            "- closer than 30 km to an ice edge\n"
            "- wind above 50 knots\n"
            "- wave height above 8 m\n\n"
            "The recommended route is the best blend of safety and fuel (weights 0.6 and 0.4), not "
            "necessarily the shortest or the cheapest - which is why an alternative can be shorter "
            "and still not be recommended. Routes are refreshed on a 2-hour cycle.\n\n"
            "A route is a planning aid computed under model assumptions. Nothing in this system can "
            "promise a route is safe."
        ),
    ),
    Section(
        id="glossary-sea-ice",
        title="Sea-ice terms",
        keywords=(
            "sea ice", "concentration", "what is concentration", "fyi", "myi", "first year",
            "multi year", "multiyear", "pack ice", "floe", "lead", "fast ice", "marginal ice zone",
            "ice edge", "nivo", "divergence", "brash", "sea ice terminology", "glossary",
            "define", "what does", "meaning of",
        ),
        body=(
            "Sea ice: the frozen surface layer of the ocean that forms where water cools below its "
            "freezing point. Around Antarctica it is seasonal - it grows through the southern winter "
            "and melts through the austral summer.\n"
            "Concentration: the fraction of a cell's surface covered by ice, from 0 to 1, usually "
            "quoted as a percentage. 100% is solid pack; 15% is nearly open water. It is the single "
            "most important number on the Sea-Ice Forecast page, and it drives the risk score.\n"
            "FYI (first-year ice): ice that formed during the current season. Thinner, weaker, melts "
            "faster - it is the ice a ship can usually push through.\n"
            "MYI (multi-year ice): ice that has survived at least one melt season. Thicker and far "
            "stronger, and the ice that actually stops a hull. A vessel's ice class (PC1 to PC7) is "
            "the rating of what it can handle, and this system treats first-year ice as passable and "
            "multi-year ice as an obstacle.\n"
            "Pack ice: the consolidated mass of floes packed together. Fast ice is ice attached to "
            "the coast and stationary.\n"
            "Floe: an individual floating piece of ice. A lead is a crack of open water between "
            "floes; leads and fractures are often the easiest way through a pack.\n"
            "Marginal ice zone: the band of broken, shifting ice between solid pack and open ocean. "
            "It is the hardest part of the Southern Ocean to navigate.\n"
            "Ice edge: the boundary between pack ice and open water.\n"
            "Keel: the part of an ice floe that sits below the waterline, roughly a fifth of its "
            "total thickness. It is what a ship's hull has to clear.\n"
            "Draft: how deep a ship sits in the water. The clearance under a floe's keel has to "
            "exceed the vessel's draft.\n"
            "Nivô and dawn: the period of near-constant daylight around the southern summer, when "
            "sunrise and sunset blur together."
        ),
    ),
    Section(
        id="glossary-icebergs",
        title="Iceberg terms and drift",
        keywords=(
            "iceberg", "berg", "growler", "bergy bit", "bergy", "calving", "calve", "tabular",
            "drift", "what makes icebergs move", "factors affect drift", "why do icebergs move",
            "currents", "gyre", "coriolis", "tabular iceberg", "iceberg types",
        ),
        body=(
            "An iceberg is a floating body of fresh water ice that broke off a glacier or ice shelf. "
            "Only about 10% of it shows above the water; the other 90% is submerged. Sizes are "
            "graded by name: a growler is under 1 m across, a bergy bit 1-2 m, a berg 2-5 m, a "
            "medium berg 5-100 m, a large berg 100-500 m, and a very large berg over 500 m. A "
            "tabular iceberg broke off a floating ice shelf, so it is wide, flat and deep-keeled - "
            "and far more dangerous per metre of height than an irregular berg.\n\n"
            "Calving is the process of ice breaking away. Most Antarctic icebergs ultimately come "
            "from ice shelves.\n\n"
            "Iceberg drift is governed mainly by: ocean currents (dominant for large bergs), surface "
            "wind drag on the huge above-water area, coupling with the surrounding pack ice, the "
            "Coriolis effect, and basal drag where a berg drifts over a shallow shelf. Size and shape "
            "matter: small bergs track the wind, large deep-keeled bergs track the current.\n\n"
            "In the Southern Ocean the main clockwise gyre circles the continent, which is why "
            "icebergs eventually end up on the northward side.\n\n"
            "This system tracks each iceberg's position history and projects short-horizon movement "
            "with a persistence baseline, and with an LSTM when a trained model is loaded. Those "
            "projections are physically motivated but not validated against real observations here, "
            "so treat a predicted position as a planning hint, not a fix."
        ),
    ),
    Section(
        id="data-sources",
        title="Where the observations come from",
        keywords=(
            "data source", "where does the data come from", "satellite", "nsidc", "copernicus",
            "usnic", "oscar", "era5", "instruments", "observation", "ingest", "pipeline", "netcdf",
        ),
        body=(
            "Sea-ice concentration: NSIDC Sea Ice Index passive microwave products, distributed via "
            "NSIDC and mirrored in Copernicus Marine records.\n"
            "Icebergs: USNIC (United States National Ice Center) iceberg tracks, and NSIDC's "
            "G00803 product for size and position.\n"
            "Ocean surface state: NASA OSCAR reanalysis.\n"
            "Weather: ERA5 atmospheric reanalysis.\n"
            "Sea floor and land mask: Antarctic bathymetry tiles with a land/ocean mask used to keep "
            "routes off the continent.\n\n"
            "Everything lands in a monthly CSV/NetCDF pipeline under the processed data folders, with "
            "a metadata sidecar recording the source, variable, units, resolution and coverage. The "
            "Data & Models view reports which of these are present and which are placeholders."
        ),
    ),
    Section(
        id="models",
        title="The models and how much to trust them",
        keywords=(
            "model", "which model", "accuracy", "how accurate", "metrics", "mae", "rmse",
            "convlstm", "lstm", "random forest", "persistence", "baseline", "convergence",
            "evaluation", "validation", "skill",
        ),
        body=(
            "Sea-ice concentration: a convolutional LSTM for the spatio-temporal forecast, a random "
            "forest as a second opinion, and a persistence baseline (hold today's field) as the "
            "reference every other model has to beat. Metrics reported are MAE, RMSE and spatial "
            "correlation. A model that does not beat persistence has not learned anything useful.\n"
            "Iceberg drift: a random forest over each berg's position history and surrounding ocean "
            "and weather state, with a persistence fallback.\n"
            "Routes: a weighted risk search, not a learned model.\n\n"
            "Honest framing: quote accuracy only from the metrics the backend actually returns. A "
            "metric being available does not mean it was computed on real observations - always say "
            "which of the two it was."
        ),
    ),
    Section(
        id="fleet-and-places",
        title="Vessels, ports and stations in the system",
        keywords=(
            "vessel", "ship", "fleet", "icebreaker", "port", "harbour", "harbor", "station",
            "research center", "research centre", "destination", "departure", "mcmurdo",
            "ice class", "hobart", "ushuaia", "cape town", "christchurch",
        ),
        body=(
            "Vessels. MV Ivan Papanin (polar_explorer) is the heavy icebreaker, 120 m, PC3, rated for "
            "year-round operation in medium first-year ice. MV Vasiliy Golovnin "
            "(research_vessel_sagar) is a 105 m research vessel, PC5. I/B Vladimir Ignatyuk "
            "(supply_cargo) is a 130 m resupply cargo ship, PC4. Each carries its own draft, cruise "
            "speed, daily fuel burn, range and safety distance, and those numbers feed the route "
            "engine.\n\n"
            "Departure ports. Hobart (Australia) is the default and the home of the Australian "
            "Antarctic Division. Ushuaia and Punta Arenas serve the Antarctic Peninsula. Cape Town "
            "serves the Indian Ocean sector. Christchurch and Bluff are the New Zealand gateways, "
            "with Bluff the closest to the Ross Sea.\n\n"
            "Destinations. Fifteen research stations: McMurdo and Scott Base (Ross Sea, Ross Island), "
            "Mawson, Davis, Zhongshan, Bharati and Maitri (Prydz Bay region), Casey (Budd Coast), "
            "Halley VI (Brunt Ice Shelf), Syowa, Neumayer III, Concordia (Dome C), Princess Elisabeth, "
            "Jang Bogo (Terra Nova Bay) and Villa Las Estrellas (South Shetlands).\n\n"
            "A vessel's ice class matters as much as its size. PC ratings run from PC1 (highest) "
            "downward, and each one describes the ice pressure the hull can take."
        ),
    ),
    Section(
        id="safety-and-limits",
        title="Safety framing and known limits",
        keywords=(
            "safe", "safety", "guarantee", "accurate", "reliable", "can i trust", "limitation",
            "disclaimer", "warning", "should i use this", "real navigation", "risk of relying",
        ),
        body=(
            "This is a decision support system, not an authority. Every route is computed under model "
            "assumptions, every forecast is an estimate, and no output here guarantees a safe "
            "passage.\n\n"
            "Known limits. Persistence-based drift carries no validated real-world skill here. Ice "
            "thickness is a concentration proxy, not altimetry. Keel depth is an isostatic estimate, "
            "not a measured keel. Ice type is a concentration heuristic - separating multi-year from "
            "first-year ice properly needs SAR or passive-microwave data. Route cells are half-degree, "
            "which is coarse for harbour approaches. Distances are great-circle, not along the route. "
            "Where a dataset is missing, the panels say so rather than guessing.\n\n"
            "When a panel says data is unavailable, that is a real answer. Do not substitute a "
            "plausible number for it."
        ),
    ),
    Section(
        id="faq",
        title="Common questions",
        keywords=(
            "faq", "frequently asked", "common question", "quick question", "can i",
        ),
        body=(
            "Q: Can this actually guide a ship? A: It is decision support. It assembles observations, "
            "runs models and shows the trade-offs, but a human makes the call.\n"
            "Q: Why is the route different from last time? A: Because the route is recomputed from "
            "the vessel's current position against current ice every 2 hours. A different route is "
            "the system working, not a bug.\n"
            "Q: Why does an alternative look shorter but is not recommended? A: The recommendation "
            "weights risk at 0.6 against fuel at 0.4. Shorter is not always safer.\n"
            "Q: What is the difference between mean and max concentration? A: Mean is the average "
            "across the whole field; max is the densest cell. A low mean with a high max means mostly "
            "open water with one nasty patch in it.\n"
            "Q: What does coverage mean? A: The share of grid cells that actually contain ice data. "
            "Low coverage means the picture is patchy.\n"
            "Q: Can I clear all the alerts? A: Yes, Clear All removes the records. It does not change "
            "the conditions that raised them, and new ones will appear on the next recompute.\n"
            "Q: Can I change the vessel mid-voyage? A: No. Vessel, port, center and mode lock when "
            "the journey starts. Use Reset Details to start a new one.\n"
            "Q: Why is there no Assistant entry in the sidebar? A: The assistant is meant to be "
            "always-on, so it lives in the floating penguin on every page. There is also a full "
            "assistant page linked from Home."
        ),
    ),
)

SECTIONS: tuple[Section, ...] = _SECTIONS


# --------------------------------------------------------------------------
# Glossary: short definitions surfaced when a term is mentioned
# --------------------------------------------------------------------------

GLOSSARY: dict[str, str] = {
    "sea ice": "frozen ocean surface ice; forms each southern winter and melts in summer",
    "concentration": "share of a grid cell covered by ice, 0-1 or 0-100%; the key number on the Sea-Ice Forecast page",
    "coverage": "share of grid cells that actually contain ice data, as opposed to open water",
    "mean concentration": "average ice concentration across the whole analysed field",
    "max concentration": "concentration of the densest single cell in the field",
    "pack ice": "the consolidated mass of ice floes floating together",
    "fast ice": "sea ice attached to the coast and stationary",
    "floe": "one individual floating piece of ice",
    "lead": "a crack of open water between floes; often the easiest way through a pack",
    "ice edge": "the boundary between pack ice and open water",
    "marginal ice zone": "the band of broken, shifting ice between pack and open ocean; hardest to navigate",
    "fyi": "first-year ice - formed this season, thinner and weaker, usually passable",
    "first-year ice": "ice that formed during the current season; weaker than multi-year ice",
    "myi": "multi-year ice - survived at least one melt season, thicker and much stronger",
    "multi-year ice": "ice that has survived a summer; the ice that can actually stop a hull",
    "keel": "the submerged underside of a floe, roughly a fifth of its total thickness",
    "draft": "how deep a ship sits in the water; must be less than the clearance under the ice keel",
    "clearance": "the gap between the ice keel and the seabed",
    "growler": "an iceberg under 1 m across, mostly underwater",
    "bergy bit": "an iceberg 1-2 m across",
    "tabular iceberg": "a flat, wide, deep-keeled iceberg calved from a floating ice shelf",
    "calving": "the process of ice breaking away from a glacier or ice shelf",
    "drift": "the movement of an iceberg under wind, currents, Coriolis and keel drag",
    "nivô": "the period of near-constant daylight around the southern summer",
    "trajectory": "an iceberg's observed position history; the predicted part is a model estimate",
    "persistence": "the baseline that holds today's state as tomorrow's forecast",
    "convlstm": "the convolutional LSTM used for spatio-temporal sea-ice concentration forecasting",
    "mae": "mean absolute error - average size of the model's mistakes in concentration units",
    "rmse": "root mean squared error - like MAE but penalises large misses more heavily",
    "spatial correlation": "how well the predicted pattern matches the observed pattern, from -1 to 1",
    "risk score": "weighted blend of sea-ice concentration, iceberg proximity, weather severity and distance",
    "risk level": "low, medium or high, derived from the risk score",
    "waypoint": "one of the coordinate points that make up a route",
    "great-circle distance": "the shortest path over the Earth's surface, ignoring obstacles",
    "nautical mile": "a unit of distance at sea, 1.852 km; shown as 'nm' throughout the app",
    "ice class": "a vessel rating from PC1 to PC7 for the ice pressure its hull can take",
    "hobart": "the default departure port, in Tasmania, Australia",
    "ushuaia": "an Argentine port and the usual gateway to the Antarctic Peninsula",
    "mcmurdo": "McMurdo Station, the largest Antarctic base, on Ross Island",
    "antarctic convergence": "the northern boundary where cold Antarctic water meets warmer sub-Antarctic water",
}


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------

MAX_SECTIONS = 4
MIN_SCORE = 1

#: Words a user might use for each page id, e.g. "icebergs" -> "iceberg".
_TOPIC_ALIASES = {
    "home": ("home", "overview", "landing", "simulator", "start"),
    "sea-ice": ("sea ice", "sea-ice", "ice forecast", "concentration", "ice thickness", "melt"),
    "icebergs": ("iceberg", "berg", "growler", "calving", "drift"),
    "planner": ("route", "planner", "journey", "navigation dashboard", "voyage", "fuel", "waypoint"),
    "alerts": ("alert", "notification", "warning"),
    "assistant": ("assistant", "you", "raga", "chat", "penguin"),
}


def _page_hint(page: str | None) -> tuple[Section, ...]:
    if not page:
        return ()
    return tuple(s for s in SECTIONS if page in s.pages)


def _topic_boost(question: str) -> set[str]:
    """Which pages the question is about, from the words they use for it."""
    hits: set[str] = set()
    for page, aliases in _TOPIC_ALIASES.items():
        if any(alias in question for alias in aliases):
            hits.add(page)
    return hits


def matching_sections(question: str, page: str | None = None) -> list[Section]:
    """Score every section against the question and return the best matches."""
    q = (question or "").lower()
    topics = _topic_boost(q)
    scored: list[tuple[int, int, Section]] = []
    for section in SECTIONS:
        score = section.matches(q)
        if section.pages and topics.intersection(section.pages):
            score += 2
        if section.id in _page_hint(page):
            score += 1
        if score >= MIN_SCORE:
            scored.append((score, len(section.body), section))
    # Highest score first; ties go to the more specific section, then the
    # shorter (sharper) one.
    scored.sort(key=lambda item: (-item[0], -item[2].priority, item[1]))
    return [section for _, _, section in scored[:MAX_SECTIONS]]


def matching_glossary(question: str) -> list[tuple[str, str]]:
    """Return (term, definition) for glossary entries mentioned in the question."""
    q = (question or "").lower()
    hits: list[tuple[str, str]] = []
    for term, definition in GLOSSARY.items():
        if term in q and not any(term in seen for seen, _ in hits):
            hits.append((term, definition))
    return hits[:8]


def build_knowledge_context(question: str, page: str | None = None) -> str:
    """Render the knowledge block that goes into the user message.

    The overview is always present so the model always knows what it is
    looking at; the rest is pulled in only when it looks relevant.
    """
    blocks: list[str] = []

    for section in SECTIONS:
        if section.always:
            blocks.append(f"[knowledge: {section.title}]\n{section.body}")

    current_page = _page_hint(page)
    if current_page:
        titles = ", ".join(s.title for s in current_page)
        blocks.append(
            f"[knowledge: where the user is right now]\n"
            f"The user is on the '{page}' page ({titles}). If their question refers to "
            f"\"this\", \"here\" or \"it\" without naming a page, they most likely mean this one."
        )

    for section in matching_sections(question, page):
        if section.always:
            continue
        blocks.append(f"[knowledge: {section.title}]\n{section.body}")

    glossary = matching_glossary(question)
    if glossary:
        lines = "\n".join(f"- {term}: {definition}" for term, definition in glossary)
        blocks.append(
            "[knowledge: plain-language definitions]\n"
            "Use these wordings or close paraphrases when defining terms:\n"
            f"{lines}"
        )

    return "\n\n".join(blocks)


def answer_glossary_question(question: str) -> str:
    """Plain-language definitions for whatever terms the user mentioned."""
    hits = matching_glossary(question)
    if not hits:
        return ""
    lead = "Good question - here's the short version."
    body = "\n\n".join(f"**{term}** - {definition}" for term, definition in hits)
    tail = (
        "Any of those numbers depend on which dataset loaded, so ask me for a value and I'll "
        "tell you whether it's observed, predicted or demo data."
    )
    return f"{lead}\n\n{body}\n\n{tail}"


def answer_dashboard_question(question: str, page: str | None = None) -> str:
    """Template answer for a 'how do I use the dashboard' question.

    Used when no LLM provider is configured so the offline path can still
    give a real, useful walkthrough instead of a shrug.
    """
    q = (question or "").lower()
    parts: list[str] = []

    picked = [s for s in matching_sections(question, page) if not s.always]
    if not picked:
        picked = list(_page_hint(page)) or [
            next(s for s in SECTIONS if s.id == "end-to-end-workflow")
        ]

    lead = {
        "page-sea-ice": "Happy to walk you through it.",
        "page-icebergs": "Sure - here's how that page works.",
        "page-planner": "Here's the whole flow on that page.",
        "page-alerts": "Here's how the alerts page works.",
        "page-assistant": "Here's how to use me.",
        "page-home": "Here's what the home page gives you.",
        "global-navigation": "Quick answer on that:",
        "end-to-end-workflow": "Here's the whole thing end to end:",
    }

    if len(picked) == 1 and picked[0].id in lead:
        parts.append(lead[picked[0].id])
    else:
        parts.append("Here's how that works.")

    for section in picked:
        parts.append(f"**{section.title}**\n\n{section.body}")

    parts.append(
        "Want me to go deeper on any one of those, or read you the live numbers instead?"
    )
    return "\n\n".join(parts)
