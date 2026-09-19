"""Health check endpoint."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from config import settings
from database.database import SessionLocal
from schemas.models import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


def _db_check() -> str:
    try:
        with SessionLocal() as db:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "unavailable"


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    """GET /api/health"""
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        demo_mode=settings.demo_forced,
        database=_db_check(),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    )