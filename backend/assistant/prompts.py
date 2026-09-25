"""Prompt templates and context formatting for the DSS assistant.

All phrasing rules live here so the LLM policy is in one place and the
template fallback follows the same honesty rules as the LLM path.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

SYSTEM_PROMPT = """You are the navigation analyst assistant for the Antarctic Navigation Decision Support System (Problem Statement 26059). You are directly assisting a ship captain.

You answer questions about sea-ice forecasts, iceberg drift predictions, route recommendations, distances and fuel estimates. You ALWAYS ground your answers about navigation and data in the CONTEXT block provided at the end of the user message, which comes from the project's own backend API. However, you are also capable of natural conversation. If the captain greets you (e.g., "Hi", "Hello"), respond naturally and politely, asking how you can assist with their voyage or project today.

Hard rules:
1. NEVER claim a route is guaranteed safe. Routes are planning aids produced under model assumptions.
2. Distinguish OBSERVED data from PREDICTED data explicitly (use words like "observed", "predicted", "forecast", "projected").
3. Distinguish DEMO (synthetic) data from real data. If the context marks something "demo", say so clearly and state the result carries no real-world information.
4. Explain uncertainty: say when a value is a model estimate, a baseline, or lacks validated skill. Do not invent confidence intervals or accuracy numbers.
5. Never invent scientific facts, model accuracy, or metric values that are not in the context.
6. Never claim live satellite imagery or live remote-sensing data unless the context explicitly says real observations were available.
7. Quote specific numbers and identifiers (iceberg IDs, route IDs, vessel names) exactly as given in the context.
8. When the context does not contain a requested value, say "the backend did not provide that" and suggest a related question you CAN answer.
9. Be concise, professional, and structured. Use short paragraphs and bullet lists when helpful.
10. Mention your data sources in the reply (e.g. "sea-ice forecast", "iceberg trajectory", "distance tool") so the user sees what you used.
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
    return "\n\n".join(blocks) or "[no data was retrieved]"


def build_user_prompt(question: str, context_report: str) -> str:
    return (
        "Question from the user:\n"
        + question
        + "\n\nCONTEXT (from the DSS backend API, may be demo data):\n"
        + context_report
        + "\n\nAnswer the question using ONLY this context, following the system rules."
    )


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


