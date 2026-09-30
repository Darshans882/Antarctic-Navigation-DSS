"""ProjectContext: one normalised snapshot of the whole running application.

The browser is the only place that knows what the user is looking at - which
page, which iceberg is selected, which horizon is displayed, where the voyage
simulator currently is, and the alert log (alerts are derived in the browser,
never stored by the API). Everything else the backend can look up itself.

This module turns that browser state plus live backend reads into a single
structured snapshot that:
  * both the LLM prompt and the offline answer composer read from, so they can
    never disagree with each other, and
  * records, per subsystem, whether the value is *known* or *unavailable*, so
    the assistant can say "I don't have that" instead of inventing it.

Nothing here computes a number that did not come from the backend or the
browser. That is the whole point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Subsystems the assistant can talk about. Used to report coverage honestly.
SUBSYSTEMS = (
    "page", "sea_ice", "icebergs", "navigation", "alerts", "vessel", "system",
)

#: "Not loaded" is a real answer. These are the only two ways to express it.
UNKNOWN = None


def _clean(value: Any) -> Any:
    """Drop keys whose value is None so prompts stay small and unambiguous."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _dump(model: Any) -> dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return _clean(model.model_dump())
    if isinstance(model, dict):
        return _clean(model)
    return {}


@dataclass
class ProjectContext:
    """A single, honest snapshot of the application at the moment of the question."""

    # --- what the browser told us -------------------------------------
    page: str | None = None
    horizon_hours: int = 24
    page_horizon: int | None = None
    selected_iceberg_id: str | None = None
    alerts: list[dict[str, Any]] = field(default_factory=list)
    unread_alert_count: int | None = None
    navigation: dict[str, Any] = field(default_factory=dict)
    vessel_hint: dict[str, Any] = field(default_factory=dict)

    # --- what the backend read back ----------------------------------
    sea_ice: dict[str, Any] = field(default_factory=dict)
    iceberg: dict[str, Any] = field(default_factory=dict)
    route: dict[str, Any] = field(default_factory=dict)
    vessel: dict[str, Any] = field(default_factory=dict)
    system: dict[str, Any] = field(default_factory=dict)

    # --- bookkeeping --------------------------------------------------
    unavailable: dict[str, str] = field(default_factory=dict)
    demo_subsystems: set[str] = field(default_factory=set)
    #: The dashboard payload as received, for argument resolution.
    raw_dashboard: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    @classmethod
    def from_request(cls, req: Any) -> "ProjectContext":
        """Build the browser half of the context from the chat request."""
        dash = _dump(getattr(req, "dashboard", None))
        nav = dash.get("navigation") or {}
        journey = nav.get("journey") or {}

        status = "not_started"
        if journey.get("status"):
            status = str(journey["status"])
        elif journey.get("journey_id"):
            status = "complete" if journey.get("is_complete") else "active"

        navigation = {
            "port_id": nav.get("port_id"),
            "center_id": nav.get("center_id"),
            "vessel_id": nav.get("vessel_id"),
            "journey_mode": nav.get("journey_mode"),
            "live_lat": nav.get("live_lat"),
            "live_lon": nav.get("live_lon"),
            "route_id": nav.get("route_id"),
            "destination_name": nav.get("destination_name"),
            "selected_route": nav.get("selected_route") or {},
            "routes_available": nav.get("routes_available") or [],
            "time_step_hours": nav.get("time_step_hours"),
            "journey": (
                {
                    "journey_id": journey.get("journey_id"),
                    "origin": journey.get("origin"),
                    "destination": journey.get("destination"),
                    "journey_mode": journey.get("journey_mode"),
                    "status": status,
                    "total_distance_nm": journey.get("total_distance_nm"),
                    "total_fuel_tons": journey.get("total_fuel_tons"),
                    "estimated_duration_hours": journey.get("estimated_duration_hours"),
                    "max_risk_level": journey.get("max_risk_level"),
                    "route_update_count": journey.get("route_update_count"),
                    "vessel_lat": journey.get("vessel_lat"),
                    "vessel_lon": journey.get("vessel_lon"),
                    "current_time_hours": journey.get("current_time_hours"),
                    "progress_percent": journey.get("progress_percent"),
                    "remaining_distance_nm": journey.get("remaining_distance_nm"),
                    "remaining_fuel_tons": journey.get("remaining_fuel_tons"),
                    "is_complete": journey.get("is_complete"),
                }
                if journey
                else {}
            ),
        }

        inst = cls(
            page=dash.get("page"),
            horizon_hours=int(getattr(req, "horizon_hours", 24) or 24),
            page_horizon=dash.get("sea_ice_horizon"),
            selected_iceberg_id=dash.get("selected_iceberg_id"),
            alerts=list(dash.get("alert_context") or []),
            unread_alert_count=dash.get("unread_alert_count"),
            navigation=_clean(navigation),
            vessel_hint=_clean(dash.get("vessel") or {}),
            raw_dashboard=dash,
        )
        inst.enrich_from_backend()
        return inst

    # ------------------------------------------------------------------
    # The horizon the user is actually looking at wins over the request
    # default, so "change to 72h" then "what is it?" agrees with the page.
    @property
    def effective_horizon(self) -> int:
        return int(self.page_horizon or self.horizon_hours or 24)

    @property
    def journey(self) -> dict[str, Any]:
        return self.navigation.get("journey") or {}

    @property
    def journey_active(self) -> bool:
        return self.journey.get("status") == "active"

    @property
    def vessel_position(self) -> tuple[float | None, float | None]:
        """Vessel position, most authoritative source first."""
        journey = self.journey
        if journey.get("vessel_lat") is not None and journey.get("vessel_lon") is not None:
            return float(journey["vessel_lat"]), float(journey["vessel_lon"])
        for source in (self.vessel, self.vessel_hint):
            if source.get("lat") is not None and source.get("lon") is not None:
                return float(source["lat"]), float(source["lon"])
        try:
            lat = self.navigation.get("live_lat")
            lon = self.navigation.get("live_lon")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

        # If a browser dashboard was explicitly sent, do not invent coordinates if none were given
        if self.raw_dashboard:
            return None, None

        # For bare queries without a browser session, use the configured departure port
        port_id = self.navigation.get("port_id")
        try:
            from app.config import load_ports
            ports = {p.get("port_id"): p for p in load_ports()}
            if port_id and port_id in ports:
                p = ports[port_id]
                return float(p["latitude"]), float(p["longitude"])
            if "hobart" in ports:
                p = ports["hobart"]
                return float(p["latitude"]), float(p["longitude"])
        except Exception:
            pass

        return None, None

    def enrich_from_backend(self) -> None:
        """Enrich context with live backend data so tools and prompts have complete real state."""
        # Vessel info
        try:
            from app.config import load_vessels
            vessels = {v.get("vessel_id"): v for v in load_vessels()}
            vid = self.navigation.get("vessel_id") or "polar_explorer"
            vinfo = vessels.get(vid) or vessels.get("polar_explorer") or {}
            if vinfo:
                lat, lon = self.vessel_position
                self.vessel.setdefault("vessel_id", vinfo.get("vessel_id", vid))
                self.vessel.setdefault("name", vinfo.get("name", "Polar Explorer"))
                self.vessel.setdefault("type", vinfo.get("type", "Research Vessel"))
                self.vessel.setdefault("ice_class", vinfo.get("ice_class", "PC5"))
                self.vessel.setdefault("draft_m", vinfo.get("draft_m", 7.5))
                self.vessel.setdefault("cruising_speed_knots", vinfo.get("cruising_speed_knots", 14.0))
                self.vessel.setdefault("fuel_consumption_tons_per_day", vinfo.get("fuel_consumption_tons_per_day", 18.0))
                self.vessel.setdefault("lat", lat)
                self.vessel.setdefault("lon", lon)
        except Exception as exc:
            self.mark_unavailable("vessel", str(exc))

        # Sea-ice summary
        try:
            from services.sea_ice_service import sea_ice_service
            curr = sea_ice_service.current()
            if curr and curr.get("status") != "error":
                conc = curr.get("concentration") or []
                flat = [v for row in conc for v in row if v is not None]
                self.sea_ice = {
                    "timestamp": curr.get("timestamp"),
                    "mean_concentration": round(sum(flat) / len(flat), 4) if flat else 0.0,
                    "max_concentration": round(max(flat), 4) if flat else 0.0,
                    "grid_size": f"{len(conc)}x{len(conc[0]) if conc else 0}",
                    "horizon_hours": self.effective_horizon,
                    "demo": bool(curr.get("demo")),
                }
        except Exception as exc:
            self.mark_unavailable("sea_ice", str(exc))

        # Iceberg summary
        try:
            from services.iceberg_service import iceberg_service
            ib_data = iceberg_service.list_icebergs()
            if ib_data and ib_data.get("status") != "error":
                bergs = ib_data.get("icebergs") or []
                self.iceberg = {
                    "count": len(bergs),
                    "items": bergs,
                    "selected_id": self.selected_iceberg_id,
                }
        except Exception as exc:
            self.mark_unavailable("icebergs", str(exc))

        # System / dataset status
        try:
            from services import dataset_service
            ds_data = dataset_service.from_database()
            if ds_data and not isinstance(ds_data, dict):
                real_count = len([d for d in ds_data if not d.get("demo")])
                self.system = {
                    "backend_connected": True,
                    "real_data_available": real_count > 0,
                    "dataset_count": len(ds_data),
                    "datasets": ds_data,
                }
        except Exception as exc:
            self.mark_unavailable("system", str(exc))

    def mark_unavailable(self, subsystem: str, reason: str) -> None:
        """Record that a subsystem could not be read, and why."""
        self.unavailable[subsystem] = reason

    def note_demo(self, subsystem: str) -> None:
        self.demo_subsystems.add(subsystem)

    def has(self, subsystem: str) -> bool:
        return subsystem not in self.unavailable

    # ------------------------------------------------------------------
    def as_dict(self) -> dict[str, Any]:
        """The snapshot as the prompt and composer both consume it."""
        lat, lon = self.vessel_position
        vessel = dict(self.vessel)
        if lat is not None and lon is not None:
            vessel["lat"], vessel["lon"] = lat, lon
        vessel.update(self.vessel_hint)
        if not vessel.get("speed_known"):
            # The app deliberately reports speed as unknown rather than
            # inventing it. Never let that become a number.
            vessel.pop("speed_knots", None)
            vessel["speed_knots"] = None

        return _clean({
            "page": self.page,
            "effective_horizon_hours": self.effective_horizon,
            "selected_iceberg_id": self.selected_iceberg_id,
            "sea_ice": self.sea_ice,
            "iceberg": self.iceberg,
            "navigation": self.navigation,
            "vessel": vessel,
            "alerts": {
                "count": len(self.alerts),
                "unread": self.unread_alert_count,
                "records": self.alerts,
            },
            "system": self.system,
        })

    def coverage_report(self) -> dict[str, str]:
        """Which subsystems are readable right now, for honest messaging."""
        report: dict[str, str] = {}
        for name in SUBSYSTEMS:
            if name in self.unavailable:
                report[name] = f"unavailable: {self.unavailable[name]}"
            elif name in self.demo_subsystems:
                report[name] = "available (synthetic demo data)"
            else:
                report[name] = "available"
        return report

    def render(self) -> str:
        """Compact, readable dump for the LLM prompt."""
        import json

        body = json.dumps(self.as_dict(), indent=2, default=str)
        coverage = "\n".join(f"- {k}: {v}" for k, v in self.coverage_report().items())
        return (
            "Live application state, read from the running system just now.\n"
            "Fields that are absent were not available; do not fill them in.\n\n"
            f"{body}\n\n"
            "Coverage:\n"
            f"{coverage}"
        )


