r"""Build the global land mask used to draw land outside the surveyed bathymetry.

The ETOPO2022 bathymetry in this project only covers the Antarctic box
(20-120E, 50-90S), so anywhere else the ENC chart had nothing but open ocean
and the rest of the world looked like there was no land at all.

Natural Earth 110m land polygons (public domain) are rasterised onto a regular
0.1 degree global grid covering everything Web Mercator can project, then
packed one bit per cell (MSB first, row-major, north to south) so the whole
world costs well under a megabyte.

    frontend/scripts/assets/ne_110m_land.geojson  ->  public/data/world_land.bin
                                                        public/data/world_land_meta.json
"""

from __future__ import annotations

import json
import os

import numpy as np
import shapely
import shapely.ops
from shapely.geometry import shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "scripts", "assets", "ne_110m_land.geojson")
OUT_DIR = os.path.join(ROOT, "public", "data")

STEP = 0.1
# Web Mercator cannot represent anything past +/-85.05112878, so the mask stops
# at the same limit and the chart never asks for a row that does not exist.
MAX_LAT = 85.05112878


def main() -> int:
    with open(SRC, encoding="utf-8") as handle:
        data = json.load(handle)

    land = shapely.ops.unary_union(
        [shape(feature["geometry"]) for feature in data["features"]]
    )
    print(f"land geometry: {land.geom_type}, bounds {land.bounds}")

    n_lon = int(round(360.0 / STEP)) + 1
    n_lat = int(round(2 * MAX_LAT / STEP)) + 1
    lon = -180.0 + np.arange(n_lon) * STEP
    lat = MAX_LAT - np.arange(n_lat) * STEP  # row 0 is the northernmost

    # Rasterise on cell centres so the mask lines up with how the chart samples
    # its grids.  Chunked because a single contains_xy call over six million
    # points is needlessly slow.
    mask = np.zeros((n_lat, n_lon), dtype=bool)
    lon_centres = lon + STEP / 2
    lat_centres = lat - STEP / 2
    for j0 in range(0, n_lon, 256):
        j1 = min(n_lon, j0 + 256)
        xs, ys = np.meshgrid(lon_centres[j0:j1], lat_centres)
        mask[:, j0:j1] = shapely.contains_xy(land, xs, ys)

    cells = int(mask.sum())
    print(f"grid {n_lat} x {n_lon} = {n_lat * n_lon} cells @ {STEP} deg")
    print(f"land cells {cells} ({cells / mask.size * 100:.1f}%)")

    packed = np.packbits(mask.reshape(-1), bitorder="big")
    os.makedirs(OUT_DIR, exist_ok=True)

    bin_path = os.path.join(OUT_DIR, "world_land.bin")
    packed.tofile(bin_path)

    meta = {
        "step_deg": STEP,
        "lat_start": float(lat[-1]),
        "lat_end": float(lat[0]),
        "n_lat": n_lat,
        "lon_start": float(lon[0]),
        "lon_end": float(lon[-1]),
        "n_lon": n_lon,
        "row_order": "north_to_south",
        "bits_per_cell": 1,
        "bitorder": "msb_first",
        "land_cells": cells,
        "total_cells": int(mask.size),
        "source": "Natural Earth 110m land (public domain)",
    }
    with open(os.path.join(OUT_DIR, "world_land_meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    print(f"wrote {bin_path} {os.path.getsize(bin_path)} bytes")
    print("wrote world_land_meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
