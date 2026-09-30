"""Prompt templates and context formatting for the DSS assistant.

All phrasing rules live here so the LLM policy is in one place and the
template fallback follows the same honesty rules as the LLM path.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from assistant import knowledge

SYSTEM_PROMPT = """You are Raga, the assistant built into Cryosphere Routing Optimization - an Antarctic navigation decision support dashboard. You have been part of this tool long enough to know your way around it.

HOW YOU TALK
- Write the way a person actually talks. Warm, direct, relaxed. Contractions are fine.
- Answer the question that was asked. Skip the preamble, the throat-clearing and the summary of what you are about to say. If someone asks what mean concentration is, give them the definition - not a paragraph about how you'll answer.
- No openings like "Great question!", "Certainly!", "I'd be happy to help", "Certainly! Here's...". Never.
- Numbers get said out loud, not dumped. "42% mean concentration" reads as "mean concentration is 42%". "distance_km: 812.4" does not read as anything.
- One or two short paragraphs, or a few short bullets when it is genuinely a list. No tables. No markdown headings unless you are walking someone through a numbered process.
- Match the user's energy. A one-line question gets a short answer, not an essay. A "walk me through" question gets real steps.
- Explain a technical term in plain words the first time it comes up, then use it normally.
- You may use a little warmth and a gentle aside, but do not perform enthusiasm.
- Never call the user "Captain", "sir", "madam" or "user", and never narrate your own capabilities ("As an AI I..."). You are Raga and you work here.

WHAT YOU KNOW
- HOW TO USE THE APP. Every page, button, dropdown, toggle, panel and filter, and the order to do things in. Never guess - the KNOWLEDGE block in the user's message contains the real walkthroughs.
- THE DOMAIN. Sea ice, icebergs, drift, routes, risk, the models, and where the observations come from. Same rule: it is in the KNOWLEDGE block.
- WHAT IS HAPPENING RIGHT NOW. Live numbers, and only from the CONTEXT block.

HONESTY RULES - THESE DO NOT BEND
1. Never say a route is safe or guaranteed. It is a planning aid computed under model assumptions.
2. Say whether something is observed or predicted. Use the words "observed", "forecast", "predicted", "projected" - not vague present tense for either.
3. Say whether data is real or synthetic. If the context flags something as demo, say plainly that it is demo data and means nothing about the real Southern Ocean.
4. Be clear about estimates. A thickness derived from concentration, a keel depth derived from thickness, a drift projection - these are estimates, and saying so is not hedging, it is the job.
5. Never invent a scientific fact, a model accuracy, a confidence interval or a metric that is not in the message. If it is not there, you do not know it.
6. Never claim live satellite imagery or live remote sensing unless the context says real observations were used.
7. Quote identifiers exactly: iceberg IDs, route IDs, vessel names, station names. Do not "correct" or normalise them.
8. If the answer is not in the context, say so in a normal way - "I don't have that number" - and offer something you can actually answer. Do not phrase it as an error.
9. Use the percent sign. 0.42 is 42%.
10. Close by pointing somewhere useful - a related question, or the panel that shows this. Do not end on a dead stop.

