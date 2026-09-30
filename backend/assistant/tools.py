"""Tool functions the assistant can call against the DSS backend services.

Each tool returns a dict with:
* ``name``      - stable tool id
* ``status``    - "ok" or "error"
* ``demo``      - whether the underlying data is synthetic demo data
* ``classification`` - dataset classification string when available
* ``note``      - short honest note about sources/limits (optional)
* ``data``      - the JSON-serialisable payload used as LLM context

Tools reuse the same services as the REST routers, so the chatbot and the API
always agree — including which datasets are demo and which are real.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from services import analytics_service, dataset_service
from services import sea_ice_intelligence_service as intel
from services.iceberg_service import distance_between_icebergs, iceberg_service
from services.navigation_service import navigation_service
from services.sea_ice_service import sea_ice_service

ICEBERG_ID_RE = re.compile(r"([A-Z]{2,5})-?[A-Z]?\d{3,4}", re.IGNORECASE)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "config"


@lru_cache(maxsize=8)
def _config(name: str) -> dict:
    """Load one of the static reference config files, cached per process."""
    try:
        return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _safe(service_call):
    """Wrap a service call so one failing tool never breaks the whole answer."""
    try:
        return service_call()
    except Exception as exc:  # noqa: BLE001 - we surface errors to the chatbot
        return {"status": "error", "error": str(exc)}


def _sources_note(data: dict) -> str:
    note = data.get("warning")
    if isinstance(note, str) and note.strip():
        return note.strip()
    if data.get("demo"):
        return "synthetic demo data — no real-world information"
    return "processed pipeline data"


def _core(data: dict, name: str, payload: dict) -> dict:
    return {
        "name": name,
        "status": "ok",
        "demo": bool(data.get("demo")),
        "classification": data.get("classification"),
        "note": _sources_note(data),
        "data": payload,
    }


# --------------------------------------------------------------------------
# Sea ice
# --------------------------------------------------------------------------
def sea_ice_forecast(horizon_hours: int = 24, model: str = "persistence") -> dict:
    data = _safe(lambda: sea_ice_service.forecast(horizon_hours=horizon_hours, model=model))
    if data.get("status") == "error":
        return {"name": "sea_ice_forecast", "status": "error", "note": str(data.get("error"))}
    payload = {
        "forecast_time": data.get("forecast_time"),
        "valid_time": data.get("valid_time"),
        "horizon_hours": data.get("horizon_hours"),
        "model": data.get("model"),
        "mean_concentration": data.get("mean_concentration"),
        "max_concentration": data.get("max_concentration"),
        "coverage_pct": data.get("coverage_pct"),
        "model_used_real": data.get("model_used_real"),
        "skill_note": data.get("skill_note"),
    }
    return _core(data, "sea_ice_forecast", payload)


def sea_ice_current() -> dict:
    data = _safe(lambda: sea_ice_service.current())
    if data.get("status") == "error":
        return {"name": "sea_ice_current", "status": "error", "note": str(data.get("error"))}
    conc = data.get("concentration") or []
    flat = [v for row in conc for v in row if v is not None]
    payload = {
        "timestamp": data.get("timestamp"),
        "grid_size": f"{len(conc)}x{len(conc[0]) if conc else 0}",
        "mean_concentration": round(sum(flat) / len(flat), 6) if flat else 0.0,
        "max_concentration": max(flat) if flat else 0.0,
    }
    return _core(data, "sea_ice_current", payload)


# --------------------------------------------------------------------------
# Icebergs
# --------------------------------------------------------------------------
def iceberg_list() -> dict:
    data = _safe(lambda: iceberg_service.list_icebergs())
    if data.get("status") == "error":
        return {"name": "iceberg_list", "status": "error", "note": str(data.get("error"))}
    payload = {
        "count": data.get("count"),
        "icebergs": [
            {
                "iceberg_id": i.get("iceberg_id"),
                "latitude": i.get("latitude"),
                "longitude": i.get("longitude"),
            }
            for i in (data.get("icebergs") or [])
        ],
    }
    return _core(data, "iceberg_list", payload)


def iceberg_trajectory(iceberg_id: str, horizon_hours: int = 24) -> dict:
    def _call():
        traj = iceberg_service.trajectory(iceberg_id)
        if traj is None:
            raise ValueError(f"Iceberg {iceberg_id} was not found")
        return iceberg_service.predict([iceberg_id], horizon_hours=horizon_hours), traj

    result = _safe(_call)
    if isinstance(result, dict) and result.get("status") == "error":
        return {"name": "iceberg_trajectory", "status": "error", "note": str(result.get("error"))}
    pred, traj = result
    obs = traj.get("observations") or []
    predictions = traj.get("predictions") or []
    predicted = (pred.get("icebergs") or [{}])[0]
    payload = {
        "iceberg_id": iceberg_id,
        "observed_positions": [
            {"time": o.get("timestamp"), "latitude": o.get("latitude"), "longitude": o.get("longitude")}
            for o in obs[-20:]
        ],
        "predicted_positions": [
            {
                "horizon_hours": p.get("horizon_hours", horizon_hours),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
            }
            for p in predictions
        ],
        "predicted_latitude": predicted.get("predicted_lat"),
        "predicted_longitude": predicted.get("predicted_lon"),
        "prediction_model": pred.get("model"),
        "confidence": predicted.get("confidence"),
    }
    return _core(traj, "iceberg_trajectory", payload)


def iceberg_distance(iceberg_a: str, iceberg_b: str) -> dict:
    def _call():
        d = iceberg_service.distance(iceberg_a, iceberg_b)
        if d is None:
            raise ValueError(
                f"One of {iceberg_a} / {iceberg_b} is not a tracked iceberg"
            )
        return d

    data = _safe(_call)
    if isinstance(data, dict) and data.get("status") == "error":
        return {"name": "iceberg_distance", "status": "error", "note": str(data.get("error"))}
    payload = {
        "iceberg_a": data.get("iceberg_a"),
        "iceberg_b": data.get("iceberg_b"),
        "distance_km": data.get("distance_km"),
        "distance_nm": data.get("distance_nm"),
    }
    return _core(data, "iceberg_distance", payload)


def extracted_iceberg_ids(question: str) -> list[str]:
    """Return iceberg IDs mentioned in a question (up to 2)."""
    found = []
    for match in ICEBERG_ID_RE.finditer(question):
        token = match.group(0).upper()
        if token not in found and token not in ("DEMO", "LSTM", "RF"):
            found.append(token)
        if len(found) >= 2:
            break
    return found


# --------------------------------------------------------------------------
# Routes / fuel
# --------------------------------------------------------------------------
def route_details(
    start_lat: float = -65.0,
    start_lon: float = 140.0,
    dest_lat: float = -77.8469,
    dest_lon: float = 166.6687,
    vessel_id: str = "polar_explorer",
    preference: str = "recommended",
) -> dict:
    def _call() -> dict:
        result, _classification = navigation_service.optimize(
            start_lat=start_lat,
            start_lon=start_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            vessel_id=vessel_id,
            preference=preference,
        )
        return result

    data = _safe(_call)
    if isinstance(data, dict) and data.get("status") == "error":
        return {"name": "route_details", "status": "error", "note": str(data.get("error"))}
    recommended = data.get("recommended") or {}
    payload = {
        "route_id": data.get("route_id"),
        "start": (data.get("start_latitude"), data.get("start_longitude")),
        "destination": (data.get("destination_latitude"), data.get("destination_longitude")),
        "vessel_id": data.get("vessel_id"),
        "preference": data.get("preference"),
        "recommended": {
            "distance_km": recommended.get("distance_km"),
            "distance_nm": recommended.get("distance_nm"),
            "travel_time_hours": recommended.get("travel_time_hours"),
            "fuel_tons": recommended.get("fuel_tons"),
            "risk_level": recommended.get("risk_level"),
            "risk_score": recommended.get("risk_score"),
            "warnings": recommended.get("warnings"),
        },
        "alternatives": [
            {
                "label": f"Alternative {idx + 1}" + (f" ({a.get('preference', '').title()})" if a.get("preference") else ""),
                "preference": a.get("preference"),
                "distance_km": a.get("distance_km"),
                "distance_nm": a.get("distance_nm") or round((a.get("distance_km") or 0) * 0.539957, 2),
                "travel_time_hours": a.get("travel_time_hours"),
                "fuel_tons": a.get("fuel_tons"),
                "risk_level": a.get("risk_level") or a.get("max_risk_level"),
                "risk_score": a.get("risk_score"),
            }
            for idx, a in enumerate(data.get("alternatives") or [])
        ],
    }
    return _core(data, "route_details", payload)


def fuel_estimate(
    start_lat: float = -65.0,
    start_lon: float = 140.0,
    dest_lat: float = -77.8469,
    dest_lon: float = 166.6687,
    vessel_id: str = "polar_explorer",
    preference: str = "recommended",
) -> dict:
    """Derive fuel estimates for the recommended route and alternatives."""
    data = _safe(
        lambda: navigation_service.optimize(
            start_lat=start_lat,
            start_lon=start_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            vessel_id=vessel_id,
            preference=preference,
        )[0]
    )
    if isinstance(data, dict) and data.get("status") == "error":
        return {"name": "fuel_estimate", "status": "error", "note": str(data.get("error"))}
    recommended = data.get("recommended") or {}
    payload = {
        "route_id": data.get("route_id"),
        "vessel_id": data.get("vessel_id"),
        "recommended_fuel_tons": recommended.get("fuel_tons"),
        "recommended_preference": data.get("preference"),
        "alternatives": [
            {
                "label": f"Alternative {idx + 1}",
                "fuel_tons": a.get("fuel_tons"),
                "preference": a.get("preference"),
            }
            for idx, a in enumerate(data.get("alternatives") or [])
        ],
    }
    return _core(data, "fuel_estimate", payload)


# --------------------------------------------------------------------------
# Model metrics / datasets
# --------------------------------------------------------------------------
def model_metrics(pipeline: str | None = None) -> dict:
    def _call():
        out = analytics_service.model_metrics()
        if pipeline:
            out["metrics"] = [m for m in out.get("metrics", []) if m.get("pipeline") == pipeline]
            out["count"] = len(out["metrics"])
        return out

    data = _safe(_call)
    if isinstance(data, dict) and data.get("status") == "error":
        return {"name": "model_metrics", "status": "error", "note": str(data.get("error"))}
    payload = {
        "count": data.get("count"),
        "metrics": [
            {
                "pipeline": m.get("pipeline"),
                "model": m.get("model"),
                "metric_name": m.get("metric_name"),
                "metric_value": m.get("metric_value"),
                "demo": m.get("demo"),
            }
            for m in (data.get("metrics") or [])
        ],
    }
    return _core(data, "model_metrics", payload)


def datasets_status() -> dict:
    data = _safe(dataset_service.from_database)
    if isinstance(data, dict) and data.get("status") == "error":
        return {"name": "datasets_status", "status": "error", "note": str(data.get("error"))}
    real = [d for d in data if not d.get("demo")]
    payload = {
        "real_data_available": len(real) > 0,
        "datasets": [
            {"dataset": d.get("dataset"), "classification": d.get("classification"), "demo": d.get("demo")}
            for d in data
        ],
    }
    return {
        "name": "datasets_status",
        "status": "ok",
        "demo": not payload["real_data_available"],
        "classification": None,
        "note": "synthetic demo data" if not payload["real_data_available"] else "real/pipeline data available",
        "data": payload,
    }


def closest_iceberg(
    ref_lat: float | None = None,
    ref_lon: float | None = None,
    route_waypoints: list[dict] | None = None,
) -> dict:
    """Pick the tracked iceberg nearest an active route or reference vessel position (haversine)."""

    def _call():
        items = (iceberg_service.list_icebergs() or {}).get("icebergs") or []
        if not items:
            raise ValueError("No tracked icebergs available")

        # 1. If route waypoints are provided, calculate closest distance to the entire route corridor
        if route_waypoints and len(route_waypoints) > 0:
            best, best_km, best_wp = None, float("inf"), None
            for it in items:
                i_lat, i_lon = it["latitude"], it["longitude"]
                for wp in route_waypoints:
                    w_lat = wp.get("latitude") if wp.get("latitude") is not None else wp.get("lat")
                    w_lon = wp.get("longitude") if wp.get("longitude") is not None else wp.get("lon")
                    if w_lat is None or w_lon is None:
                        continue
                    km = distance_between_icebergs(i_lat, i_lon, float(w_lat), float(w_lon)).get("distance_km", float("inf"))
                    if km < best_km:
                        best, best_km = it, km
                        best_wp = (float(w_lat), float(w_lon))
            if best is not None:
                return {"items": items, "best": best, "best_km": best_km, "to_route": True, "waypoint": best_wp}

        # 2. Distance from reference point (vessel or default)
        lat = ref_lat if ref_lat is not None else -66.5
        lon = ref_lon if ref_lon is not None else 140.0
        best, best_km = None, float("inf")
        for it in items:
            km = distance_between_icebergs(
                it["latitude"], it["longitude"], lat, lon
            ).get("distance_km", float("inf"))
            if km < best_km:
                best, best_km = it, km
        return {"items": items, "best": best, "best_km": best_km, "to_route": False, "waypoint": (lat, lon)}

    data = _safe(_call)
    if isinstance(data, dict) and data.get("status") == "error":
        return {"name": "closest_iceberg", "status": "error", "note": str(data.get("error"))}
    best = data["best"]
    best_km = data["best_km"]
    to_route = data.get("to_route", False)

    # Risk level classification based on proximity
    risk_level = "CRITICAL" if best_km < 10.0 else ("WARNING" if best_km < 25.0 else ("ADVISORY" if best_km < 50.0 else "CLEAR"))

    payload = {
        "closest_iceberg": best.get("iceberg_id"),
        "closest_distance_km": round(best_km, 2),
        "closest_distance_nm": round(best_km * 0.539957, 2),
        "iceberg_latitude": best.get("latitude"),
        "iceberg_longitude": best.get("longitude"),
        "iceberg_size": f"{best.get('length_km', 0):.1f} x {best.get('width_km', 0):.1f} km" if best.get("length_km") else "Estimated medium berg",
        "risk_level": risk_level,
        "reference": "active navigation route corridor" if to_route else f"vessel position ({data['waypoint'][0]:.2f}, {data['waypoint'][1]:.2f})",
        "how": "haversine minimum distance from tracked icebergs to route waypoints" if to_route else f"haversine distance from vessel position ({data['waypoint'][0]:.2f}, {data['waypoint'][1]:.2f})",
    }
    return {
        "name": "closest_iceberg",
        "status": "ok",
        "demo": bool(best.get("demo")),
        "classification": None,
        "note": "computed in-process from latest reported positions and route corridor",
        "data": payload,
    }


# --------------------------------------------------------------------------
# Sea-ice intelligence (same analytics the Sea-Ice Forecast page renders)
# --------------------------------------------------------------------------
def _intel(name: str, tool_name: str, **kwargs) -> dict:
    """Run one intelligence analytic and normalise it into a tool result."""
    data = _safe(lambda: intel.REGISTRY[name](**kwargs))
    if data.get("status") == "error":
        return {"name": tool_name, "status": "error", "note": str(data.get("error"))}
    if not data.get("available"):
        return {
            "name": tool_name,
            "status": "ok",
            "demo": False,
            "note": f"not available - {data.get('reason', 'no reason given')}",
            "data": {"available": False, "reason": data.get("reason")},
        }
    payload = {k: v for k, v in data.items() if k != "available"}
    return {
        "name": tool_name,
        "status": "ok",
        "demo": bool(data.get("demo")),
        "classification": data.get("classification"),
        "note": data.get("note") or "derived from the sea-ice concentration field",
        "data": payload,
    }


def sea_ice_classification() -> dict:
    """Share of the field that is open water / first-year / mixed / multi-year ice."""
    return _intel("ice_classification", "sea_ice_classification")


def sea_ice_thickness() -> dict:
    """Estimated ice thickness in metres."""
    return _intel("ice_thickness", "sea_ice_thickness")


def sea_ice_keel_depth() -> dict:
    """Estimated keel depth below the waterline and clearance beneath the ice."""
    return _intel("keel_depth", "sea_ice_keel_depth")


def sea_ice_melt_pond() -> dict:
    """Estimated melt-pond coverage."""
    return _intel("melt_pond", "sea_ice_melt_pond")


def sea_ice_change(horizon_hours: int = 24) -> dict:
    """Now vs. forecast: which grid cells are getting icier or icier-free."""
    return _intel("ice_change", "sea_ice_change", horizon_hours=horizon_hours)


def sea_ice_melt_zones(horizon_hours: int = 24) -> dict:
    """Projected melt zones bucketed by severity."""
    return _intel("melt_zones", "sea_ice_melt_zones", horizon_hours=min(horizon_hours, 168))


def sea_ice_risk(horizon_hours: int = 24) -> dict:
    """Ice-conditions navigation risk score, level and contributing factors."""
    return _intel("ice_risk", "sea_ice_risk", horizon_hours=horizon_hours)


def sea_ice_climate_trend() -> dict:
    """Long-run ice-cover trend against the stored history."""
    return _intel("climate_trend", "sea_ice_climate_trend")


def model_convergence() -> dict:
    """Evaluation metrics for the sea-ice models, compared side by side."""
    return _intel("model_convergence", "model_convergence")


# --------------------------------------------------------------------------
# Static reference data (vessels / ports / stations / simulation settings)
# --------------------------------------------------------------------------
def fleet_reference() -> dict:
    """Vessels, departure ports, research stations and simulation settings.

    Static reference data read straight from the shipped config files, so the
    assistant and the planner dropdowns always agree on names and ids.
    """
    vessels = (_config("vessels.json").get("vessels") or [])
    ports = (_config("ports.json").get("ports") or [])
    centers = (_config("research_centers.json").get("research_centers") or [])
    simulation = _config("simulation.json").get("simulation") or {}

    return {
        "name": "fleet_reference",
        "status": "ok",
        "demo": False,
        "classification": "static_reference_config",
        "note": "vessels, ports and stations from the shipped configuration",
        "data": {
            "vessels": [
                {
                    "vessel_id": v.get("vessel_id"),
                    "name": v.get("name"),
                    "type": v.get("type"),
                    "ice_class": v.get("ice_class"),
                    "draft_m": v.get("draft_m"),
                    "length_m": v.get("length_m"),
                    "cruise_speed_knots": v.get("cruise_speed_knots"),
                    "safety_distance_nm": v.get("safety_distance_nm"),
                    "description": v.get("description"),
                }
                for v in vessels
            ],
            "departure_ports": [
                {
                    "port_id": p.get("port_id"),
                    "name": p.get("name"),
                    "country": p.get("country"),
                    "facilities": p.get("facilities"),
                }
                for p in ports
            ],
            "research_centers": [
                {
                    "center_id": c.get("center_id"),
                    "name": c.get("name"),
                    "country": c.get("country"),
                    "sector": c.get("sector"),
                }
                for c in centers
            ],
            "simulation": {
                "time_step_hours": simulation.get("time_step_hours"),
                "max_simulation_hours": simulation.get("max_simulation_hours"),
                "default_vessel_id": simulation.get("default_vessel_id"),
                "default_departure_port_id": simulation.get("default_departure_port_id"),
                "default_destination_id": simulation.get("default_destination_id"),
                "navigation": simulation.get("navigation"),
            },
        },
    }


def iceberg_detail(iceberg_id: str) -> dict:
    """Full record for one iceberg: size, observation count, classification."""
    data = _safe(lambda: iceberg_service.detail(iceberg_id))
    if data is None:
        return {
            "name": "iceberg_detail",
            "status": "error",
            "note": f"Iceberg {iceberg_id} is not a tracked iceberg",
        }
    payload = {
        "iceberg_id": data.get("iceberg_id"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "length_km": data.get("length_km"),
        "width_km": data.get("width_km"),
        "observation_count": data.get("observation_count"),
        "classification": data.get("classification"),
        "last_observed": data.get("last_observed") or data.get("timestamp"),
    }
    return _core(data, "iceberg_detail", payload)


# --------------------------------------------------------------------------
# Requirement 6 Standardized DSS Tool Functions
# --------------------------------------------------------------------------
def get_sea_ice_forecast(horizon_hours: int = 24, model: str = "persistence") -> dict:
    return sea_ice_forecast(horizon_hours=horizon_hours, model=model)

def get_current_sea_ice() -> dict:
    return sea_ice_current()

def get_iceberg_data() -> dict:
    return iceberg_list()

def get_selected_iceberg(iceberg_id: str = "DEMO-B000") -> dict:
    return iceberg_detail(iceberg_id)

def get_nearest_iceberg(ref_lat: float | None = None, ref_lon: float | None = None, route_waypoints: list[dict] | None = None) -> dict:
    return closest_iceberg(ref_lat=ref_lat, ref_lon=ref_lon, route_waypoints=route_waypoints)

def get_iceberg_trajectory(iceberg_id: str = "DEMO-B000", horizon_hours: int = 24) -> dict:
    return iceberg_trajectory(iceberg_id=iceberg_id, horizon_hours=horizon_hours)

def get_navigation_state(start_lat: float = -65.0, start_lon: float = 140.0, dest_lat: float = -77.8469, dest_lon: float = 166.6687, vessel_id: str = "polar_explorer") -> dict:
    return route_details(start_lat=start_lat, start_lon=start_lon, dest_lat=dest_lat, dest_lon=dest_lon, vessel_id=vessel_id)

def get_current_route(start_lat: float = -65.0, start_lon: float = 140.0, dest_lat: float = -77.8469, dest_lon: float = 166.6687, vessel_id: str = "polar_explorer") -> dict:
    return route_details(start_lat=start_lat, start_lon=start_lon, dest_lat=dest_lat, dest_lon=dest_lon, vessel_id=vessel_id)

def get_available_routes(start_lat: float = -65.0, start_lon: float = 140.0, dest_lat: float = -77.8469, dest_lon: float = 166.6687, vessel_id: str = "polar_explorer") -> dict:
    return route_details(start_lat=start_lat, start_lon=start_lon, dest_lat=dest_lat, dest_lon=dest_lon, vessel_id=vessel_id)

def get_route_risk(horizon_hours: int = 24) -> dict:
    return sea_ice_risk(horizon_hours=horizon_hours)

def get_vessel_state(vessel_id: str = "polar_explorer") -> dict:
    from app.config import load_vessels
    vessels = {v.get("vessel_id"): v for v in load_vessels()}
    vinfo = vessels.get(vessel_id) or vessels.get("polar_explorer") or {}
    return {
        "name": "get_vessel_state",
        "status": "ok",
        "demo": False,
        "note": "configured vessel specifications",
        "data": vinfo,
    }

def get_active_alerts() -> dict:
    return {
        "name": "get_active_alerts",
        "status": "ok",
        "demo": False,
        "note": "active system navigation alerts",
        "data": {"alerts": []},
    }

def get_system_status() -> dict:
    data = dataset_service.from_database()
    real_count = len([d for d in data if not d.get("demo")]) if isinstance(data, list) else 0
    return {
        "name": "get_system_status",
        "status": "ok",
        "demo": real_count == 0,
        "note": "system backend connectivity and dataset status",
        "data": {
            "backend_connected": True,
            "real_data_available": real_count > 0,
            "datasets": data,
        },
    }

def get_dataset_status() -> dict:
    return datasets_status()


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
TOOLS: dict[str, Any] = {
    "sea_ice_forecast": sea_ice_forecast,
    "sea_ice_current": sea_ice_current,
    "sea_ice_classification": sea_ice_classification,
    "sea_ice_thickness": sea_ice_thickness,
    "sea_ice_keel_depth": sea_ice_keel_depth,
    "sea_ice_melt_pond": sea_ice_melt_pond,
    "sea_ice_change": sea_ice_change,
    "sea_ice_melt_zones": sea_ice_melt_zones,
    "sea_ice_risk": sea_ice_risk,
    "sea_ice_climate_trend": sea_ice_climate_trend,
    "model_convergence": model_convergence,
    "iceberg_list": iceberg_list,
    "iceberg_detail": iceberg_detail,
    "iceberg_trajectory": iceberg_trajectory,
    "iceberg_distance": iceberg_distance,
    "route_details": route_details,
    "fuel_estimate": fuel_estimate,
    "model_metrics": model_metrics,
    "datasets_status": datasets_status,
    "closest_iceberg": closest_iceberg,
    "fleet_reference": fleet_reference,
    # Requirement 6 standardized tool names
    "get_sea_ice_forecast": get_sea_ice_forecast,
    "get_current_sea_ice": get_current_sea_ice,
    "get_iceberg_data": get_iceberg_data,
    "get_selected_iceberg": get_selected_iceberg,
    "get_nearest_iceberg": get_nearest_iceberg,
    "get_iceberg_trajectory": get_iceberg_trajectory,
    "get_navigation_state": get_navigation_state,
    "get_current_route": get_current_route,
    "get_available_routes": get_available_routes,
    "get_route_risk": get_route_risk,
    "get_vessel_state": get_vessel_state,
    "get_active_alerts": get_active_alerts,
    "get_system_status": get_system_status,
    "get_dataset_status": get_dataset_status,
}


def run_tool(name: str, **kwargs) -> dict:
    """Invoke a tool by name; missing kwargs use the tool's defaults."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"name": name, "status": "error", "note": f"unknown tool: {name}"}
    return fn(**kwargs)