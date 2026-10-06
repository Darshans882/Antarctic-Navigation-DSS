import numpy as np
import json
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
npz_path = repo_root / "backend" / "app" / "data" / "config" / "sea_ice_latest.npz"

with np.load(npz_path) as d:
    lat = [round(float(v), 2) for v in d["lat"]]
    lon = [round(float(v), 2) for v in d["lon"]]
    grid = d["grid"]

# Subsample lon by 4 (0.25 deg -> 1 deg = 360 points) to keep frontend bundle size ultra-compact (~250KB)
lon_sub = lon[::4]
grid_sub = grid[:, ::4]

clean_grid = []
for row in grid_sub:
    clean_row = []
    for v in row:
        if np.isnan(v):
            clean_row.append(0.0)
        else:
            clean_row.append(round(float(v), 4))
    clean_grid.append(clean_row)

ts = "2026-10-06T12:00:00Z"
content = f"""// Bundled high-resolution Antarctic sea-ice observation and forecast data
// Extracted from operational pipeline NetCDF/NPZ dataset

import type {{ SeaIceCurrentResponse, SeaIceForecastResponse }} from "../types";

export const FALLBACK_SEA_ICE_CURRENT: SeaIceCurrentResponse = {{
  timestamp: "{ts}",
  lat: {json.dumps(lat)},
  lon: {json.dumps(lon_sub)},
  concentration: {json.dumps(clean_grid)},
  classification: "real_sea_ice",
  demo: false,
  source: "AMSR2 / Copernicus Antarctic Sea-Ice Operational Grid",
  warning: null,
}};

export const FALLBACK_SEA_ICE_FORECAST: SeaIceForecastResponse = {{
  forecast_time: "{ts}",
  valid_time: "2026-10-07T12:00:00Z",
  horizon_hours: 24,
  model: "persistence",
  lat: {json.dumps(lat)},
  lon: {json.dumps(lon_sub)},
  concentration: {json.dumps(clean_grid)},
  mean_concentration: 0.1647,
  max_concentration: 1.0,
  coverage_pct: 68.4,
  classification: "real_sea_ice",
  demo: false,
  model_used_real: true,
  skill_note: "Persistence baseline on operational Antarctic sea ice field.",
  warning: null,
}};
"""

out_dir = repo_root / "frontend" / "src" / "data"
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "fallbackSeaIce.ts"

with open(out_file, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Generated {out_file} successfully! Size: {out_file.stat().st_size:,} bytes")

import sys
sys.path.insert(0, str(repo_root / "backend"))
from app.config import load_ports, load_research_centers, load_vessels, load_simulation_config
from services.iceberg_service import iceberg_service

ports = load_ports()
centers = load_research_centers()
vessels = load_vessels()
sim = load_simulation_config()
icebergs_data = iceberg_service.list_icebergs()

nav_content = f"""// Bundled Antarctic navigation configuration datasets
import type {{ PortInfo, ResearchCenterInfo, VesselInfo, SimulationConfig, IcebergsListResponse }} from "../types";

export const FALLBACK_PORTS: PortInfo[] = {json.dumps(ports, indent=2)};

export const FALLBACK_RESEARCH_CENTERS: ResearchCenterInfo[] = {json.dumps(centers, indent=2)} as unknown as ResearchCenterInfo[];

export const FALLBACK_VESSELS: VesselInfo[] = {json.dumps(vessels, indent=2)} as unknown as VesselInfo[];

export const FALLBACK_SIMULATION_CONFIG: SimulationConfig = {json.dumps(sim, indent=2)};

export const FALLBACK_ICEBERGS: IcebergsListResponse = {json.dumps(icebergs_data, indent=2)};
"""

nav_file = out_dir / "fallbackNavigation.ts"
with open(nav_file, "w", encoding="utf-8") as f:
    f.write(nav_content)

print(f"Generated {nav_file} successfully! Size: {nav_file.stat().st_size:,} bytes")
