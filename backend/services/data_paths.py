"""Resolved paths to datasets.

Constants here are the single point where the loaders learn where the *real*
datasets live.  They are read in this order of preference:

1. ``Real data/processed/<dataset>/csv/`` — your real, preprocessed dataset
   (the loader always looks here first and, when present, uses only real data).
2. ``Real data/raw/<dataset>/``        — the raw original (only if the processed
   copy is missing).
3. ``backend/datasets/processed/``     — demo / synthetic fallback, used so the
   dashboard keeps working while the ``Real data`` folders are still empty.

When a dataset is missing entirely and ``DATA_MODE=real``, the resolved path
points at a nonexistent sentinel so the loader can report *Data Unavailable*.
Otherwise the resolved path still points at a valid demo file and a warning is
logged by the loader — nothing crashes.
"""
from __future__ import annotations

import warnings
from pathlib import Path

from config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BACKEND_DIR / "datasets" / "processed"

_REAL_ROOT = BACKEND_DIR.parents[0] / "Real data"

_RAW = _REAL_ROOT / "raw"
_PROC = _REAL_ROOT / "processed"
_CSV = {ds: _PROC / ds / "csv" for ds in
        ("sea_ice", "iceberg", "ocean", "weather", "vessel", "bathymetry")}

_DEMO_SEA_ICE = PROCESSED_DIR / "sea_ice.nc"
_DEMO_OCEAN = PROCESSED_DIR / "ocean_surface.nc"
_DEMO_WEATHER = PROCESSED_DIR / "weather_surface.nc"
_DEMO_ICEBERG_CSV = PROCESSED_DIR / "icebergs_demo.csv"


def _first_csv(folder: Path) -> Path | None:
    """Return the first (sorted) CSV in a processed dataset csv folder, if any."""
    if not folder.is_dir():
        return None
    files = sorted(p for p in folder.glob("*.csv") if p.is_file())
    return files[0] if files else None


def _resolve(real_candidates: list[Path], demo: Path, label: str) -> Path:
    for path in real_candidates:
        if path.is_file():
            return path
    if settings.data_mode_real:
        # Real mode: missing dataset is surfaced as Data Unavailable by the
        # loader. Point at a nonexistent sentinel to trigger that path.
        warnings.warn(
            f"Real dataset '{label}' not found under Real data/processed CSV "
            f"folders ({label}) while DATA_MODE=real. Marking dataset "
            "unavailable — the API will return 'Data Unavailable' rather than "
            "demo data.",
            UserWarning,
            stacklevel=3,
        )
        return _PROC / label / "csv" / "__missing__"
    if _REAL_ROOT.exists() and (
        (_RAW.is_dir() and any(_RAW.iterdir()))
        or (_PROC.is_dir() and any(_PROC.iterdir()))
    ):
        # Real folders exist but this dataset is not in them yet.
        warnings.warn(
            f"Real dataset '{label}' not found under Real data/raw|processed "
            f"({label}); falling back to demo data. Place files in "
            f"'Real data/raw/{label}/' or 'Real data/processed/{label}/csv/'.",
            UserWarning,
            stacklevel=3,
        )
    return demo


def _has_real_data() -> bool:
    return _REAL_ROOT.exists() and (
        (_RAW.is_dir() and any(_RAW.iterdir()))
        or (_PROC.is_dir() and any(_PROC.iterdir()))
    )


# Primary platform datasets. Each resolves to a real CSV when one exists.
_REAL_SEA_ICE_CSV = _first_csv(_CSV["sea_ice"])
_REAL_OCEAN_CSV = _first_csv(_CSV["ocean"])
_REAL_WEATHER_CSV = _first_csv(_CSV["weather"])
_REAL_ICEBERG_CSV = _first_csv(_CSV["iceberg"])

SEA_ICE_NETCDF = _resolve(
    [_REAL_SEA_ICE_CSV] if _REAL_SEA_ICE_CSV else [_PROC / "sea_ice" / "csv"],
    _DEMO_SEA_ICE,
    "sea_ice",
)
OCEAN_NETCDF = _resolve(
    [_REAL_OCEAN_CSV] if _REAL_OCEAN_CSV else [_PROC / "ocean" / "csv"],
    _DEMO_OCEAN,
    "ocean",
)
WEATHER_NETCDF = _resolve(
    [_REAL_WEATHER_CSV] if _REAL_WEATHER_CSV else [_PROC / "weather" / "csv"],
    _DEMO_WEATHER,
    "weather",
)

_DEMO_ICEBERG_CSV = PROCESSED_DIR / "icebergs_demo.csv"
ICEBERG_CSV = _REAL_ICEBERG_CSV if (_REAL_ICEBERG_CSV := _first_csv(_CSV["iceberg"])) else (
    _resolve([_PROC / "iceberg" / "csv"], _DEMO_ICEBERG_CSV, "iceberg")
)

have_real_datasets: bool = _has_real_data() and (
    _first_csv(_CSV["sea_ice"]) is not None or _first_csv(_CSV["iceberg"]) is not None
)
