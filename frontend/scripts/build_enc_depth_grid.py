r"""Build the ENC bathymetry grid consumed by the ECDIS chart layer.

Aggregates the ETOPO2022 bathymetry CSV parts in `Real data\processed\
bathymetry\csv` into two little-endian Int32 planes laid out row-major over a
regular 0.1 degree grid:

    plane 0  depth_m      >= 0 water depth in metres, -1 land, 0 empty
    plane 1  elevation_m  >= 0 land height in metres, otherwise 0

Rows run north to south, so row 0 is the northernmost latitude and
`lat_start` in the metadata is the *southern* edge. Columns run west to east
starting at `lon_start`.

The CSV parts each cover a different latitude band, so the grid cannot be
sized until every part's extent is known. Each part is therefore
accumulated into a grid sized to that part alone, and the partials are
merged into a single global grid at the end. This keeps the script to a
single pass over the data.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(ROOT, os.pardir, "Real data", "processed", "bathymetry", "csv")
CSV_DIR = os.path.normpath(CSV_DIR)
OUT_DIR = os.path.join(ROOT, "public", "data")

STEP = 0.1
COLUMNS = ["latitude", "longitude", "elevation_meters", "depth_meters"]
DTYPES = {name: np.float64 for name in COLUMNS}


class Partial:
    """A part's aggregates, indexed from that part's own northernmost row."""

    def __init__(self, lat_north: float, lat_south: float, lon_west: float, n_lat: int, n_lon: int) -> None:
        self.latNorth = lat_north
        self.latSouth = lat_south
        self.lonWest = lon_west
        self.nLat = n_lat
        self.nLon = n_lon
        self.depthSum = np.zeros((n_lat, n_lon), np.float64)
        self.depthCount = np.zeros((n_lat, n_lon), np.int32)
        self.landSum = np.zeros((n_lat, n_lon), np.float64)


def count_steps(span: float) -> int:
    return int(round(span / STEP)) + 1


def main() -> int:
    parts = sorted(glob.glob(os.path.join(CSV_DIR, "bathymetry_part_*.csv")))
    if not parts:
        print(f"no bathymetry parts found in {CSV_DIR}", file=sys.stderr)
        return 1

    partials: list[Partial] = []
    total_rows = 0

    for path in parts:
        name = os.path.basename(path)
        print(f"reading {name}", flush=True)
        frame = pd.read_csv(path, usecols=COLUMNS, dtype=DTYPES)
        total_rows += len(frame)

        lat = frame["latitude"].values
        lon = frame["longitude"].values
        lat_north = float(lat.max())
        lat_south = float(lat.min())
        lon_west = float(lon.min())
        n_lat = count_steps(lat_north - lat_south)
        n_lon = count_steps(float(lon.max()) - lon_west)

        partial = Partial(lat_north, lat_south, lon_west, n_lat, n_lon)

        row = np.clip(np.round((lat_north - lat) / STEP).astype(np.int32), 0, n_lat - 1)
        col = np.clip(np.round((lon - lon_west) / STEP).astype(np.int32), 0, n_lon - 1)
        flat = row * n_lon + col

        depth = frame["depth_meters"].values
        ocean = np.isfinite(depth) & (depth > 0)
        np.add.at(partial.depthSum.ravel(), flat[ocean], depth[ocean])
        np.add.at(partial.depthCount.ravel(), flat[ocean], 1)

        elevation = frame["elevation_meters"].values
        is_land = np.isfinite(elevation) & (elevation > 0)
        np.add.at(partial.landSum.ravel(), flat[is_land], elevation[is_land])

        partials.append(partial)
        print(f"  {len(frame)} rows, local grid {n_lat} x {n_lon}, lat {lat_south:.4f}..{lat_north:.4f}", flush=True)
        del frame

    lat_north = max(p.latNorth for p in partials)
    lat_south = min(p.latSouth for p in partials)
    lon_west = min(p.lonWest for p in partials)
    lon_east = max(p.lonWest + (p.nLon - 1) * STEP for p in partials)
    n_lat = count_steps(lat_north - lat_south)
    n_lon = count_steps(lon_east - lon_west)

    depth_sum = np.zeros((n_lat, n_lon), np.float64)
    depth_count = np.zeros((n_lat, n_lon), np.int32)
    land_sum = np.zeros((n_lat, n_lon), np.float64)

    for partial in partials:
        row_offset = int(round((lat_north - partial.latNorth) / STEP))
        col_offset = int(round((partial.lonWest - lon_west) / STEP))
        rows = slice(row_offset, row_offset + partial.nLat)
        cols = slice(col_offset, col_offset + partial.nLon)
        depth_sum[rows, cols] += partial.depthSum
        depth_count[rows, cols] += partial.depthCount
        land_sum[rows, cols] += partial.landSum

    mean_depth = np.divide(depth_sum, np.maximum(depth_count, 1))
    is_ocean = depth_count > 0
    is_land_cell = (land_sum > 0) & ~is_ocean

    cells = n_lat * n_lon
    print(f"\nrows={total_rows}  lat {lat_south:.4f}..{lat_north:.4f}  lon {lon_west:.4f}..{lon_east:.4f}")
    print(f"grid {n_lat} x {n_lon} = {cells} cells @ {STEP} deg")
    print(f"ocean={int(is_ocean.sum())}  land={int(is_land_cell.sum())}  empty={int((~(is_ocean | is_land_cell)).sum())}")
    if is_ocean.any():
        print(f"depth {mean_depth[is_ocean].min():.1f} .. {mean_depth[is_ocean].max():.1f} m")

    ocean_flat = is_ocean.ravel()
    land_flat = is_land_cell.ravel()

    depth_out = np.zeros(cells, np.int32)
    depth_out[ocean_flat] = np.clip(np.round(mean_depth.ravel()[ocean_flat]), 0, 30000).astype(np.int32)
    depth_out[land_flat] = -1

    elevation_out = np.zeros(cells, np.int32)
    elevation_out[land_flat] = np.clip(np.round(land_sum.ravel()[land_flat]), 0, 30000).astype(np.int32)

    meta = {
        "step_deg": STEP,
        "lat_start": lat_south,
        "lat_end": lat_north,
        "n_lat": n_lat,
        "lon_start": lon_west,
        "lon_end": lon_east,
        "n_lon": n_lon,
        "row_order": "north_to_south",
        "note": "depth_m: >=0 water depth in metres, -1 land, 0 empty. elevation_m: >=0 land height in metres, else 0.",
        "source": "Real data\\processed\\bathymetry\\csv (ETOPO2022 60s Antarctic 20_120)",
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    bin_path = os.path.join(OUT_DIR, "enc_depth.bin")
    with open(bin_path, "wb") as handle:
        depth_out.astype("<i4").tofile(handle)
        elevation_out.astype("<i4").tofile(handle)
    with open(os.path.join(OUT_DIR, "enc_depth_meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    print(f"\nwrote {bin_path} {os.path.getsize(bin_path)} bytes")
    print("wrote enc_depth_meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
