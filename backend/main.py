"""Antarctic Navigation DSS — FastAPI REST API.

Run from ``backend/``:
    uvicorn main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
OpenAPI spec:    http://localhost:8000/openapi.json

All routes are mounted under the ``/api`` prefix:
    /api/health
    /api/datasets            (+ /status)
    /api/sea-ice/current     (+ /forecast, /predict)
    /api/icebergs            (+ /{id}, /predict, /trajectory, /distance)
    /api/routes/optimize     (+ /{route_id})
    /api/analytics/summary   (+ /model-metrics)

Secrets (API keys etc.) live in environment variables and are never exposed
in responses. Demo data is always clearly labeled in the ``warning`` /
``demo`` fields.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database.database import init_db

from api import analytics, assistant, datasets, health, icebergs, models, routes, sea_ice, sea_ice_intelligence, vessels
from app.routes import config_routes, navigation_routes, vessel_routes

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("dss.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s v%s (real_data_mode=%s)", settings.APP_NAME, settings.APP_VERSION, settings.data_mode_real)
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - startup should remain resilient
        logger.exception("Startup DB init failed: %s", exc)

    try:
        from services.sea_ice_service import sea_ice_service
        from services.navigation_service import navigation_service
        from navigation.grid import AntarcticGrid
        from navigation.land_mask import load_land_mask
        sea_ice_service.current()
        load_land_mask(AntarcticGrid.from_config({}), settings.LAND_MASK_FILE)
        navigation_service.optimize(
            start_lat=-54.8,
            start_lon=-68.3,
            dest_lat=-62.2,
            dest_lon=-58.9,
            vessel_id="polar_explorer",
            preference="balanced",
        )
        logger.info("Pre-warmed sea-ice, land-mask, and route engine successfully")
    except Exception as exc:  # pragma: no cover
        logger.warning("Data pre-warming notice: %s", exc)

    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Navigation Decision Support System for Antarctic vessels. "
        "Connects ML models, sea-ice/iceberg data, and route optimisation "
        "behind one REST API. The system operates in real-data mode; missing "
        "resources are reported as unavailable instead of substituted."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

is_wildcard_origin = settings.cors_origins_list == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=None if is_wildcard_origin else r"https://.*\.vercel\.app",
    allow_credentials=not is_wildcard_origin,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint for cloud ping and load-balancer probes."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_health": "/api/health",
    }


@app.get("/health", tags=["root"])
async def root_health() -> dict[str, str]:
    """Root health probe for AWS Target Groups, ECS, ALBs, and proxies."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ---------------------------------------------------------------------------
# Route registration — order matters only inside /icebergs (static paths are
# declared before the /{iceberg_id} parameter route).
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api")
app.include_router(health.system_router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(sea_ice.router, prefix="/api")
app.include_router(sea_ice_intelligence.router, prefix="/api")
app.include_router(icebergs.router, prefix="/api")
app.include_router(routes.router, prefix="/api")
app.include_router(vessels.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(models.router, prefix="/api")


# ---------------------------------------------------------------------------
# Legacy /api/v1 surface (ports/centers/vessels + journey lifecycle) mounted
# here so the frontend can drive real, live journeys through the same backend
# and Vite proxy. Pure additions — app.main:app on :8001 remains unchanged.
# ---------------------------------------------------------------------------
app.include_router(config_routes.router, prefix="/api/v1")
app.include_router(vessel_routes.router, prefix="/api/v1")
app.include_router(navigation_routes.router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: never leak internals or secrets to clients."""
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
