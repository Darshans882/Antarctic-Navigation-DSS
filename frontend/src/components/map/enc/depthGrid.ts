/**
 * Client-side access to the ETOPO2022 bathymetry grid that backs the ENC chart.
 *
 * The asset is produced by `scripts/build_enc_depth_grid.py` from the project's
 * own processed bathymetry (14.4 M ETOPO2022 60s cells) and downsampled to
 * 0.1 degrees, giving a 140 x 1001 grid over 50°S-90°S / 20°E-120°E packed as
 * two little-endian Int32 planes:
 *
 *   depth.bin  [ depth x n , elevation x n ]
 *
 *   depth      >= 0  water depth in metres
 *              == -1 land
 *   elevation  >= 0  land height in metres, otherwise 0
 *
 * Orientation: `enc_depth_meta.json` reports `lat_start` as the *southernmost*
 * latitude, but rows were written northernmost-first (row 0 sits at the 50°S
 * edge).  The grid therefore carries both edges explicitly, so callers never
 * derive a row index from the wrong anchor.
 */

const META_URL = `${import.meta.env.BASE_URL ?? "/"}data/enc_depth_meta.json`;
const BIN_URL = `${import.meta.env.BASE_URL ?? "/"}data/enc_depth.bin`;

export interface DepthGrid {
  stepDeg: number;
  /** Northernmost latitude — grid row 0. */
  latNorth: number;
  /** Southernmost latitude — grid row nLat - 1. */
  latSouth: number;
  lonWest: number;
  lonEast: number;
  nLat: number;
  nLon: number;
  /** Row 0 is the northernmost latitude. */
  depth: Int32Array;
  elevation: Int32Array;
}

interface GridMeta {
  step_deg: number;
  /** Southernmost latitude. */
  lat_start: number;
  lon_start: number;
  n_lat: number;
  n_lon: number;
}

let cache: Promise<DepthGrid> | null = null;

export function loadDepthGrid(): Promise<DepthGrid> {
  if (!cache) {
    cache = (async () => {
      const [metaRes, binRes] = await Promise.all([fetch(META_URL), fetch(BIN_URL)]);
      if (!metaRes.ok) throw new Error(`enc depth meta ${metaRes.status}`);
      if (!binRes.ok) throw new Error(`enc depth bin ${binRes.status}`);
      const meta = (await metaRes.json()) as GridMeta;
      const buf = await binRes.arrayBuffer();
      const cells = meta.n_lat * meta.n_lon;
      const all = new Int32Array(buf);
      if (all.length < cells * 2) {
        throw new Error(`enc depth bin truncated: ${all.length} < ${cells * 2}`);
      }
      const latSouth = meta.lat_start;
      return {
        stepDeg: meta.step_deg,
        latNorth: latSouth + (meta.n_lat - 1) * meta.step_deg,
        latSouth,
        lonWest: meta.lon_start,
        lonEast: meta.lon_start + (meta.n_lon - 1) * meta.step_deg,
        nLat: meta.n_lat,
        nLon: meta.n_lon,
        depth: all.subarray(0, cells),
        elevation: all.subarray(cells, cells * 2),
      };
    })().catch((err) => {
      cache = null;
      throw err;
    });
  }
  return cache;
}

/** Row index for a latitude, measured from the northernmost row. */
export function rowOf(grid: DepthGrid, lat: number): number {
  return Math.round((grid.latNorth - lat) / grid.stepDeg);
}

/** Column index for a longitude. */
export function colOf(grid: DepthGrid, lon: number): number {
  return Math.round((lon - grid.lonWest) / grid.stepDeg);
}

/** Latitude of a grid row (row 0 = northernmost). */
export function latOfRow(grid: DepthGrid, i: number): number {
  return grid.latNorth - i * grid.stepDeg;
}

/** Longitude of a grid column. */
export function lonOfCol(grid: DepthGrid, j: number): number {
  return grid.lonWest + j * grid.stepDeg;
}

/** True when the grid covers this coordinate at all. */
export function gridCovers(grid: DepthGrid, lat: number, lon: number): boolean {
  return (
    lat <= grid.latNorth &&
    lat >= grid.latSouth &&
    lon >= grid.lonWest &&
    lon <= grid.lonEast
  );
}

/** Nearest-cell lookup.  Returns 0 outside the grid, -1 for land, else metres. */
export function depthAt(grid: DepthGrid, lat: number, lon: number): number {
  if (!gridCovers(grid, lat, lon)) return 0;
  const i = rowOf(grid, lat);
  const j = colOf(grid, lon);
  if (i < 0 || i >= grid.nLat || j < 0 || j >= grid.nLon) return 0;
  return grid.depth[i * grid.nLon + j];
}

export function isLand(grid: DepthGrid, lat: number, lon: number): boolean {
  return depthAt(grid, lat, lon) === -1;
}

export function elevationAt(grid: DepthGrid, lat: number, lon: number): number {
  if (!gridCovers(grid, lat, lon)) return 0;
  const i = rowOf(grid, lat);
  const j = colOf(grid, lon);
  if (i < 0 || i >= grid.nLat || j < 0 || j >= grid.nLon) return 0;
  return grid.elevation[i * grid.nLon + j];
}

/**
 * Inclusive index window of the grid rows/columns covering a geographic range,
 * clamped to the grid.  `empty` is true when nothing in the requested range
 * exists in the grid at all.
 */
export function gridWindow(
  grid: DepthGrid,
  latMin: number,
  latMax: number,
  lonMin: number,
  lonMax: number,
): { i0: number; i1: number; j0: number; j1: number; empty: boolean } {
  const i0 = rowOf(grid, latMax);
  const i1 = rowOf(grid, latMin);
  const j0 = colOf(grid, lonMin);
  const j1 = colOf(grid, lonMax);
  if (i1 < 0 || j1 < 0 || i0 >= grid.nLat || j0 >= grid.nLon) {
    return { i0: 0, i1: -1, j0: 0, j1: -1, empty: true };
  }
  return {
    i0: Math.max(0, i0),
    i1: Math.min(grid.nLat - 1, i1),
    j0: Math.max(0, j0),
    j1: Math.min(grid.nLon - 1, j1),
    empty: false,
  };
}