def build_fallback(question: str, results: list[dict]) -> str:
    """Template answer used when no LLM provider is configured.

    Follows the same honesty rules as the LLM path: quotes only the numbers
    actually returned by the backend tools.
    """
    named = {r.get("name"): r for r in results if r}
    lines: list[str] = []
    demo_names = [r["name"] for r in results if r.get("demo")]
    any_real = any(r for r in results if not r.get("demo"))

    q = question.lower()

    # 1 / 8: sea-ice concentration forecast
    if any(n in q for n in ("sea-ice", "sea ice", "concentration", "sea_ice")):
        fc = named.get("sea_ice_forecast")
        if fc and fc.get("data"):
            d = fc["data"]
            fc_text = (
                f"Captain, the sea-ice forecast for the next {d.get('horizon_hours', 24)} h "
                f"(using the {d.get('model', 'persistence')} model) estimates a mean concentration of "
                f"{d.get('mean_concentration', 0) * 100:.1f}% and a maximum of "
                f"{d.get('max_concentration', 0) * 100:.1f}%. The grid coverage is {d.get('coverage_pct', 0):.1f}%. "
                f"Please note this is a projected field, not a direct observation."
            )
            if d.get("model_used_real") is False:
                fc_text += " The model has not been trained on real observations."
            if d.get("skill_note"):
                fc_text += f" Skill note: {d['skill_note']}."
            lines.append(fc_text)
        else:
            lines.append("I could not retrieve a sea-ice forecast from the backend.")

    # 8 / 8: actual vs predicted sea ice
    if "actual" in q and any(n in q for n in ("sea", "ice")):
        cur = named.get("sea_ice_current")
        fc = named.get("sea_ice_forecast")
        if cur and fc and cur.get("data") and fc.get("data"):
            cm = cur["data"].get("mean_concentration")
            fm = fc["data"].get("mean_concentration")
            if cm is not None and fm is not None:
                diff = abs(fm - cm)
                lines.append(
                    f"Observed (current) field has a mean concentration of {cm * 100:.1f}%; "
                    f"the {fc['data'].get('horizon_hours', 24)} h forecast estimates "
                    f"{fm * 100:.1f}% — an absolute mean difference of {diff * 100:.1f} percent "
                    f"points. The current field is treated as the observation; the forecast is "
                    f"a projection, so the difference is not a skill statistic."
                )
        if "climatology" in q:
            lines.append("I do not have a climatology baseline in the retrieved data.")

    # 2 / 8: iceberg trajectory / where will it move
    if any(n in q for n in ("where will", "move", "trajectory", "drift")) and "next 24" in q:
        tr = named.get("iceberg_trajectory")
        if tr and tr.get("data"):
            d = tr["data"]
            obs = d.get("observed_positions") or []
            pred = d.get("predicted_positions") or []
            lines.append(
                f"Captain, for Iceberg {d.get('iceberg_id')}, I have {len(obs)} observed position(s) and "
                f"{len(pred)} predicted position(s) available."
            )
            if obs:
                last = obs[-1]
                lines.append(
                    f"Latest observed position: ({last.get('latitude'):.3f}, {last.get('longitude'):.3f})."
                )
            if d.get("predicted_latitude") is not None:
                lines.append(
                    f"The predicted position after {d.get('prediction_model', 'persistence')} "
                    f"projection is ({d.get('predicted_latitude'):.3f}, {d.get('predicted_longitude'):.3f}). "
                    f"This is a projection, not an observation."
                )
            else:
                lines.append("No prediction was available for this iceberg.")
        else:
            lines.append("I could not find that iceberg or its trajectory.")

    # 7 / 8: factors affecting drift (scientific background, no fake numbers)
    if "drift" in q or "factors affect" in q:
        lines.append(
            "Iceberg drift is governed mainly by: ocean currents (dominant for large bergs), "
            "surface wind drag on the vast above-water area, coupling with surrounding pack ice, "
            "the Coriolis effect, basal/water-depth drag when bergs approach shallow shelf regions, "
            "and iceberg size/shape (small bergs follow wind more than currents). "
            "This system tracks position history and models short-horizon movement with a "
            "persistence baseline (plus an LSTM when trained); those models are NOT yet trained "
            "on real observations here, so any quoted drift, while physically motivated, carries "
            "no validated real-world accuracy."
        )

    # 3 / 8: distance between two icebergs
    if "distance between" in q or ("distance" in q and "iceberg" in q):
        dist = named.get("iceberg_distance")
        if dist and dist.get("data"):
            d = dist["data"]
            lines.append(
                f"Captain, the distance between {d.get('iceberg_a')} and {d.get('iceberg_b')} is "
                f"{d.get('distance_km', 0):.1f} km ({d.get('distance_nm', 0):.1f} nm). "
                f"This is the great-circle distance based on their latest reported positions."
            )
        else:
            lines.append("I could not calculate that distance (one of the iceberg IDs may be unknown).")

    # which iceberg is closest
    if "closest" in q or "nearest" in q:
        cl = named.get("closest_iceberg")
        if cl and cl.get("data"):
            d = cl["data"]
            lines.append(
                f"Captain, the closest tracked iceberg to your reference position "
                f"({d.get('reference_position_lat')}, {d.get('reference_position_lon')}) is "
                f"{d.get('closest_iceberg')} at a distance of about {d.get('closest_distance_km')} km. "
                f"({d.get('how')})"
            )
        else:
            lines.append("I could not identify the closest iceberg.")

    # 5 / 8: fuel comparison
    if "fuel" in q and ("lower" in q or "compare" in q or "which" in q):
        fe = named.get("fuel_estimate")
        if fe and fe.get("data"):
            d = fe["data"]
            rec_fuel = d.get("recommended_fuel_tons")
            alt_text = ", ".join(
                f"{a.get('label', 'alt')}: {a.get('fuel_tons')} t" for a in d.get("alternatives") or []
            )
            if rec_fuel is not None:
                lines.append(
                    f"Recommended route ({d.get('recommended_preference')}): "
                    f"{rec_fuel:.1f} t estimated fuel."
                )
            else:
                lines.append("The backend did not return a fuel estimate for the recommended route.")
            if alt_text:
                lines.append(f"Alternatives — {alt_text}.")
            lines.append(
                "Fuel is estimated by the route engine from vessel consumption rates; it is an "
                "estimate, not a guarantee."
            )
        else:
            lines.append("I could not retrieve fuel estimates.")

    # 4 / 8 + risks: route details
    if any(n in q for n in ("route", "fuel", "risk")):
        rte = named.get("route_details")
        if rte and rte.get("data"):
            d = rte["data"]
            rec = d.get("recommended") or {}
            if rec:
                lines.append(
                    f"Captain, the recommended route for {d.get('vessel_id')} (preference: "
                    f"'{d.get('preference')}') is estimated at {rec.get('distance_km', 0):.0f} km "
                    f"({rec.get('distance_nm', 0):.0f} nm), taking approximately {rec.get('travel_time_hours', 0):.1f} h. "
                    f"Estimated fuel is {rec.get('fuel_tons', 0) if rec.get('fuel_tons') is not None else 'n/a'} t, "
                    f"with a risk level assessed as {rec.get('risk_level', 'n/a')} (score {rec.get('risk_score', 'n/a')})."
                )
            alts = d.get("alternatives") or []
            if alts:
                lines.append(
                    "Alternatives: "
                    + "; ".join(
                        f"{a.get('label', 'alt')}: {a.get('distance_km', 0):.0f} km, "
                        f"{a.get('travel_time_hours', 0):.1f} h, fuel {a.get('fuel_tons', 'n/a')} t, "
                        f"risk {a.get('risk_level', 'n/a')}"
                        for a in alts
                    )
                    + "."
                )
        else:
            lines.append("I could not compute a route.")

    if "risks" in q or "safety" in q:
        rte = named.get("route_details")
        if rte and rte.get("data"):
            rec = rte["data"].get("recommended") or {}
            warnings = rec.get("warnings") or []
            lines.append(
                f"Risk summary for the selected route: level {rec.get('risk_level', 'n/a')} "
                f"(score {rec.get('risk_score', 'n/a')})."
            )
            if warnings:
                for w in warnings:
                    lines.append(f"* {w}")
            else:
                lines.append("* The backend reported no explicit warnings for this route.")
        else:
            lines.append("I could not retrieve route risk information.")

    if "why" in q and "route" in q and not any(n in q for n in ("risk", "fuel", "distance")):
        rte = named.get("route_details")
        if rte and rte.get("data"):
            rec = rte["data"].get("recommended") or {}
            alts = rte["data"].get("alternatives") or []
            lines.append(
                "Captain, I selected this route because it provides the best overall balance "
                f"for your selected preference ('{rte['data'].get('preference')}'). It optimally balances the distance "
                f"({rec.get('distance_km', 0):.0f} km), travel time ({rec.get('travel_time_hours', 0):.1f} h), "
                f"estimated fuel, and the assessed risk level ({rec.get('risk_level', 'n/a')}). While it might not "
                f"be the absolute shortest or cheapest compared to the {len(alts)} alternative(s), it is the most appropriate and balanced choice for these conditions."
            )

    if "how many" in q and "iceberg" in q:
        il = named.get("iceberg_list")
        if il and il.get("data"):
            lines.append(f"There are {il['data'].get('count', 0)} icebergs currently tracked.")
        else:
            lines.append("I could not retrieve the iceberg list.")

    if not lines:
        if any(greet in q for greet in ("hi", "hello", "hey", "greetings")):
            lines.append(
                "Greetings, Captain. How can I assist you with your voyage or project today? "
                "I can help with sea-ice forecasts, iceberg positions, distances, routes, fuel estimates, and risks."
            )
        else:
            lines.append(
                "I'm sorry, Captain, but I couldn't find any relevant data for that request. "
                "Please ask me about sea-ice forecasts, iceberg positions, distances, routes, fuel estimates, or risks."
            )

    return "\n\n".join(lines)