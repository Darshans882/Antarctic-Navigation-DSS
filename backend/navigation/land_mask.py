"""Land-mask loading for the Antarctic routing grid.

The navigation engine needs to know which cells are land (Antarctica and
islands) so routes cannot cross the continent. This module loads a coastline /
bathymetry layer from disk and maps it onto a :class:`AntarcticGrid`.

Supported formats (configurable via ``LAND_MASK_FILE``):

* NetCDF with an ``elevation`` variable (GEBCO-style: land where
  ``elevation >= 0``) or a ``depth`` variable (land where ``depth < 0``),
* a raw ``.npy`` boolean array already aligned to the grid,
* ``.tif``/GeoTIFF rasters via rasterio when installed (elevation >= 0 = land), and
* ``.json`` produced by the real-data pipeline: parallel ``latitude``/``longitude``
  coordinate-pair arrays marking every ocean cell (everything else is land).

If no file is configured or the file cannot be read, :func:`load_land_mask`
returns ``(None, info)`` — the caller must then keep the whole region as open
water and surface this as an explicit limitation (never silently).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from navigation.grid import AntarcticGrid


def _land_from_elevation(lat, lon, elevation) -> np.ndarray:
    flat_lat = np.sort(np.unique(np.asarray(lat, dtype=float)))
    flat_lon = np.sort(np.unique(np.asarray(lon, dtype=float)))
    elev = np.asarray(elevation, dtype=float)
    if elev.ndim == 1 and len(elev) == len(flat_lat) * len(flat_lon):
        elev = elev.reshape(len(flat_lat), len(flat_lon))
    if elev.shape != (len(flat_lat), len(flat_lon)):
        lat2d, lon2d = np.meshgrid(flat_lat, flat_lon, indexing="ij")
        from scipy.interpolate import griddata

        points = np.column_stack([np.asarray(lat).ravel(), np.asarray(lon).ravel()])
        elev = griddata(points, elev.ravel(), (lat2d.ravel(), lon2d.ravel()),
                        method="nearest").reshape(lat2d.shape)
    return np.where(np.isfinite(elev), elev >= 0, False)


_LOADED_MASKS: dict[tuple[int, int, str], tuple[np.ndarray, dict[str, Any]]] = {}


def load_land_mask(grid: AntarcticGrid, path: str | None) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Load and regrid a land mask onto ``grid``.

    Returns ``(mask, info)``; ``mask`` is ``None`` when no usable land layer is
    available. ``info`` always describes exactly what was (or was not) loaded.
    """
    if not path:
        return None, {
            "loaded": False,
            "file": None,
            "reason": "LAND_MASK_FILE is not set; the grid is treated as open water.",
        }

    cache_key = (grid.nlat, grid.nlon, str(path))
    if cache_key in _LOADED_MASKS:
        return _LOADED_MASKS[cache_key]

    full = Path(path)

    # Fast path: check for pre-aligned .npy file (either next to json or in bundled config)
    cfg_dir = Path(__file__).resolve().parents[1] / "app" / "data" / "config"
    npy_candidates = [
        cfg_dir / f"land_mask_nav_{grid.nlat}_{grid.nlon}.npy",
        cfg_dir / f"land_mask_def_{grid.nlat}_{grid.nlon}.npy",
        full if full.suffix.lower() == ".npy" else full.with_suffix(".npy"),
        cfg_dir / "land_ocean_mask.npy",
    ]
    for npy_path in npy_candidates:
        if npy_path.is_file():
            try:
                mask = np.load(npy_path)
                mask = np.asarray(mask, dtype=bool)
                if mask.shape == (grid.nlat, grid.nlon):
                    info = {
                        "loaded": True,
                        "file": str(npy_path),
                        "format": "npy",
                        "land_cells": int(mask.sum()),
                        "land_fraction": float(mask.mean()),
                    }
                    _LOADED_MASKS[cache_key] = (mask, info)
                    return mask, info
            except Exception:
                pass

    # Fast path 2: check for compressed .npz representation (instant resampling to any grid shape)
    npz_path = cfg_dir / "land_ocean_mask.npz"
    if npz_path.is_file():
        try:
            with np.load(npz_path) as z:
                lat_arr = z["lat_arr"]
                lon_arr = z["lon_arr"]
                land = z["land"]
            lat_idx = np.array([int(np.argmin(np.abs(lat_arr - lat))) for lat in grid.lats])
            lon_idx = np.array([int(np.argmin(np.abs(lon_arr - lon))) for lon in grid.lons])
            mask = land[np.ix_(lat_idx, lon_idx)]
            info = {
                "loaded": True,
                "file": str(npz_path),
                "format": "npz",
                "land_cells": int(mask.sum()),
                "land_fraction": float(mask.mean()),
            }
            _LOADED_MASKS[cache_key] = (mask, info)
            return mask, info
        except Exception:
            pass

    if not full.exists():
        return None, {
            "loaded": False,
            "file": str(full),
            "reason": f"Configured land-mask file does not exist: {full}",
        }

    src: dict[str, Any] = {}
    try:
        suffix = full.suffix.lower()
        if suffix == ".npy":
            mask = np.load(full)
            mask = np.asarray(mask, dtype=bool)
            if mask.shape != (grid.nlat, grid.nlon):
                raise ValueError(
                    f"Land mask shape {mask.shape} does not match grid "
                    f"{(grid.nlat, grid.nlon)} (npy masks must be pre-aligned)."
                )
            masked = mask
            src["format"] = "npy"
            info = {
                "loaded": True,
                "file": str(full),
                "format": "npy",
                "land_cells": int(mask.sum()),
                "land_fraction": float(mask.mean()),
            }
            _LOADED_MASKS[cache_key] = (masked, info)
            return masked, info
        elif suffix in (".tif", ".tiff"):
            import rasterio

            with rasterio.open(full) as ds:
                band = ds.read(1)
                transform = ds.transform
                rows, cols = np.indices(band.shape)
                xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
                lat = np.asarray([float(y) for y in ys.ravel().tolist()])
                lon = np.asarray([float(x) for x in xs.ravel().tolist()])
            land = np.where(np.isfinite(band), band >= 0, False)
            src["format"] = "geotiff"
        elif suffix == ".json":
            import ijson

            with full.open("rb") as handle:
                o_lat = np.fromiter(ijson.items(handle, "latitude.item"), dtype=float)
            with full.open("rb") as handle:
                o_lon = np.fromiter(ijson.items(handle, "longitude.item"), dtype=float)
            if len(o_lat) != len(o_lon):
                raise ValueError("JSON land mask latitude/longitude arrays must be equal length.")
            lat_arr = np.sort(np.unique(o_lat))
            lon_arr = np.sort(np.unique(o_lon))
            lat_idx = np.unique(o_lat, return_inverse=True)[1]
            lon_idx = np.unique(o_lon, return_inverse=True)[1]
            land = np.ones((len(lat_arr), len(lon_arr)), dtype=bool)
            land[lat_idx, lon_idx] = False
            lat, lon = o_lat, o_lon
            del lat_idx, lon_idx
            src["format"] = "json"
        else:  # netCDF (GEBCO-style or depth variable)
            import xarray as xr

            with xr.open_dataset(full) as ds:
                lat = ds["lat"].values if "lat" in ds else ds["latitude"].values
                lon = ds["lon"].values if "lon" in ds else ds["longitude"].values
                if "elevation" in ds:
                    elev = ds["elevation"].values
                    land = _land_from_elevation(lat, lon, elev)
                elif "depth" in ds:
                    land = _land_from_elevation(lat, lon, -np.asarray(ds["depth"].values))
                else:
                    raise ValueError(
                        "NetCDF land mask must contain an 'elevation' or 'depth' variable."
                    )
            src["format"] = "netcdf"
    except Exception as exc:  # noqa: BLE001 - report, never raise into routing
        return None, {
            "loaded": False,
            "file": str(full),
            "reason": f"Failed to read land-mask file: {exc}",
        }

    lat_arr = np.sort(np.unique(np.asarray(lat, dtype=float).ravel()))
    lon_arr = np.sort(np.unique(np.asarray(lon, dtype=float).ravel()))
    land2d = np.asarray(land, dtype=bool).reshape(len(lat_arr), len(lon_arr))

    lat_idx = np.array([int(np.argmin(np.abs(lat_arr - lat))) for lat in grid.lats])
    lon_idx = np.array([int(np.argmin(np.abs(lon_arr - lon))) for lon in grid.lons])
    mask = land2d[np.ix_(lat_idx, lon_idx)]

    info = {
        "loaded": True,
        "file": str(full),
        "format": src.get("format", "unknown"),
        "land_cells": int(mask.sum()),
        "land_fraction": float(mask.mean()),
    }
    try:
        save_path = full.with_suffix(".npy")
        if not save_path.is_file():
            np.save(str(save_path), mask)
    except Exception:
        pass
    _LOADED_MASKS[cache_key] = (mask, info)
    return mask, info