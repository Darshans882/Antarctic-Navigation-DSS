"""Advanced sea-ice intelligence endpoints.

Thin HTTP wrappers over ``services.sea_ice_intelligence_service``. The math
lives in the service so the AI assistant returns exactly the same numbers the
dashboard renders - there is one implementation, not two.

No values are fabricated; unavailable data is clearly indicated.

Routes are mounted under the /api/sea-ice prefix alongside the existing
sea_ice router (see main.py).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services import sea_ice_intelligence_service as intel

router = APIRouter(prefix="/sea-ice", tags=["sea-ice-intelligence"])


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/classification
# ---------------------------------------------------------------------------
@router.get("/intelligence/classification")
async def sea_ice_classification() -> dict[str, Any]:
    """Sea-ice type classification derived from concentration field."""
    return intel.ice_classification()


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/thickness
# ---------------------------------------------------------------------------
@router.get("/intelligence/thickness")
async def sea_ice_thickness() -> dict[str, Any]:
    """Estimated sea-ice thickness derived from concentration."""
    return intel.ice_thickness()


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/keel-depth
# ---------------------------------------------------------------------------
@router.get("/intelligence/keel-depth")
async def keel_depth() -> dict[str, Any]:
    """Sub-ice topography / keel depth analytical estimate."""
    return intel.keel_depth()


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/melt-pond
# ---------------------------------------------------------------------------
@router.get("/intelligence/melt-pond")
async def melt_pond() -> dict[str, Any]:
    """Real-time melt-pond detection status."""
    return intel.melt_pond()


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/change
# ---------------------------------------------------------------------------
@router.get("/intelligence/change")
async def sea_ice_change(
    horizon_hours: int = Query(24, ge=2, le=168),
) -> dict[str, Any]:
    """Sea-ice change detection: current vs. forecast."""
    return intel.ice_change(horizon_hours)


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/melt-zones
# ---------------------------------------------------------------------------
@router.get("/intelligence/melt-zones")
async def projected_melt_zones(
    horizon_hours: int = Query(24, ge=2, le=240),
) -> dict[str, Any]:
    """Projected melt zones from forecast concentration decrease."""
    return intel.melt_zones(min(horizon_hours, 168)) | {"horizon_hours": horizon_hours}


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/risk
# ---------------------------------------------------------------------------
@router.get("/intelligence/risk")
async def sea_ice_risk(
    horizon_hours: int = Query(24, ge=2, le=168),
) -> dict[str, Any]:
    """Sea-ice risk assessment from concentration and forecast data."""
    return intel.ice_risk(horizon_hours)


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/climate-trend
# ---------------------------------------------------------------------------
@router.get("/intelligence/climate-trend")
async def climate_trend() -> dict[str, Any]:
    """Historical sea-ice trend from stored forecast records."""
    return intel.climate_trend()


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/model-convergence
# ---------------------------------------------------------------------------
@router.get("/intelligence/model-convergence")
async def model_convergence() -> dict[str, Any]:
    """ML model convergence metrics from saved evaluation results or database."""
    return intel.model_convergence()


# ---------------------------------------------------------------------------
# /api/sea-ice/intelligence/spectral
# ---------------------------------------------------------------------------
@router.get("/intelligence/spectral")
async def spectral_analysis() -> dict[str, Any]:
    """Spectral sea-ice analysis placeholder."""
    return intel.spectral_analysis()
