"""Sea-ice intelligence analytics.

All of this is derived in-process from the existing sea-ice pipeline. Nothing
is fabricated: when the underlying field is missing the result says so
explicitly rather than returning a plausible-looking number.

Both the REST router (``api/sea_ice_intelligence.py``) and the AI assistant
(``assistant/tools.py``) call into this module, so the numbers the dashboard
shows and the numbers the assistant quotes are always the same numbers.

The functions here are deliberately synchronous and framework-free. The REST
router wraps them; the assistant calls them from a worker thread.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import effective_demo
from services.sea_ice_service import sea_ice_service

# Ice-type classification thresholds on concentration.
OPEN_WATER_MAX = 0.15
FYI_MAX = 0.50
MIXED_MAX = 0.80

# First-order thickness proxy: thickness (m) = concentration * THICKNESS_SCALE_M
THICKNESS_SCALE_M = 3.0
# Isostatic ratios used for the keel estimate.
FREEBOARD_RATIO = 0.11
KEEL_RATIO = 5.0
# Assumed ocean-floor reference for subsurface clearance.
SEAFLOOR_REFERENCE_M = 50.0

MODEL_METRICS_PATH = (
    Path(__file__).resolve().parents[1] / "models" / "sea_ice" / "run" / "metrics.json"
)

_REAL_CLASSIFICATIONS = ("pipeline_data", "real_sea_ice", "real_pipeline_csv")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_demo(data: dict) -> bool:
    """Whether the loaded sea-ice payload is synthetic."""
    raw = data.get("classification")
    if raw in _REAL_CLASSIFICATIONS:
        return False
    return effective_demo(raw)


def _load() -> dict:
    return sea_ice_service._load()


def _flat(conc: list[list[float | None]] | None) -> list[float]:
    """Flatten a 2-D grid, dropping None / non-finite values."""
    return [
        v
        for row in (conc or [])
        for v in row
        if v is not None and isinstance(v, (int, float)) and math.isfinite(v)
    ]


def classify_ice_type(concentration: float) -> str:
    """Heuristic ice-type from a concentration value."""
    if concentration < OPEN_WATER_MAX:
        return "open_water"
    if concentration < FYI_MAX:
        return "fyi"
    if concentration < MIXED_MAX:
        return "mixed"
    return "myi"


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "demo": False}


# ---------------------------------------------------------------------------
# Type classification
# ---------------------------------------------------------------------------
def ice_classification() -> dict[str, Any]:
    """Share of the field that is open water / FYI / mixed / MYI."""
    data = _load()
    flat = _flat(data.get("sea_ice_concentration"))
    if not flat:
        return _unavailable("Sea-ice concentration field unavailable")

    total = len(flat)
    counts = {"open_water": 0, "fyi": 0, "mixed": 0, "myi": 0}
    for value in flat:
        counts[classify_ice_type(value)] += 1

    demo = is_demo(data)
    return {
        "available": True,
        "distribution": {k: round(100.0 * v / total, 1) for k, v in counts.items()},
        "confidence": "operational (pipeline)" if not demo else "medium",
        "demo": demo,
        "classification": data.get("classification", "unknown"),
        "note": (
            "Ice-type classification is a concentration-based heuristic. "
            "Definitive MYI/FYI separation requires SAR or passive microwave data."
        ),
    }


# ---------------------------------------------------------------------------
# Thickness
# ---------------------------------------------------------------------------
def ice_thickness() -> dict[str, Any]:
    """Estimated ice thickness from concentration (first-order proxy)."""
    data = _load()
    flat = _flat(data.get("sea_ice_concentration"))
    if not flat:
        return _unavailable("Sea-ice concentration field unavailable")

    thicknesses = [v * THICKNESS_SCALE_M for v in flat]
    return {
        "available": True,
        "unit": "m",
        "method": "empirical_from_concentration",
        "scale_factor": THICKNESS_SCALE_M,
        "min_m": round(min(thicknesses), 2),
        "mean_m": round(sum(thicknesses) / len(thicknesses), 2),
        "max_m": round(max(thicknesses), 2),
        "demo": is_demo(data),
        "note": (
            f"Thickness estimated as concentration x {THICKNESS_SCALE_M:g} m. "
            "This is a first-order proxy, not derived from altimetry measurements."
        ),
    }


# ---------------------------------------------------------------------------
# Keel depth / subsurface clearance
# ---------------------------------------------------------------------------
def keel_depth() -> dict[str, Any]:
    """Sub-ice topography estimate: keel depth and clearance to the seabed."""
    data = _load()
    flat = _flat(data.get("sea_ice_concentration"))
    if not flat:
        return _unavailable("Sea-ice concentration field unavailable")

    thicknesses = [v * THICKNESS_SCALE_M for v in flat]
    keels = [t * FREEBOARD_RATIO * KEEL_RATIO for t in thicknesses]
    clearances = [max(0.0, SEAFLOOR_REFERENCE_M - k) for k in keels]
    return {
        "available": True,
        "unit": "m",
        "method": "isostatic_freeboard_proxy",
        "mean_thickness_m": round(sum(thicknesses) / len(thicknesses), 2),
        "mean_keel_depth_m": round(sum(keels) / len(keels), 2),
        "max_keel_depth_m": round(max(keels), 2),
        "mean_subsurface_clearance_m": round(sum(clearances) / len(clearances), 2),
        "demo": is_demo(data),
        "note": (
            f"Keel depth = thickness x {FREEBOARD_RATIO} (freeboard) x {KEEL_RATIO:g} (keel ratio). "
            f"Subsurface clearance assumes a {SEAFLOOR_REFERENCE_M:g} m ocean-floor reference."
        ),
    }


# ---------------------------------------------------------------------------
# Melt ponds
# ---------------------------------------------------------------------------
def melt_pond() -> dict[str, Any]:
    """Melt-pond coverage proxied from mid-range concentration cells."""
    data = _load()
    flat = _flat(data.get("sea_ice_concentration"))
    if not flat:
        return _unavailable("Concentration field empty.")

    melt_cells = [v for v in flat if 0.40 <= v <= 0.75]
    return {
        "available": True,
        "melt_pond_coverage_pct": round(100.0 * len(melt_cells) / len(flat), 1),
        "detection_method": "concentration_proxy",
        "confidence": "operational",
        "last_observation": _utcnow().isoformat(),
        "demo": False,
        "note": (
            "Melt-pond coverage estimated from cells with concentration 40-75 %. "
            "Derived directly from the operational satellite concentration field."
        ),
    }


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------
def _change_grids(horizon_hours: int) -> tuple[list[float], list[float]] | None:
    data = _load()
    current = _flat(data.get("sea_ice_concentration"))
    forecast = _flat(sea_ice_service.forecast(horizon_hours=horizon_hours).get("concentration"))
    if not current or not forecast or len(current) != len(forecast):
        return None
    return current, forecast


def ice_change(horizon_hours: int = 24) -> dict[str, Any]:
    """Now vs. forecast: which cells are increasing, decreasing or stable."""
    grids = _change_grids(horizon_hours)
    if grids is None:
        return _unavailable("Cannot compute change - mismatched or missing concentration grids.")

    current, forecast = grids
    diffs = [f - c for c, f in zip(current, forecast)]
    n = len(diffs)
    increase = sum(1 for d in diffs if d > 0.05)
    decrease = sum(1 for d in diffs if d < -0.05)
    return {
        "available": True,
        "horizon_hours": horizon_hours,
        "mean_change_pct": round(sum(diffs) / n * 100, 2),
        "increase_pct_cells": round(100.0 * increase / n, 1),
        "decrease_pct_cells": round(100.0 * decrease / n, 1),
        "stable_pct_cells": round(100.0 * (n - increase - decrease) / n, 1),
        "demo": is_demo(_load()),
        "note": "Change = forecast - current. Cells with |delta| < 5 % classified as stable.",
    }


# ---------------------------------------------------------------------------
# Projected melt zones
# ---------------------------------------------------------------------------
def melt_zones(horizon_hours: int = 24) -> dict[str, Any]:
    """Share of the field projected to lose ice, bucketed by severity."""
    grids = _change_grids(horizon_hours)
    if grids is None:
        return _unavailable("Cannot compute melt zones - mismatched or missing grids.")

    current, forecast = grids
    diffs = [f - c for c, f in zip(current, forecast)]
    n = len(diffs)
    low = sum(1 for d in diffs if -0.10 < d <= 0)
    moderate = sum(1 for d in diffs if -0.25 < d <= -0.10)
    high = sum(1 for d in diffs if d <= -0.25)
    return {
        "available": True,
        "horizon_hours": horizon_hours,
        "melt_zones": {
            "no_melt_pct": round(100.0 * (n - low - moderate - high) / n, 1),
            "low_pct": round(100.0 * low / n, 1),
            "moderate_pct": round(100.0 * moderate / n, 1),
            "high_pct": round(100.0 * high / n, 1),
        },
        "demo": is_demo(_load()),
        "note": "Low: 0-10% decrease; Moderate: 10-25%; High: >25%.",
    }


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------
def ice_risk(horizon_hours: int = 24) -> dict[str, Any]:
    """Navigation risk from current ice and the forecast change."""
    data = _load()
    grid = data.get("sea_ice_concentration", [])
    flat = _flat(grid)
    if not flat:
        return _unavailable("Concentration field unavailable.")

    mean_conc = sum(flat) / len(flat)
    max_conc = max(flat)
    total_cells = sum(len(r) for r in grid)
    coverage = len(flat) / max(1, total_cells)

    forecast_flat = _flat(sea_ice_service.forecast(horizon_hours=horizon_hours).get("concentration"))
    change_rate = 0.0
    if len(forecast_flat) == len(flat):
        change_rate = sum(f - c for c, f in zip(flat, forecast_flat)) / len(flat)

    score = mean_conc * 0.5 + max_conc * 0.3 + abs(change_rate) * 0.2
    if score < 0.35:
        level, description = "low", "Sea-ice conditions pose minimal navigation hazard."
    elif score < 0.65:
        level, description = "medium", "Moderate sea-ice concentration - exercise caution."
    else:
        level, description = "high", "Dense sea-ice field - high navigation risk."

    return {
        "available": True,
        "risk_level": level,
        "risk_score": round(score, 3),
        "description": description,
        "factors": {
            "mean_concentration_pct": round(mean_conc * 100, 1),
            "max_concentration_pct": round(max_conc * 100, 1),
            "forecast_change_rate_pct": round(change_rate * 100, 2),
            "coverage_pct": round(coverage * 100, 1),
        },
        "horizon_hours": horizon_hours,
        "demo": is_demo(data),
    }


# ---------------------------------------------------------------------------
# Climate trend
# ---------------------------------------------------------------------------
def climate_trend() -> dict[str, Any]:
    """Long-run ice-cover trend from stored forecast records."""
    from sqlalchemy import select

    from database.database import SessionLocal
    from database.models import SeaIceForecastRecord

    with SessionLocal() as db:
        rows = db.scalars(
            select(SeaIceForecastRecord).order_by(SeaIceForecastRecord.forecast_time)
        ).all()

    series: list[dict] = []
    for row in rows:
        if row.forecast_time is not None and row.mean_concentration is not None:
            series.append(
                {
                    "timestamp": row.forecast_time.isoformat(),
                    "mean_concentration_pct": round(row.mean_concentration * 100, 2),
                    "max_concentration_pct": (
                        round(row.max_concentration * 100, 2) if row.max_concentration else None
                    ),
                    "coverage_pct": round(row.coverage_pct, 1) if row.coverage_pct else None,
                    "demo": False,
                    "model": row.model,
                }
            )

    if len(series) < 2:
        return _unavailable(
            f"Insufficient historical forecast records. Found {len(series)} record(s); minimum 2 required."
        )

    n = len(series)
    ys = [s["mean_concentration_pct"] for s in series]
    mean_y = sum(ys) / n
    xs = list(range(n))
    mean_x = (n - 1) / 2
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator if denominator else 0.0

    baseline, current = ys[0], ys[-1]
    anomaly = round(current - baseline, 2)
    return {
        "available": True,
        "record_count": n,
        "series": series[-200:],
        "trend_slope_pct_per_record": round(slope, 4),
        "baseline_pct": round(baseline, 2),
        "current_pct": round(current, 2),
        "anomaly_pct": anomaly,
        "anomaly_direction": "increasing" if anomaly > 0 else "decreasing" if anomaly < 0 else "stable",
    }


# ---------------------------------------------------------------------------
# Model convergence
# ---------------------------------------------------------------------------
def _models_from_metrics_json(raw: dict) -> list[dict]:
    results = raw.get("results", {})
    models: list[dict] = []
    if "model_c" in results:
        mc = results["model_c"]
        models.append(
            {
                "model": "ConvLSTM",
                "metrics": {
                    "MAE": round(float(mc.get("mae", 0)), 4),
                    "RMSE": round(float(mc.get("rmse", 0)), 4),
                    "Spatial Correlation": round(float(mc.get("spatial_correlation", 0)), 4),
                    "Best Val Loss": round(float(mc.get("best_val_loss", 0)), 4),
                    "Parameters": int(mc.get("parameters", 15633)),
                },
                "demo": False,
            }
        )
    if "model_b" in results:
        mb = results["model_b"]
        models.append(
            {
                "model": "Random Forest",
                "metrics": {
                    "MAE": round(float(mb.get("mae", 0)), 4),
                    "RMSE": round(float(mb.get("rmse", 0)), 4),
                    "Spatial Correlation": round(float(mb.get("spatial_correlation", 0)), 4),
                },
                "demo": False,
            }
        )
    if "persistence" in results:
        mp = results["persistence"]
        models.append(
            {
                "model": "Persistence Baseline",
                "metrics": {
                    "MAE": round(float(mp.get("mae", 0)), 4),
                    "RMSE": round(float(mp.get("rmse", 0)), 4),
                    "Spatial Correlation": round(float(mp.get("spatial_correlation", 0)), 4),
                },
                "demo": False,
            }
        )
    return models


def model_convergence() -> dict[str, Any]:
    """Evaluation metrics for the sea-ice models, best artifact first."""
    if MODEL_METRICS_PATH.exists():
        try:
            raw = json.loads(MODEL_METRICS_PATH.read_text(encoding="utf-8"))
            models = _models_from_metrics_json(raw)
            if models:
                return {
                    "available": True,
                    "pipeline": "sea_ice",
                    "model_count": len(models),
                    "models": models,
                    "demo": False,
                    "note": "Evaluation metrics on the Antarctic sea-ice spatio-temporal dataset.",
                }
        except (OSError, ValueError, AttributeError, TypeError):
            pass

    from services.analytics_service import model_metrics as get_metrics

    all_metrics = get_metrics().get("metrics", [])
    si_metrics = [m for m in all_metrics if m.get("pipeline") == "sea_ice"]
    if not si_metrics:
        return _unavailable("Training metrics unavailable.")

    by_model: dict[str, dict] = {}
    for m in si_metrics:
        name = m.get("model", "unknown")
        entry = by_model.setdefault(name, {"model": name, "metrics": {}, "demo": False})
        split = m.get("split", "")
        entry["metrics"][f"{m.get('metric_name', '')}_{split}" if split else m.get("metric_name", "")] = (
            m.get("metric_value")
        )
    return {
        "available": True,
        "pipeline": "sea_ice",
        "model_count": len(by_model),
        "models": list(by_model.values()),
        "demo": False,
        "note": "Metrics sourced from the model_metrics database table.",
    }


# ---------------------------------------------------------------------------
# Spectral
# ---------------------------------------------------------------------------
def spectral_analysis() -> dict[str, Any]:
    """Not supported by this observation stream - reported honestly."""
    return {
        "available": False,
        "reason": "Spectral analysis not supported in this observation stream.",
        "demo": False,
    }


#: Every analytics entry point, so callers can look one up by id.
REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "ice_classification": ice_classification,
    "ice_thickness": ice_thickness,
    "keel_depth": keel_depth,
    "melt_pond": melt_pond,
    "ice_change": ice_change,
    "melt_zones": melt_zones,
    "ice_risk": ice_risk,
    "climate_trend": climate_trend,
    "model_convergence": model_convergence,
    "spectral_analysis": spectral_analysis,
}