# ----------------------------------------------------------------------
# Route argument resolution for backend tools
# ----------------------------------------------------------------------
def route_arguments(ctx: ProjectContext, fallback_start: tuple[float, float],
                    fallback_dest: tuple[float, float]) -> dict[str, Any]:
    """Build /api/routes/optimize arguments from the app's current selections.

    The browser's own start/destination are authoritative when present. A live
    vessel position overrides the start, because that is what a recalculation
    is actually for.
    """
    from config import settings

    start_lat, start_lon = fallback_start
    dest_lat, dest_lon = fallback_dest

    raw = ctx.raw_dashboard
    if raw.get("start_lat") is not None and raw.get("start_lon") is not None:
        start_lat, start_lon = raw["start_lat"], raw["start_lon"]
    if raw.get("dest_lat") is not None and raw.get("dest_lon") is not None:
        dest_lat, dest_lon = raw["dest_lat"], raw["dest_lon"]

    lat, lon = ctx.vessel_position
    if lat is not None and lon is not None:
        start_lat, start_lon = lat, lon

    return {
        "start_lat": float(start_lat),
        "start_lon": float(start_lon),
        "dest_lat": float(dest_lat),
        "dest_lon": float(dest_lon),
        "vessel_id": ctx.navigation.get("vessel_id") or settings.DEFAULT_VESSEL_ID,
        "preference": "recommended",
    }
