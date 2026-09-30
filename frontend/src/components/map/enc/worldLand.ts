/**
 * Global land mask for the ENC basemap.
 *
 * The project's bathymetry is an Antarctic survey (ETOPO2022_60s_Antarctic_20_120,
 * 20°E-120°E / 50°S-90°S), so the chart had no land to draw anywhere else and
 * the rest of the world rendered as bare open ocean.  This mask covers the whole
 * world from Natural Earth 110m land so the continents are always drawn.
 *
 * Produced by `scripts/build_world_land_mask.py`: a 0.1 degree global grid over
 * everything Web Mercator can project, packed one bit per cell (MSB first,
 * row-major, row 0 northernmost) so the whole world costs about 750 kB.
 */

const META_URL = `${import.meta.env.BASE_URL ?? "/"}data/world_land_meta.json`;
const BIN_URL = `${import.meta.env.BASE_URL ?? "/"}data/world_land.bin`;

export interface WorldLand {
  stepDeg: number;
  /** Northernmost latitude — row 0. */
  latNorth: number;
  latSouth: number;
  lonWest: number;
  lonEast: number;
  nLat: number;
  nLon: number;
  /** 1 = land, 0 = water. */
  bits: Uint8Array;
}

interface LandMeta {
  step_deg: number;
  lat_start: number;
  lat_end: number;
  lon_start: number;
  n_lat: number;
  n_lon: number;
}

let cache: Promise<WorldLand> | null = null;

export function loadWorldLand(): Promise<WorldLand> {
  if (!cache) {
    cache = (async () => {
      const [metaRes, binRes] = await Promise.all([fetch(META_URL), fetch(BIN_URL)]);
      if (!metaRes.ok) throw new Error(`world land meta ${metaRes.status}`);
      if (!binRes.ok) throw new Error(`world land bin ${binRes.status}`);
      const meta = (await metaRes.json()) as LandMeta;
      const packed = new Uint8Array(await binRes.arrayBuffer());
      const cells = meta.n_lat * meta.n_lon;
      const needBytes = Math.ceil(cells / 8);
      if (packed.length < needBytes) {
        throw new Error(`world land bin truncated: ${packed.length} < ${needBytes}`);
      }
      // Expand to one byte per cell: 6 MB resident, but it keeps the sampling
      // in the render loop to a single array read.
      const bits = new Uint8Array(cells);
      for (let k = 0; k < cells; k++) {
        bits[k] = (packed[k >> 3] >> (7 - (k & 7))) & 1;
      }
      return {
        stepDeg: meta.step_deg,
        latNorth: meta.lat_end,
        latSouth: meta.lat_start,
        lonWest: meta.lon_start,
        lonEast: meta.lon_start + (meta.n_lon - 1) * meta.step_deg,
        nLat: meta.n_lat,
        nLon: meta.n_lon,
        bits,
      };
    })().catch((err) => {
      cache = null;
      throw err;
    });
  }
  return cache;
}

/** Row index for a latitude, measured from the northernmost row. */
export function landRow(mask: WorldLand, lat: number): number {
  return Math.round((mask.latNorth - lat) / mask.stepDeg);
}

/** Column index for a longitude. */
export function landCol(mask: WorldLand, lon: number): number {
  return Math.round((lon - mask.lonWest) / mask.stepDeg);
}

/** Latitude of a grid row (row 0 = northernmost). */
export function landLat(mask: WorldLand, i: number): number {
  return mask.latNorth - i * mask.stepDeg;
}

/** Longitude of a grid column. */
export function landLon(mask: WorldLand, j: number): number {
  return mask.lonWest + j * mask.stepDeg;
}

/**
 * True when the mask covers this coordinate.  Longitudes wrap, so 200°E is the
 * same place as 160°W and is covered rather than treated as out of range.
 */
export function landCovers(mask: WorldLand, lat: number, lon: number): boolean {
  if (lat > mask.latNorth || lat < mask.latSouth) return false;
  const wrapped = wrapLon(lon, mask.lonWest, mask.lonEast);
  return wrapped >= mask.lonWest && wrapped <= mask.lonEast;
}

/** Nearest-cell lookup; false for ocean or anywhere outside the mask. */
export function isLandAt(mask: WorldLand, lat: number, lon: number): boolean {
  if (!landCovers(mask, lat, lon)) return false;
  const i = landRow(mask, lat);
  const j = landCol(mask, wrapLon(lon, mask.lonWest, mask.lonEast));
  if (i < 0 || i >= mask.nLat || j < 0 || j >= mask.nLon) return false;
  return mask.bits[i * mask.nLon + j] === 1;
}

/**
 * Inclusive index window of rows/columns covering a geographic range.
 *
 * The column range is returned unwrapped, so `j1` may exceed `nLon - 1` when
 * the view straddles the antimeridian; callers index the mask modulo `nLon` and
 * keep the unwrapped index when converting back to a longitude.
 */
export function landWindow(
  mask: WorldLand,
  latMin: number,
  latMax: number,
  lonMin: number,
  lonMax: number,
): { i0: number; i1: number; j0: number; j1: number; empty: boolean } {
  const north = Math.min(latMax, mask.latNorth);
  const south = Math.max(latMin, mask.latSouth);
  const i0 = landRow(mask, north);
  const i1 = landRow(mask, south);
  if (i1 < i0 || i1 < 0 || i0 >= mask.nLat) {
    return { i0: 0, i1: -1, j0: 0, j1: -1, empty: true };
  }
  const spanCols = Math.round((lonMax - lonMin) / mask.stepDeg);
  if (spanCols + 1 >= mask.nLon) {
    // The view is wider than the world, so the whole mask is in play.
    return {
      i0: Math.max(0, i0),
      i1: Math.min(mask.nLat - 1, i1),
      j0: 0,
      j1: mask.nLon - 1,
      empty: false,
    };
  }
  return {
    i0: Math.max(0, i0),
    i1: Math.min(mask.nLat - 1, i1),
    j0: landCol(mask, wrapLon(lonMin, mask.lonWest, mask.lonEast)),
    j1: landCol(mask, wrapLon(lonMin, mask.lonWest, mask.lonEast)) + Math.max(1, spanCols),
    empty: false,
  };
}

/** Fold a longitude back into [west, east] so panning past the antimeridian works. */
function wrapLon(lon: number, west: number, east: number): number {
  const span = east - west;
  if (span <= 0) return lon;
  let v = lon;
  while (v < west) v += span;
  while (v > east) v -= span;
  return v;
}