WHEN THE KNOWLEDGE AND THE CONTEXT DISAGREE, TRUST THE CONTEXT. Knowledge tells you what the buttons and concepts mean. Context tells you what is true right now. Never let a walkthrough's example numbers leak into a live answer.
"""


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _jsonable(value, depth: int = 0) -> object:
    """Recursively convert a tool payload to a JSON-serialisable structure."""
    import math

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, dict):
        return {k: _jsonable(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v, depth + 1) for v in list(value)[:200]]
    return str(value)


def format_tool_result(result: dict) -> str:
    """Render one tool result into a compact, readable text block."""
    lines = [
        f"[source: {result.get('name', 'unknown')}]",
        f"status: {result.get('status', 'ok')}",
    ]
    if result.get("demo"):
        lines.append("demo: TRUE (synthetic demo data)")
    if result.get("classification"):
        lines.append(f"classification: {result['classification']}")
    note = result.get("note")
    if note:
        lines.append(f"note: {note}")
    data = result.get("data")
    if data is not None:
        lines.append(f"data: {json.dumps(_jsonable(data), ensure_ascii=False)[:9000]}")
    return "\n".join(lines)


def build_context_report(results: list[dict]) -> str:
    """Join multiple tool results into a single CONTEXT block."""
    blocks = [format_tool_result(r) for r in results if r]
    return "\n\n".join(blocks) or "[no live data was retrieved for this question]"


def build_user_prompt(question: str, context_report: str, page: str | None = None) -> str:
    """Assemble the user turn: question, then knowledge, then live context."""
    parts = [f"Question from the user:\n{question}"]

    knowledge_block = knowledge.build_knowledge_context(question, page)
    if knowledge_block:
        parts.append(
            "KNOWLEDGE (how the app works, and what the terms mean - this is "
            "authoritative documentation, use it directly):\n" + knowledge_block
        )

    parts.append(
        f"CONTEXT (live numbers pulled just now from the DSS backend; this may be demo data):\n"
        f"{context_report}"
    )

    parts.append(
        "Answer naturally, as Raga, in the same language the user wrote in. Use the knowledge "
        "block for anything about how the app works or what a term means. Use the context block "
        "for anything about current conditions, and never invent a value that is not in it. If "
        "the context has no data for what was asked, say so plainly and offer the closest thing "
        "you can answer."
    )
    return "\n\n".join(parts)


def build_history_prefix(history: list[dict] | None) -> list[dict]:
    """Turn the short session history into openai-style messages."""
    if not history:
        return []
    msgs: list[dict] = []
    for item in history[-12:]:
        role = item.get("role")
        content = str(item.get("content", ""))[:4000]
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    return msgs


# --------------------------------------------------------------------------
# Offline path: template answers, same personality, same honesty rules
# --------------------------------------------------------------------------

_HOWTO_PATTERNS = (
    r"\bhow (?:do|can|would|should) i\b",
    r"\bhow (?:to|do)\b",
    r"\bhow does\b",
    r"\bhow would\b",
    r"\bwhere (?:do|can|should) i\b",
    r"\bwhere (?:is|are) the\b",
    r"\bwhat (?:does|do) the [\w' -]{2,40} (?:do|mean|work|represent|look like)\b",
    r"\bwhat (?:does|do) the \w+ (?:page|button|panel|tab|icon|badge|chip)\b",
    r"\bwalk me through\b",
    r"\bshow me how\b",
    r"\bexplain (?:the|how|this|what)\b",
    r"\bwhat (?:is|are) the \w+ (?:page|panel|button|tab|icon)\b",
    r"\btutorial\b",
    r"\bguide me\b",
    r"\bgetting started\b",
    r"\bfirst time\b",
    r"\bcan i\b",
    r"\bdemo (?:me|this|the app)\b",
    r"\bwhat can (?:i|you) (?:do|ask)\b",
    r"\bhow (?:is|are) (?:the|this) (?:dashboard|app|system|interface)\b",
    r"\bnavigate (?:the|to)\b",
    r"\bfind (?:the|a|an)\b",
    r"\bwhat (?:are|is) the options\b",
    r"\bhow (?:is|are) (?:risk|ice|route) (?:calculated|scored|computed)\b",
)

_HOWTO_RE = re.compile("|".join(_HOWTO_PATTERNS))

# Questions that look like how-to but are actually asking for a live number or analytical assessment.
_LIVE_QUESTION_HINTS = (
    "right now", "currently", "at the moment", "today", "latest", "live",
    "how many", "what is the", "what's the", "which one", "closest", "nearest",
    "forecast", "distance", "score", "level", "percent", "%",
    "trajectory", "drift", "recommended route", "route hazards", "which route", "available routes", "corridor", "concentration", "waypoint", "iceberg", "recalculate",
)


def looks_like_howto(question: str) -> bool:
    """True for app-usage questions that need documentation, not live data."""
    q = (question or "").lower()
    if not _HOWTO_RE.search(q):
        return False
    if any(k in q for k in ("page", "panel", "how do i", "how to", "walk me through")):
        if not any(k in q for k in ("current", "right now", "latest", "nearest", "closest")):
            return True
    return not any(hint in q for hint in _LIVE_QUESTION_HINTS)


def _pct(value, digits: int = 1) -> str:
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "n/a"


def _km(value, digits: int = 0) -> str:
    try:
        return f"{float(value):,.{digits}f} km"
    except (TypeError, ValueError):
        return "n/a"


def _hours(value, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f} hours"
    except (TypeError, ValueError):
        return "n/a"


def _demo_note(result: dict | None) -> str:
    if not result:
        return ""
    if result.get("demo"):
        return " Worth saying out loud: that one is synthetic demo data, so it tells you nothing about the real Southern Ocean."
    return ""


def _fallback_sea_ice(question: str, named: dict) -> list[str]:
    q = question.lower()
    horizon = (named.get("sea_ice_forecast") or {}).get("data", {}) or {}
    lines: list[str] = []

    wants_current = any(k in q for k in ("actual", "current", "observed", "right now", "now"))
    if wants_current and "difference" not in q:
        cur = (named.get("sea_ice_current") or {}).get("data") or {}
        if cur:
            lines.append(
                f"The observed field right now has a mean concentration of "
                f"{_pct(cur.get('mean_concentration'))}, with the densest cell at "
                f"{_pct(cur.get('max_concentration'))}, on a {cur.get('grid_size')} grid."
                f"{_demo_note(named.get('sea_ice_current'))}"
            )

    if horizon:
        h = horizon.get("horizon_hours", 24)
        lines.append(
            f"Looking {h} hours out, the forecast puts mean concentration at "
            f"{_pct(horizon.get('mean_concentration'))} and the peak at "
            f"{_pct(horizon.get('max_concentration'))}, across "
            f"{horizon.get('coverage_pct', 0):.1f}% of the grid. That's a projection, not "
            f"something observed."
        )
        if horizon.get("model_used_real") is False:
            lines.append("Worth knowing: this model hasn't been trained on real observations yet.")
        if horizon.get("skill_note"):
            lines.append(horizon["skill_note"])

    if wants_current and "difference" in q:
        cur = (named.get("sea_ice_current") or {}).get("data") or {}
        if cur and horizon:
            cm, fm = cur.get("mean_concentration"), horizon.get("mean_concentration")
            if cm is not None and fm is not None:
                lines.append(
                    f"So right now it's {_pct(cm)} and the forecast says {_pct(fm)} - a gap of "
                    f"{abs(fm - cm) * 100:.1f} percentage points. That's the difference between "
                    f"one field and another, not a measure of how accurate the model is."
                )

    risk = (named.get("sea_ice_risk") or {}).get("data") or {}
    if risk:
        lines.append(
            f"On risk, it's sitting at {risk.get('risk_level', 'unknown')} - a score of "
            f"{float(risk.get('risk_score', 0)) * 100:.1f} out of 100. {risk.get('description', '')}"
        )

    change = (named.get("sea_ice_change") or {}).get("data") or {}
    if change and ("change" in q or "changing" in q or "melt" in q):
        lines.append(
            f"Against the {change.get('horizon_hours')}-hour forecast, {change.get('increase_pct_cells')}% "
            f"of cells are getting icier, {change.get('decrease_pct_cells')}% are getting clearer, "
            f"and {change.get('stable_pct_cells')}% aren't really moving."
        )

    melt = (named.get("sea_ice_melt_zones") or {}).get("data") or {}
    if melt and "melt" in q:
        zones = melt.get("melt_zones", {}) or {}
        lines.append(
            f"On melt, {zones.get('no_melt_pct')}% of the field isn't forecast to lose any ice. "
            f"Of the rest, {zones.get('low_pct')}% lose a little (under 10%), "
            f"{zones.get('moderate_pct')}% lose 10 to 25%, and {zones.get('high_pct')}% lose more "
            f"than a quarter of their cover."
        )

    classification = (named.get("sea_ice_classification") or {}).get("data") or {}
    if classification and ("type" in q or "fyi" in q or "myi" in q or "young" in q or "old ice" in q):
        dist = classification.get("distribution", {}) or {}
        lines.append(
            f"On ice type, it's roughly {dist.get('open_water', 0)}% open water, "
            f"{dist.get('fyi', 0)}% first-year ice, {dist.get('mixed', 0)}% mixed, and "
            f"{dist.get('myi', 0)}% multi-year. First-year ice you can usually push through; "
            f"multi-year is the ice that actually stops a hull. That split is inferred from "
            f"concentration alone, so treat it as a rough guide."
        )

    thickness = (named.get("sea_ice_thickness") or {}).get("data") or {}
    if thickness and ("thick" in q or "how thick" in q or "thickness" in q):
        lines.append(
            f"Thickness comes out at about {thickness.get('mean_m')} m on average, ranging from "
            f"{thickness.get('min_m')} m to {thickness.get('max_m')} m. That's concentration times "
            f"three metres - a proxy, not a sonar measurement."
        )

    keel = (named.get("sea_ice_keel_depth") or {}).get("data") or {}
    if keel and ("keel" in q or "clearance" in q or "underwater" in q or "under the ice" in q):
        lines.append(
            f"For the underwater part, the mean keel depth is about {keel.get('mean_keel_depth_m')} m "
            f"and the deepest point goes to {keel.get('max_keel_depth_m')} m, leaving roughly "
            f"{keel.get('mean_subsurface_clearance_m')} m of clearance beneath the ice on average. "
            f"Keel is what a hull has to clear, so this is the number that decides whether ice is "
            f"passable - though it's an estimate built from thickness, not a measured keel."
        )

    trend = (named.get("sea_ice_climate_trend") or {}).get("data") or {}
    if trend and ("trend" in q or "long term" in q or "over time" in q or "anomaly" in q or "history" in q):
        lines.append(
            f"Looking at the stored history - {trend.get('record_count')} records - ice cover is "
            f"{trend.get('anomaly_direction', 'stable')} at {trend.get('current_pct')}% against a "
            f"baseline of {trend.get('baseline_pct')}%."
        )

    if "climatology" in q and not trend:
        lines.append("I don't have a climatology baseline to compare that against.")

    return lines


def _fallback_iceberg(question: str, named: dict) -> list[str]:
    q = question.lower()
    lines: list[str] = []

    traj = (named.get("iceberg_trajectory") or {}).get("data") or {}
    if traj and any(k in q for k in ("where will", "move", "drift", "trajectory", "head", "going")):
        obs = traj.get("observed_positions") or []
        pred = traj.get("predicted_positions") or []
        berg = traj.get("iceberg_id") or "the selected iceberg"
        model_name = traj.get("prediction_model") or "persistence baseline"
        conf_val = traj.get("confidence")
        if isinstance(conf_val, (int, float)):
            conf_str = f" (Confidence score: {conf_val:.1%})"
        elif conf_val:
            conf_str = f" ({conf_val})"
        else:
            conf_str = ""
        lines.append(f"Iceberg Trajectory Analysis for {berg}:")
        if obs:
            last = obs[-1]
            lines.append(
                f"- Latest Observed Position: Lat {last.get('latitude')}, Lon {last.get('longitude')} "
                f"(tracked across {len(obs)} recorded observation intervals)."
            )
        if traj.get("predicted_latitude") is not None:
            lines.append(
                f"- Forecast Projection: Positioned at Lat {traj.get('predicted_latitude')}, "
                f"Lon {traj.get('predicted_longitude')} using {model_name} drift physics{conf_str}."
            )
        lines.append(
            "- Trajectory Dynamics: Trajectory prediction models combine hydrodynamic ocean currents, "
            "prevailing Antarctic circumpolar wind drag on exposed sail area, and Coriolis deflection. "
            "A standard 10 km No-Go exclusion buffer and 25 km safety advisory buffer are monitored along this track."
        )

    if "drift" in q or "factors affect" in q or "why do icebergs move" in q:
        lines.append(
            "Icebergs move because of four things pulling in different directions: ocean currents, "
            "which dominate for big deep-keeled bergs; wind drag across their enormous above-water "
            "area; friction and freezing into the surrounding pack ice, which can hold them almost "
            "still for months; and basal drag once they drift over the shallow shelf. The "
            "Coriolis effect bends their path as they move, and size and shape decide how much "
            "each of these matters. Around Antarctica the whole set circles clockwise, which is why "
            "bergs eventually end up north of the continent."
        )
        lines.append(
            "One caveat on this system specifically: it tracks position history and projects "
            "short-term movement with a persistence baseline, plus an LSTM when a trained model is "
            "loaded. Those aren't validated against real observations here, so a quoted drift is a "
            "planning hint rather than a fix."
        )

    dist = (named.get("iceberg_distance") or {}).get("data") or {}
    if dist and ("distance" in q or "how far" in q or "between" in q):
        lines.append(
            f"{dist.get('iceberg_a')} and {dist.get('iceberg_b')} are "
            f"{_km(dist.get('distance_km'), 1)} apart - {dist.get('distance_nm', 0):.0f} nautical "
            f"miles. That's the great-circle distance between their latest reported positions, not "
            f"the distance you'd actually sail."
        )

    closest = (named.get("closest_iceberg") or {}).get("data") or {}
    if closest:
        ref_text = closest.get('reference', 'the reference position')
        risk_text = f" (Proximity Risk: {closest.get('risk_level')})" if closest.get('risk_level') else ""
        lines.append(
            f"The nearest tracked iceberg to {ref_text} is "
            f"{closest.get('closest_iceberg')}, located at Lat {closest.get('iceberg_latitude')}, "
            f"Lon {closest.get('iceberg_longitude')}, approximately {_km(closest.get('closest_distance_km'), 1)} "
            f"({closest.get('closest_distance_nm', 0):.1f} nm) away.{risk_text}"
            f"{_demo_note(named.get('closest_iceberg'))}"
        )

    if "how many" in q:
        il = (named.get("iceberg_list") or {}).get("data") or {}
        if il:
            lines.append(
                f"There are {il.get('count', 0)} icebergs being tracked right now."
                f"{_demo_note(named.get('iceberg_list'))}"
            )

    detail = (named.get("iceberg_detail") or {}).get("data") or {}
    if detail and any(k in q for k in ("size", "large", "length", "wide", "how big", "detail", "tell me about")):
        lines.append(
            f"{detail.get('iceberg_id')} is about {detail.get('length_km')} km long, sitting at "
            f"{detail.get('latitude')}, {detail.get('longitude')}, with "
            f"{detail.get('observation_count')} observations on record."
        )

    return lines


def _fallback_route(question: str, named: dict) -> list[str]:
    q = question.lower()
    lines: list[str] = []
    rte = (named.get("route_details") or {}).get("data") or {}
    rec = rte.get("recommended") or {}

    # 1. "Why is this route recommended?" or analytical route query
    if rec and ("why" in q or "reason" in q or "recommend" in q and "why" in q):
        lines.append(
            "Current Route\n"
            "----------------\n"
            f"Route: Recommended\n"
            f"Risk: {rec.get('risk_level', 'Low')} (Score: {rec.get('risk_score', 'n/a')})\n"
            f"Distance: {_km(rec.get('distance_km'))} ({rec.get('distance_nm', 0):.0f} nm)\n"
            f"Estimated Time: {_hours(rec.get('travel_time_hours'))}\n"
            f"Fuel: {rec.get('fuel_tons', 'n/a')} tonnes\n\n"
            "Hazards\n"
            "----------------\n"
            "Sea Ice: Filtered for concentration within vessel Polar Class capability.\n"
            "Nearest Iceberg: Clear of critical 10 km No-Go exclusion buffers.\n\n"
            "Reason\n"
            "----------------\n"
            "The Recommended route balances travel time, fuel consumption, and environmental hazard exposure "
            "using multi-objective A* search. Unlike the Shortest route (which cuts through higher ice pack) "
            "or the Safest route (which adds a significant detour), the Recommended route optimizes the Pareto "
            "trade-off to provide the lowest composite risk profile."
        )
    # 2. "What are the three available routes?" or alternative comparisons
    elif rte and any(k in q for k in ("three available routes", "three routes", "3 routes", "available routes", "show routes", "alternatives")):
        alts = rte.get("alternatives") or []
        overview_lines = [
            "Available Routes Overview\n"
            "--------------------------------------------------\n"
            f"1. Recommended Route (Balanced Optimization)\n"
            f"- Distance: {_km(rec.get('distance_km'))} ({rec.get('distance_nm', 0):.0f} nm)\n"
            f"- Estimated Time: {_hours(rec.get('travel_time_hours'))}\n"
            f"- Fuel: {rec.get('fuel_tons', 'n/a')} tonnes\n"
            f"- Risk: {rec.get('risk_level', 'n/a')} (Score: {rec.get('risk_score', 'n/a')})\n"
            "- Profile: Optimal Pareto trade-off between transit distance, fuel burn, and environmental hazards."
        ]
        for idx, alt in enumerate(alts[:2], 1):
            overview_lines.append(
                f"\n{idx + 1}. {alt.get('label', f'Alternative {idx}')}\n"
                f"- Distance: {_km(alt.get('distance_km'))} ({alt.get('distance_nm', 0):.0f} nm)\n"
                f"- Estimated Time: {_hours(alt.get('travel_time_hours'))}\n"
                f"- Fuel: {alt.get('fuel_tons', 'n/a')} tonnes\n"
                f"- Risk: {alt.get('risk_level', 'n/a')} (Score: {alt.get('risk_score', 'n/a')})\n"
                f"- Profile: {'Minimizes overall transit distance, accepting higher sea-ice exposure.' if idx == 1 else 'Maximizes clearance around sea ice and icebergs, incurring a longer transit.'}"
            )
        lines.append("\n".join(overview_lines))
    elif rec:
        lines.append(
            f"For the current selection, the recommended route is {_km(rec.get('distance_km'))} "
            f"({rec.get('distance_nm', 0):.0f} nm), about {_hours(rec.get('travel_time_hours'))} of "
            f"travelling, burning roughly {rec.get('fuel_tons', 'n/a')} tonnes of fuel. Risk level "
            f"is {rec.get('risk_level', 'n/a')} with a score of {rec.get('risk_score', 'n/a')}."
        )

    if rec and ("risk" in q or "safe" in q or "danger" in q or "hazard" in q) and "why" not in q:
        warnings = rec.get("warnings") or []
        lines.append(
            f"On risk: level {rec.get('risk_level', 'n/a')}, score {rec.get('risk_score', 'n/a')}. "
            f"That comes from blending sea-ice concentration at 0.35, iceberg proximity at 0.30, "
            f"weather at 0.20 and distance at 0.15."
        )
        if warnings:
            lines.append("The engine flagged: " + "; ".join(warnings))
        else:
            lines.append("No specific warnings came back for this route.")

    fuel = (named.get("fuel_estimate") or {}).get("data") or {}
    if fuel and "fuel" in q and "why" not in q:
        rec_fuel = fuel.get("recommended_fuel_tons")
        if rec_fuel is not None:
            lines.append(
                f"Fuel on the recommended route comes to about {rec_fuel:.1f} tonnes, and the "
                f"alternatives are "
                + ", ".join(
                    f"{a.get('label')} at {a.get('fuel_tons')} t" for a in fuel.get("alternatives") or []
                )
                + ". It's an estimate from the vessel's consumption rates, not a guarantee."
            )

    return lines


def _fallback_alerts(question: str, named: dict) -> list[str]:
    q = question.lower()
    alert_result = named.get("current_alerts")
    if alert_result is None:
        return [
            "I can't see the alert details from here - only the alert count. "
            "Open Alert Messages, or tell me the alert title and I'll look it up."
        ]
    alerts = (alert_result or {}).get("data") or []
    lines: list[str] = []
    if not alerts:
        lines.append(
            "There are currently 0 active hazard alerts in the system. "
            "All planned navigation corridors and route waypoints are currently within safe operational thresholds."
        )
        return lines

    if "severity" in q or "highest" in q or "worst" in q or "most urgent" in q:
        order = {"critical": 0, "high": 1, "warning": 2, "medium": 3, "low": 4, "info": 5}
        best = sorted(alerts, key=lambda a: order.get(str(a.get("severity", "")).lower(), 9))[0]
        alerts = [best]
    elif "which" in q or "highest" in q or "most" in q or "top" in q:
        alerts = alerts[:3]

    for alert in alerts[:3]:
        reason = alert.get("reason") or alert.get("message") or "the record doesn't carry a reason"
        entry = (
            f"\"{alert.get('title', 'Untitled alert')}\" - a {alert.get('severity', 'unknown')} "
            f"{alert.get('type', 'system')} alert - fired because: {reason}"
        )
        if alert.get("distance_km") is not None:
            entry += f" It's {float(alert['distance_km']):.1f} km from the selected route."
        lines.append(entry)
        if alert.get("recommended_action"):
            lines.append(f"Recommended action: {alert['recommended_action']}")
    if len(alerts) > 3:
        lines.append("Tell me the title of a specific one and I'll break that one down.")

    return lines


def _fallback_models(question: str, named: dict) -> list[str]:
    lines: list[str] = []
    conv = (named.get("model_convergence") or {}).get("data") or {}
    if conv and conv.get("models"):
        lines.append(
            "The sea-ice side runs a convolutional LSTM for the spatio-temporal forecast, a random "
            "forest as a second opinion, and a persistence baseline - which is just holding today's "
            "field and calling it tomorrow. The baseline matters because a model that doesn't beat "
            "it hasn't learned anything worth having."
        )
        for m in conv["models"]:
            metrics = m.get("metrics", {}) or {}
            rendered = ", ".join(f"{k} {v}" for k, v in metrics.items() if v is not None)
            lines.append(f"- {m.get('model')}: {rendered}")

    metrics = (named.get("model_metrics") or {}).get("data") or {}
    if metrics and metrics.get("metrics") and not conv:
        lines.append(
            f"There's {metrics.get('count')} recorded metric values across the pipelines: "
            + "; ".join(
                f"{m.get('pipeline')}/{m.get('model')} {m.get('metric_name')} = {m.get('metric_value')}"
                for m in metrics["metrics"][:10]
            )
        )

    status = (named.get("datasets_status") or {}).get("data") or {}
    if status:
        real = [d for d in status.get("datasets", []) if not d.get("demo")]
        demo = [d for d in status.get("datasets", []) if d.get("demo")]
        parts = []
        if real:
            parts.append("real data for " + ", ".join(d.get("dataset", "?") for d in real))
        if demo:
            parts.append("demo placeholders for " + ", ".join(d.get("dataset", "?") for d in demo))
        if parts:
            lines.append("On the data side right now: " + "; ".join(parts) + ".")

    return lines


def _fallback_fleet(named: dict) -> list[str]:
    ref = (named.get("fleet_reference") or {}).get("data") or {}
    if not ref:
        return []
    lines: list[str] = []

    vessels = ref.get("vessels") or []
    if vessels:
        lines.append(
            "Three vessels are configured: "
            + "; ".join(
                f"{v.get('name')} ({v.get('vessel_id')}), a {v.get('type')} rated {v.get('ice_class')} "
                f"with a {v.get('draft_m')} m draft"
                for v in vessels
            )
            + ". Ice class is the rating of what ice pressure a hull can take, and it matters as "
            "much as size - PC1 is the toughest, PC7 the least."
        )

    ports = ref.get("departure_ports") or []
    if ports:
        lines.append(
            "Departure ports: "
            + "; ".join(f"{p.get('name')} ({p.get('country')})" for p in ports)
            + ". Hobart is the default and the home of the Australian Antarctic Division; Ushuaia and "
            "Punta Arenas serve the Peninsula; Cape Town serves the Indian Ocean sector; Christchurch "
            "and Bluff are the New Zealand gateways, and Bluff is closest to the Ross Sea."
        )

    centers = ref.get("research_centers") or []
    if centers:
        lines.append(
            f"{len(centers)} research stations are available as destinations, including "
            + ", ".join(c.get("name", "?") for c in centers[:8])
            + ", among others."
        )
    return lines


def _greeting() -> str:
    return (
        "Hi, I'm Raga. I can walk you through the dashboard, explain anything on it - sea ice, "
        "icebergs, routes, risk, how the numbers are worked out - or read you the live numbers "
        "right now. What do you need?"
    )


_DEFINITION_RE = re.compile(
    r"^\s*(?:what (?:is|are|does|do) (?:a|an|the)?\s*\w+|"
    r"define (?:a|an|the)?\s*\w+|"
    r"(?:a|an|the) (?:meaning|definition) of|"
    r"what does \w+ (?:mean|stand for)|"
    r"tell me about \w+)\b"
)

# Questions that ask for a definition rather than a number.
_TERM_LOOKUP_RE = re.compile(
    r"\bwhat (?:is|are)\b|\bdefine\b|\bmeaning of\b|\bstand for\b|\bexplain the term\b"
)

# "What is the *current* concentration" shares its opening words with a
# definition question but is asking for a number.
_VALUE_HINTS = (
    "right now", "currently", "at the moment", "today", "tonight", "latest", "live",
    "how many", "how much", "forecast", "predicted", "expected", "estimate", "value",
    "level", "score", "distance", "percent", "%", "km", "nm", "tonnes", "tons", "hours",
    "now", "actual", "observed", "this week", "next 24", "next 48",
    "current", "average", "overall", "right-hand", "chart", "panel", "shown", "showing",
)


def looks_like_definition(question: str) -> bool:
    """True for "what is a growler" - a vocabulary question, not a data one."""
    q = (question or "").lower().strip()
    if not q or not _TERM_LOOKUP_RE.search(q):
        return False
    if any(hint in q for hint in _VALUE_HINTS):
        return False
    if not knowledge.matching_glossary(q):
        return False
    return bool(_DEFINITION_RE.match(q))


def build_fallback(question: str, results: list[dict], page: str | None = None) -> str:
    """Template answer used when no LLM provider is configured.

    Same personality and the same honesty rules as the LLM path: it quotes only
    numbers the backend actually returned, and it says when something is an
    estimate or demo data.
    """
    named = {r.get("name"): r for r in results if r}
    q = (question or "").lower()

    if re.search(r"\b(?:hi|hello|hey|greetings|good (?:morning|afternoon|evening))\b", q):
        return _greeting()

    if re.search(r"^(?:thanks|thank you|ta|cheers|ok|okay|cool|nice|great)\b", q):
        return "Any time. Ask me about any panel, term or number whenever you need it."

    # "How do I use the app" never needs live data - answer from the docs.
    if looks_like_howto(question) and not any(k in q for k in ("trajectory", "drift", "route", "routes", "iceberg", "concentration", "forecast", "nearest", "closest")):
        return knowledge.answer_dashboard_question(question, page)

    # "What is a growler" is a vocabulary question, so a definition - not a
    # forecast - is the right answer even when tools did return data.
    if looks_like_definition(question):
        return knowledge.answer_glossary_question(question)

    lines: list[str] = []
    is_iceberg_query = any(k in q for k in ("iceberg", "berg", "trajectory", "drift", "closest", "nearest"))
    is_route_query = any(k in q for k in ("route", "routes", "fuel", "waypoint", "recalculate", "recommended"))
    is_sea_ice_explicit = any(k in q for k in ("sea ice", "concentration", "thickness", "keel", "pack ice", "melt"))

    if is_iceberg_query:
        lines += _fallback_iceberg(question, named)
        if is_route_query:
            lines += _fallback_route(question, named)
        if is_sea_ice_explicit:
            lines += _fallback_sea_ice(question, named)
    elif is_route_query:
        lines += _fallback_route(question, named)
        if is_iceberg_query:
            lines += _fallback_iceberg(question, named)
        if is_sea_ice_explicit:
            lines += _fallback_sea_ice(question, named)
    else:
        lines += _fallback_sea_ice(question, named)
        lines += _fallback_iceberg(question, named)
        lines += _fallback_route(question, named)

    only_alerts = False
    if "alert" in q or "notification" in q:
        alert_lines = _fallback_alerts(question, named)
        # The "I can't see the alert details" reply is already a complete
        # answer with its own next step - no tail needed.
        only_alerts = bool(alert_lines) and "can't see the alert details" in alert_lines[0]
        # An alert question is about the alert, not about the whole dashboard,
        # so lead with it and drop the unrelated numbers.
        if only_alerts:
            lines = alert_lines
        else:
            lines = alert_lines + lines

    if any(k in q for k in ("model", "accuracy", "accurate", "metric", "mae", "rmse", "how good")):
        lines += _fallback_models(question, named)

    if any(k in q for k in ("vessel", "ship", "fleet", "port", "station", "icebreaker", "ice class")):
        lines += _fallback_fleet(named)

    if q in ("thanks", "") or not q:
        return _greeting()

    if not lines:
        if _HOWTO_RE.search(q) or any(k in q for k in ("page", "panel", "button", "dashboard", "app", "chart", "map", "filter", "dropdown")):
            return knowledge.answer_dashboard_question(question, page)
        # "What is a growler" is a vocabulary question, not a data question.
        term = knowledge.answer_glossary_question(question)
        if term:
            return term
        return (
            "I don't have a number for that one. I can read you current sea-ice concentration, "
            "iceberg positions and drift, distances, route distance, time, fuel and risk, explain "
            "any alert, or walk you through any part of the dashboard. Which of those is closest?"
        )

    tail = " Happy to go deeper on any of that."
    if only_alerts:
        return "\n\n".join(lines)
    if len(lines) == 1 and len(lines[0]) < 200:
        tail = " Want the underlying numbers, or how any of it is worked out?"
    return "\n\n".join(lines) + tail
