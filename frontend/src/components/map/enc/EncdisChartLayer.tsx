import { useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import {
  loadDepthGrid,
  depthAt,
  gridCovers,
  gridWindow,
  latOfRow,
  lonOfCol,
  type DepthGrid,
} from "./depthGrid";
import {
  loadWorldLand,
  isLandAt,
  landWindow,
  landLat,
  landLon,
  type WorldLand,
} from "./worldLand";
import { marchingSquares } from "./marchingSquares";
import { ENC, CONTOUR_LEVELS, SEA_NAMES, depthColorInto } from "./palette";

/**
 * Procedural ECDIS / ENC chart renderer.
 *
 * Paints a nautical chart into a canvas that lives in its own Leaflet pane
 * (below the overlay pane, so the dashboard's real route / sea-ice / iceberg /
 * vessel layers still draw on top).  Everything is derived from the project's
 * real bathymetry and sea-ice grids -- there are no hand-placed soundings.
 *
 * Styling follows the reference chart: graded depth bands, labelled iso-depth
 * contours, scattered depth soundings, tan land against blue water, a lat/lon
 * graticule with edge labels, spaced-out water-body names, a magenta planned
 * route, and a dual NM/km scale bar.
 */

/** Raster block size in CSS pixels for the depth / ice fills. */
const BLOCK = 4;

/**
 * Target on-screen spacing between sampled grid cells.  Below this the 0.1
 * degree grid carries more detail than a pixel can show, so the contour and
 * coastline passes step over the surplus cells instead of tracing them.
 */
const MIN_CELL_PX = 1.5;

/** How many grid cells to skip so cells land at least `MIN_CELL_PX` apart. */
function gridStep(view: View, grid: DepthGrid): number {
  const cellPx = (view.worldSize * grid.stepDeg) / 360;
  if (cellPx >= MIN_CELL_PX) return 1;
  return Math.min(32, Math.ceil(MIN_CELL_PX / cellPx));
}

/** Ice concentration at or above this is charted as a "Sea Ice Area". */
const ICE_AREA_THRESHOLD = 0.15;

/** Ice concentration at or above this is charted as a "Restricted Area". */
const ICE_RESTRICTED_THRESHOLD = 0.8;

const MAX_MERCATOR_LAT = 85.05112878;

export interface EncRoutePoint {
  lat: number;
  lon: number;
  name?: string;
}

export interface EncIceberg {
  lat: number;
  lon: number;
  id?: string;
}

export interface EncChartLayers {
  depthContours: boolean;
  depthSoundings: boolean;
  seaIceArea: boolean;
  seaIceOverlay: boolean;
  restrictedAreas: boolean;
  plannedRoute: boolean;
  navigationMarks: boolean;
  aisTargets: boolean;
}

export const DEFAULT_ENC_LAYERS: EncChartLayers = {
  depthContours: true,
  depthSoundings: true,
  seaIceArea: true,
  seaIceOverlay: true,
  restrictedAreas: true,
  plannedRoute: true,
  navigationMarks: true,
  aisTargets: true,
};

interface SeaIceGridLike {
  lat: number[];
  lon: number[];
  concentration: number[][];
}

interface EncdisChartLayerProps {
  active: boolean;
  seaIce?: SeaIceGridLike | null;
  route?: EncRoutePoint[];
  icebergs?: EncIceberg[];
  vessel?: { lat: number; lon: number; label: string; heading?: number } | null;
  marks?: EncRoutePoint[];
  layers: EncChartLayers;
}

/** Everything `render` needs besides the grid, sampler and layer toggles. */
interface RenderProps {
  seaIce?: SeaIceGridLike | null;
  route?: EncRoutePoint[];
  icebergs?: EncIceberg[];
  vessel?: { lat: number; lon: number; label: string; heading?: number } | null;
  marks?: EncRoutePoint[];
}

interface View {
  w: number;
  h: number;
  zoom: number;
  worldSize: number;
  originX: number;
  originY: number;
  /** Screen-space offset of the rendered surface's (0,0) inside the map. */
  offsetX: number;
  offsetY: number;
  toPx: (lat: number, lon: number) => { x: number; y: number };
  toLatLon: (x: number, y: number) => { lat: number; lon: number };
  /** World-pixel X per grid column, or null when no grid is bound. */
  gridX: Float64Array | null;
  /** World-pixel Y per grid row, or null when no grid is bound. */
  gridY: Float64Array | null;
  /** Project a (possibly fractional) grid index to surface pixels. */
  toPxIndex: (i: number, j: number) => { x: number; y: number };
}

/** Web-Mercator world Y for a latitude, in pixels at this world size. */
function mercatorY(lat: number, worldSize: number): number {
  const clamped = Math.max(-MAX_MERCATOR_LAT, Math.min(MAX_MERCATOR_LAT, lat));
  const phi = (clamped * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(Math.PI / 4 + phi / 2)) / Math.PI) / 2) * worldSize;
}

/**
 * Build the projection for a surface `w` x `h` CSS pixels.
 *
 * `offsetX` / `offsetY` place the surface's origin inside the map viewport, so
 * a cached layer can be rendered larger than the screen and still be blitted
 * back at the right place while the user pans.
 *
 * When a grid is supplied the per-row / per-column world pixels are precomputed.
 * The bathymetry grid is regular, so projecting a contour vertex becomes two
 * array reads instead of a `tan` + `log`, which is what made the contour pass
 * slow enough to lag behind Leaflet's own pan animation.
 */
function makeView(
  map: L.Map,
  w: number,
  h: number,
  offsetX = 0,
  offsetY = 0,
  grid: DepthGrid | null = null,
): View {
  const zoom = map.getZoom();
  const worldSize = 256 * Math.pow(2, zoom);
  // Derive the world-pixel coordinate of the container's top-left from the
  // live pan transform. map.getPixelOrigin() can stay frozen while the map
  // pans, which would leave the chart stuck while Leaflet panes move.
  const topLeft = map.project(map.containerPointToLatLng(L.point(0, 0)), zoom);
  const originX = topLeft.x;
  const originY = topLeft.y;

  let gridX: Float64Array | null = null;
  let gridY: Float64Array | null = null;
  if (grid) {
    gridX = new Float64Array(grid.nLon);
    for (let j = 0; j < grid.nLon; j++) {
      gridX[j] = ((lonOfCol(grid, j) + 180) / 360) * worldSize;
    }
    gridY = new Float64Array(grid.nLat);
    for (let i = 0; i < grid.nLat; i++) {
      gridY[i] = mercatorY(latOfRow(grid, i), worldSize);
    }
  }

  const view: View = {
    w,
    h,
    zoom,
    worldSize,
    originX,
    originY,
    offsetX,
    offsetY,
    gridX,
    gridY,
    toPx(lat, lon) {
      return {
        x: ((lon + 180) / 360) * worldSize - originX + offsetX,
        y: mercatorY(lat, worldSize) - originY + offsetY,
      };
    },
    toLatLon(x, y) {
      const mx = x - offsetX + originX;
      const my = y - offsetY + originY;
      const lon = (mx / worldSize) * 360 - 180;
      const lat =
        (180 / Math.PI) *
        Math.atan(Math.sinh(Math.PI * (1 - (2 * my) / worldSize)));
      return { lat, lon };
    },
    toPxIndex(i, j) {
      if (!gridX || !gridY) return view.toPx(latOfRow(grid as DepthGrid, i), lonOfCol(grid as DepthGrid, j));
      const i0 = Math.floor(i);
      const j0 = Math.floor(j);
      const ti = i - i0;
      const tj = j - j0;
      const i1 = Math.min(gridY.length - 1, i0 + 1);
      const j1 = Math.min(gridX.length - 1, j0 + 1);
      const y = gridY[i0] + (gridY[i1] - gridY[i0]) * ti;
      const x = gridX[j0] + (gridX[j1] - gridX[j0]) * tj;
      return { x: x - originX + offsetX, y: y - originY + offsetY };
    },
  };

  return view;
}

/** Nearest-neighbour lookup into a rectilinear concentration grid. */
function makeConcentrationSampler(seaIce: SeaIceGridLike | null | undefined) {
  if (!seaIce || seaIce.lat.length === 0 || seaIce.lon.length === 0) {
    return () => 0;
  }
  const { lat, lon, concentration } = seaIce;
  const nLat = lat.length;
  const nLon = lon.length;
  const latStep = nLat > 1 ? (lat[1] - lat[0]) || 1 : 1;
  const lonStep = nLon > 1 ? (lon[1] - lon[0]) || 1 : 1;
  const ascendingLat = latStep > 0;

  return (queryLat: number, queryLon: number): number => {
    const i = ascendingLat
      ? Math.round((queryLat - lat[0]) / latStep)
      : Math.round((lat[0] - queryLat) / latStep);
    let j = Math.round((queryLon - lon[0]) / lonStep);
    if (i < 0 || i >= nLat) return 0;
    // Longitude may wrap past 180 into the grid's own range.
    if (j < 0 || j >= nLon) {
      const span = lonStep * nLon;
      j = ((j % nLon) + nLon) % nLon;
      void span;
    }
    const row = concentration[i];
    if (!row) return 0;
    const v = row[j];
    return typeof v === "number" ? v : 0;
  };
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function isAntarcticLand(lat: number): boolean {
  return lat <= -65;
}

function landColorInto(lat: number, out: Uint8ClampedArray, o: number): void {
  const hex = isAntarcticLand(lat) ? ENC.iceSheet : ENC.land;
  out[o] = parseInt(hex.slice(1, 3), 16);
  out[o + 1] = parseInt(hex.slice(3, 5), 16);
  out[o + 2] = parseInt(hex.slice(5, 7), 16);
  out[o + 3] = 255;
}

/** Format a depth the way a chart does: metres, decimals only when shallow. */
function formatSounding(depth: number): string {
  if (depth < 10) return depth.toFixed(1);
  return String(Math.round(depth));
}

/** Depth used for water outside the charted region.  There is no bathymetry
 *  there, so the basemap falls back to open ocean instead of leaving a hole.
 *  This sits in the deepest band so the fill matches the real deep water at the
 *  edge of the surveyed box and no seam is visible where the two meet. */
const OFFSHORE_DEPTH = 5500;

/** Blend a sea-ice tint over a block already coloured in `data` at `o`. */
function tintSeaIceInto(
  lat: number,
  lon: number,
  out: Uint8ClampedArray,
  o: number,
  iceAt: (lat: number, lon: number) => number,
): void {
  const c = iceAt(lat, lon);
  if (c < ICE_AREA_THRESHOLD) return;
  const edge = Math.min(1, (c - ICE_AREA_THRESHOLD) / 0.25);
  const tint = hexToRgba(ENC.seaIce, 0.35 + 0.4 * edge);
  const m = tint.match(/(\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return;
  out[o] = Math.round(out[o] * 0.35 + Number(m[1]) * 0.65);
  out[o + 1] = Math.round(out[o + 1] * 0.35 + Number(m[2]) * 0.65);
  out[o + 2] = Math.round(out[o + 2] * 0.35 + Number(m[3]) * 0.65);
}

function drawBlockRaster(
  ctx: CanvasRenderingContext2D,
  view: View,
  grid: DepthGrid,
  land: WorldLand | null,
  iceAt: (lat: number, lon: number) => number,
  layers: EncChartLayers,
): void {
  const bw = Math.max(1, Math.ceil(view.w / BLOCK));
  const bh = Math.max(1, Math.ceil(view.h / BLOCK));

  const off = document.createElement("canvas");
  off.width = bw;
  off.height = bh;
  const octx = off.getContext("2d");
  if (!octx) return;
  const img = octx.createImageData(bw, bh);
  const data = img.data;

  for (let by = 0; by < bh; by++) {
    const py = by * BLOCK + BLOCK / 2;
    for (let bx = 0; bx < bw; bx++) {
      const px = bx * BLOCK + BLOCK / 2;
      const { lat, lon } = view.toLatLon(px, py);
      const o = (by * bw + bx) * 4;
      if (!gridCovers(grid, lat, lon)) {
        // Beyond the surveyed box there is no bathymetry, but the basemap must
        // still cover the whole viewport.  Land comes from the global mask so
        // the continents are never missing; the rest is open ocean.
        if (land && isLandAt(land, lat, lon)) {
          landColorInto(lat, data, o);
        } else {
          depthColorInto(OFFSHORE_DEPTH, data, o);
          if (layers.seaIceArea) tintSeaIceInto(lat, lon, data, o, iceAt);
        }
        continue;
      }
      const d = depthAt(grid, lat, lon);
      if (d === -1) {
        landColorInto(lat, data, o);
        continue;
      }
      if (d === 0) {
        // Inside the grid but no sounding recorded: treat as charted water.
        depthColorInto(1, data, o);
        continue;
      }
      depthColorInto(d, data, o);

      if (layers.seaIceArea) tintSeaIceInto(lat, lon, data, o, iceAt);
    }
  }

  octx.putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, bw, bh, 0, 0, bw * BLOCK, bh * BLOCK);
  ctx.imageSmoothingEnabled = true;
}

function strokePath(ctx: CanvasRenderingContext2D, pts: { x: number; y: number }[]): void {
  if (pts.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
  ctx.stroke();
}

function drawCoastline(
  ctx: CanvasRenderingContext2D,
  view: View,
  grid: DepthGrid,
  bounds: L.LatLngBounds,
): void {
  const win = gridWindow(grid, bounds.getSouth(), bounds.getNorth(), bounds.getWest(), bounds.getEast());
  if (win.empty) return;
  const index = (i: number, j: number) => i * grid.nLon + j;
  // Field: land = 1, water = 0, iso-level 0.5 traces the coastline.
  const field = new Uint8Array((win.i1 - win.i0 + 1) * (win.j1 - win.j0 + 1));
  const w = win.j1 - win.j0 + 1;
  for (let i = win.i0; i <= win.i1; i++) {
    for (let j = win.j0; j <= win.j1; j++) {
      field[(i - win.i0) * w + (j - win.j0)] =
        grid.depth[index(i, j)] === -1 ? 1 : 0;
    }
  }
  const localIndex = (i: number, j: number) => (i - win.i0) * w + (j - win.j0);
  const step = gridStep(view, grid);
  const lines = marchingSquares(
    field,
    0,
    win.i1 - win.i0,
    0,
    win.j1 - win.j0,
    0.5,
    localIndex,
    (i, j) => view.toPxIndex(win.i0 + i, win.j0 + j),
    step,
    step,
  );

  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  for (const line of lines) {
    if (line.length < 2) continue;
    const midLat = view.toLatLon(line[0].x, line[0].y).lat;
    // Style must be set before stroking, otherwise every line is also stroked
    // with the previous line's colour.
    ctx.strokeStyle = isAntarcticLand(midLat) ? ENC.iceSheetEdge : ENC.landEdge;
    ctx.lineWidth = 1.1;
    strokePath(ctx, line);
  }
}

/**
 * Coastline for the rest of the world, from the global land mask.
 *
 * Inside the surveyed box the bathymetry grid already draws a coastline at full
 * detail, so this pass is clipped to the area *outside* that box.  That keeps
 * the two from doubling up while still letting a coastline run continuously out
 * of the survey area, the way a real chart continues off its edge.
 */
function drawWorldCoastline(
  ctx: CanvasRenderingContext2D,
  view: View,
  land: WorldLand,
  grid: DepthGrid,
  bounds: L.LatLngBounds,
): void {
  const win = landWindow(land, bounds.getSouth(), bounds.getNorth(), bounds.getWest(), bounds.getEast());
  if (win.empty) return;

  // Skip mask cells the screen cannot resolve, exactly as the depth pass does.
  // Sampling at the stride up front keeps the field proportional to the viewport
  // instead of to the whole 6 M-cell mask.
  const cellPx = land.stepDeg * (view.worldSize / 360);
  const step = cellPx >= MIN_CELL_PX ? 1 : Math.min(32, Math.ceil(MIN_CELL_PX / cellPx));

  const nRows = win.i1 - win.i0 + 1;
  const nCols = win.j1 - win.j0 + 1;
  const rows = Math.floor((nRows - 1) / step) + 1;
  const cols = Math.floor((nCols - 1) / step) + 1;
  if (rows < 2 || cols < 2) return;

  const field = new Uint8Array(rows * cols);
  for (let r = 0; r < rows; r++) {
    const row = (win.i0 + r * step) * land.nLon;
    for (let c = 0; c < cols; c++) {
      // Columns are unwrapped, so they can run past the antimeridian; the mask
      // itself only has one copy.
      const col = (win.j0 + c * step) % land.nLon;
      field[r * cols + c] = land.bits[row + col];
    }
  }

  const lines = marchingSquares(
    field,
    0,
    rows - 1,
    0,
    cols - 1,
    0.5,
    (i, j) => i * cols + j,
    (i, j) => view.toPx(landLat(land, win.i0 + i * step), landLon(land, win.j0 + j * step)),
    1,
    1,
  );
  if (lines.length === 0) return;

  // Clip to the viewport minus the surveyed box, in up to four bands.
  const bands = outsideBoxBands(view, grid);
  if (bands.length === 0) return;

  ctx.save();
  ctx.beginPath();
  for (const b of bands) ctx.rect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0);
  ctx.clip();

  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.lineWidth = 1.1;
  for (const line of lines) {
    if (line.length < 2) continue;
    const midLat = view.toLatLon(line[0].x, line[0].y).lat;
    ctx.strokeStyle = isAntarcticLand(midLat) ? ENC.iceSheetEdge : ENC.landEdge;
    strokePath(ctx, line);
  }
  ctx.restore();
}

/**
 * Screen-space rectangles covering the visible area outside the depth grid.
 * Empty when the viewport lies wholly inside the surveyed box.
 */
function outsideBoxBands(
  view: View,
  grid: DepthGrid,
): { x0: number; y0: number; x1: number; y1: number }[] {
  const nw = view.toPx(grid.latNorth, grid.lonWest);
  const se = view.toPx(grid.latSouth, grid.lonEast);
  const bx0 = Math.min(nw.x, se.x);
  const bx1 = Math.max(nw.x, se.x);
  const by0 = Math.min(nw.y, se.y);
  const by1 = Math.max(nw.y, se.y);

  const W = view.w;
  const H = view.h;
  const bands: { x0: number; y0: number; x1: number; y1: number }[] = [];
  const push = (x0: number, y0: number, x1: number, y1: number) => {
    const cx0 = Math.max(0, x0);
    const cy0 = Math.max(0, y0);
    const cx1 = Math.min(W, x1);
    const cy1 = Math.min(H, y1);
    if (cx1 - cx0 > 0.5 && cy1 - cy0 > 0.5) bands.push({ x0: cx0, y0: cy0, x1: cx1, y1: cy1 });
  };
  // Above and below the box, then left and right of it.
  push(0, 0, W, by0);
  push(0, by1, W, H);
  push(0, by0, bx0, by1);
  push(bx1, by0, W, by1);
  return bands;
}

function drawDepthContours(
  ctx: CanvasRenderingContext2D,
  view: View,
  grid: DepthGrid,
  bounds: L.LatLngBounds,
): void {
  const win = gridWindow(grid, bounds.getSouth(), bounds.getNorth(), bounds.getWest(), bounds.getEast());
  if (win.empty) return;
  const index = (i: number, j: number) => i * grid.nLon + j;

  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.font = "italic 9px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  // Depth range actually present in view, so levels the window cannot reach are
  // skipped instead of running a full marching-squares pass for nothing.
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = win.i0; i <= win.i1; i += 1) {
    const base = i * grid.nLon;
    for (let j = win.j0; j <= win.j1; j += 1) {
      const d = grid.depth[base + j];
      if (d < 0) continue;
      if (d < lo) lo = d;
      if (d > hi) hi = d;
    }
  }
  if (lo > hi) return;

  const step = gridStep(view, grid);
  const toPoint = (i: number, j: number) => view.toPxIndex(i, j);

  for (const level of CONTOUR_LEVELS) {
    if (level < lo || level > hi) continue;
    const lines = marchingSquares(
      grid.depth,
      win.i0,
      win.i1,
      win.j0,
      win.j1,
      level,
      index,
      toPoint,
      step,
      step,
    );
    const isIndex = level === CONTOUR_LEVELS[0] || level === 1000 || level === 5000;
    ctx.strokeStyle = isIndex ? ENC.contourIndex : ENC.contour;
    ctx.lineWidth = isIndex ? 1.1 : 0.7;
    if (isIndex) ctx.setLineDash([]);

    let labelsDrawn = 0;
    for (const line of lines) {
      strokePath(ctx, line);
      if (isIndex && labelsDrawn < 6 && line.length > 24) {
        const mid = line[Math.floor(line.length / 2)];
        const label = String(level);
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = hexToRgba(ENC.contour, 0.85);
        ctx.fillRect(mid.x - tw / 2 - 2, mid.y - 6, tw + 4, 12);
        ctx.fillStyle = ENC.ink;
        ctx.fillText(label, mid.x, mid.y);
        labelsDrawn++;
      }
    }
  }
  ctx.setLineDash([]);
}

function drawRestrictedAreas(
  ctx: CanvasRenderingContext2D,
  view: View,
  seaIce: SeaIceGridLike | null | undefined,
  iceAt: (lat: number, lon: number) => number,
  bounds: L.LatLngBounds,
): void {
  if (!seaIce || seaIce.lat.length < 2 || seaIce.lon.length < 2) return;
  const { lat, lon, concentration } = seaIce;
  const nLat = lat.length;
  const nLon = lon.length;
  const latStep = lat[1] - lat[0] || 1;
  const lonStep = lon[1] - lon[0] || 1;

  const i0 = Math.max(0, Math.round((bounds.getNorth() - lat[0]) / latStep));
  const i1 = Math.min(nLat - 1, Math.round((bounds.getSouth() - lat[0]) / latStep));
  const j0 = Math.max(0, Math.round((bounds.getWest() - lon[0]) / lonStep));
  const j1 = Math.min(nLon - 1, Math.round((bounds.getEast() - lon[0]) / lonStep));
  if (i1 <= i0 || j1 <= j0) return;

  const w = j1 - j0 + 1;
  const field = new Float32Array((i1 - i0 + 1) * w);
  for (let i = i0; i <= i1; i++) {
    const row = concentration[i] ?? [];
    for (let j = j0; j <= j1; j++) {
      field[(i - i0) * w + (j - j0)] = typeof row[j] === "number" ? row[j] : 0;
    }
  }
  void iceAt;

  const lines = marchingSquares(
    field,
    0,
    i1 - i0,
    0,
    j1 - j0,
    ICE_RESTRICTED_THRESHOLD,
    (i, j) => (i) * w + j,
    (i, j) => {
      const flatLat = lat[0] + (i0 + i) * latStep;
      const flatLon = lon[0] + (j0 + j) * lonStep;
      return view.toPx(flatLat, flatLon);
    },
  );

  ctx.save();
  ctx.fillStyle = hexToRgba(ENC.restricted, 0.55);
  ctx.strokeStyle = ENC.restrictedEdge;
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 4]);
  for (const line of lines) {
    if (line.length < 3) continue;
    ctx.beginPath();
    ctx.moveTo(line[0].x, line[0].y);
    for (let i = 1; i < line.length; i++) ctx.lineTo(line[i].x, line[i].y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();

  if (lines.length > 0) {
    ctx.save();
    ctx.fillStyle = ENC.restrictedEdge;
    ctx.font = "600 9px 'Segoe UI', system-ui, sans-serif";
    ctx.textAlign = "center";
    const first = lines[0];
    const anchor = first[Math.floor(first.length / 2)];
    if (anchor) {
      ctx.fillText("RESTRICTED AREA", anchor.x, anchor.y - 10);
    }
    ctx.restore();
  }
}

function drawGraticule(ctx: CanvasRenderingContext2D, view: View, bounds: L.LatLngBounds): void {
  const lonStep = view.zoom <= 3 ? 20 : view.zoom <= 5 ? 10 : 5;
  const latStep = lonStep;

  ctx.save();
  ctx.font = "9px 'Segoe UI', system-ui, sans-serif";
  ctx.textBaseline = "middle";

  const west = bounds.getWest();
  const east = bounds.getEast();
  const firstLon = Math.ceil(west / lonStep) * lonStep;
  for (let lon = firstLon; lon <= east; lon += lonStep) {
    const { x } = view.toPx(0, lon);
    if (x < -20 || x > view.w + 20) continue;
    const major = lon % (lonStep * 2) === 0;
    ctx.strokeStyle = major ? ENC.graticuleMajor : ENC.graticule;
    ctx.lineWidth = major ? 0.9 : 0.6;
    ctx.setLineDash(major ? [] : [3, 4]);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, view.h);
    ctx.stroke();

    ctx.setLineDash([]);
    const label = `${Math.abs(lon)}°${lon >= 0 ? "E" : "W"}`;
    ctx.fillStyle = hexToRgba(ENC.axisBand, 0.9);
    const tw = ctx.measureText(label).width;
    ctx.fillRect(x - tw / 2 - 3, 1, tw + 6, 13);
    ctx.fillRect(x - tw / 2 - 3, view.h - 14, tw + 6, 13);
    ctx.fillStyle = ENC.ink;
    ctx.textAlign = "center";
    ctx.fillText(label, x, 8);
    ctx.fillText(label, x, view.h - 7);
  }

  const south = bounds.getSouth();
  const north = bounds.getNorth();
  const firstLat = Math.ceil(south / latStep) * latStep;
  for (let lat = firstLat; lat <= north; lat += latStep) {
    const { y } = view.toPx(lat, 0);
    if (y < -20 || y > view.h + 20) continue;
    const major = lat % (latStep * 2) === 0;
    ctx.strokeStyle = major ? ENC.graticuleMajor : ENC.graticule;
    ctx.lineWidth = major ? 0.9 : 0.6;
    ctx.setLineDash(major ? [] : [3, 4]);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(view.w, y);
    ctx.stroke();

    ctx.setLineDash([]);
    const label = `${Math.abs(lat)}°${lat >= 0 ? "N" : "S"}`;
    ctx.fillStyle = hexToRgba(ENC.axisBand, 0.9);
    ctx.font = "9px 'Segoe UI', system-ui, sans-serif";
    const tw = ctx.measureText(label).width;
    ctx.fillRect(1, y - 6, tw + 6, 13);
    ctx.fillRect(view.w - tw - 7, y - 6, tw + 6, 13);
    ctx.fillStyle = ENC.ink;
    ctx.textAlign = "left";
    ctx.fillText(label, 4, y);
    ctx.textAlign = "right";
    ctx.fillText(label, view.w - 4, y);
  }
  ctx.restore();
}

function drawSeaNames(
  ctx: CanvasRenderingContext2D,
  view: View,
  bounds: L.LatLngBounds,
): void {
  ctx.save();
  ctx.fillStyle = hexToRgba(ENC.ink, 0.55);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const sea of SEA_NAMES) {
    if (sea.lat < bounds.getSouth() || sea.lat > bounds.getNorth()) continue;
    const { x, y } = view.toPx(sea.lat, sea.lon);
    if (x < 0 || x > view.w || y < 0 || y > view.h) continue;
    ctx.font = `${sea.italic ? "italic " : ""}${sea.size}px 'Segoe UI', system-ui, sans-serif`;
    ctx.letterSpacing = `${Math.max(1, sea.size * 0.18)}px`;
    ctx.fillText(sea.name, x, y);
  }
  ctx.letterSpacing = "0px";
  ctx.restore();
}

function drawSoundings(
  ctx: CanvasRenderingContext2D,
  view: View,
  grid: DepthGrid,
  bounds: L.LatLngBounds,
): void {
  // Anchor soundings geographically (as a surveyed chart does) so they hold
  // still while panning, with a deterministic jitter to avoid a rigid lattice.
  const degPerPx = 360 / view.worldSize;
  const targetSpacingPx = 62;
  const stepLon = targetSpacingPx * degPerPx;
  const midLat = (bounds.getNorth() + bounds.getSouth()) / 2;
  const stepLat = Math.max(1e-4, stepLon * Math.cos((midLat * Math.PI) / 180));

  const west = bounds.getWest() - stepLon;
  const east = bounds.getEast() + stepLon;
  const north = bounds.getNorth() + stepLat;
  const south = bounds.getSouth() - stepLat;

  const hash = (a: number, b: number): number => {
    const s = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453;
    return s - Math.floor(s);
  };

  ctx.save();
  ctx.font = "italic 9px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (let lat = Math.ceil(south / stepLat) * stepLat; lat <= north; lat += stepLat) {
    for (let lon = Math.ceil(west / stepLon) * stepLon; lon <= east; lon += stepLon) {
      const jx = (hash(Math.round(lat * 100), Math.round(lon * 100)) - 0.5) * stepLon * 0.7;
      const jy =
        (hash(Math.round(lon * 100) + 7, Math.round(lat * 100) + 13) - 0.5) * stepLat * 0.7;
      const slat = lat + jy;
      const slon = lon + jx;
      if (!gridCovers(grid, slat, slon)) continue;
      const d = depthAt(grid, slat, slon);
      if (d === -1) {
        const { x, y } = view.toPx(slat, slon);
        if (x < 0 || x > view.w || y < 0 || y > view.h) continue;
        ctx.fillStyle = ENC.soundingLand;
        ctx.fillText("•", x, y);
        continue;
      }
      if (d <= 0) continue;
      const { x, y } = view.toPx(slat, slon);
      if (x < 0 || x > view.w || y < 0 || y > view.h) continue;
      const text = formatSounding(d);
      ctx.lineWidth = 2.4;
      ctx.strokeStyle = hexToRgba(ENC.contour, 0.8);
      ctx.strokeText(text, x, y);
      ctx.fillStyle = ENC.sounding;
      ctx.fillText(text, x, y);
    }
  }
  ctx.restore();
}

function drawRoute(
  ctx: CanvasRenderingContext2D,
  view: View,
  route: EncRoutePoint[],
): void {
  const pts = route
    .map((p) => view.toPx(p.lat, p.lon))
    .filter((p) => p.x > -4000 && p.x < view.w + 4000 && p.y > -4000 && p.y < view.h + 4000);
  if (pts.length < 2) return;

  ctx.save();
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
  ctx.strokeStyle = hexToRgba(ENC.route, 0.95);
  ctx.lineWidth = 7;
  ctx.stroke();
  ctx.strokeStyle = ENC.routeCore;
  ctx.lineWidth = 2.4;
  ctx.stroke();
  ctx.restore();

  // Waypoints: small magenta-ringed circles, labelled like the reference.
  ctx.save();
  ctx.font = "600 9px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let i = 0; i < route.length; i++) {
    const { x, y } = view.toPx(route[i].lat, route[i].lon);
    if (x < -40 || x > view.w + 40 || y < -40 || y > view.h + 40) continue;
    ctx.beginPath();
    ctx.arc(x, y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = ENC.waypoint;
    ctx.fill();
    ctx.strokeStyle = ENC.routeCore;
    ctx.lineWidth = 1.4;
    ctx.stroke();
    if (route[i].name) {
      ctx.lineWidth = 2.6;
      ctx.strokeStyle = hexToRgba(ENC.contour, 0.85);
      ctx.strokeText(route[i].name as string, x, y - 11);
      ctx.fillStyle = ENC.routeCore;
      ctx.fillText(route[i].name as string, x, y - 11);
    }
  }
  ctx.restore();
}

function drawNavigationMark(ctx: CanvasRenderingContext2D, view: View, mark: EncRoutePoint): void {
  const { x, y } = view.toPx(mark.lat, mark.lon);
  if (x < -30 || x > view.w + 30 || y < -30 || y > view.h + 30) return;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(x, y - 7);
  ctx.lineTo(x + 4, y + 3);
  ctx.lineTo(x - 4, y + 3);
  ctx.closePath();
  ctx.fillStyle = ENC.buoy;
  ctx.fill();
  ctx.strokeStyle = "#c96a3a";
  ctx.lineWidth = 1.3;
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x, y + 3);
  ctx.lineTo(x, y + 8);
  ctx.stroke();
  if (mark.name) {
    ctx.font = "600 9px 'Segoe UI', system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 2.6;
    ctx.strokeStyle = hexToRgba(ENC.contour, 0.85);
    ctx.strokeText(mark.name, x + 7, y);
    ctx.fillStyle = ENC.panelInk;
    ctx.fillText(mark.name, x + 7, y);
  }
  ctx.restore();
}

function drawIcebergs(ctx: CanvasRenderingContext2D, view: View, icebergs: EncIceberg[]): void {
  ctx.save();
  for (const berg of icebergs) {
    const { x, y } = view.toPx(berg.lat, berg.lon);
    if (x < -20 || x > view.w + 20 || y < -20 || y > view.h + 20) continue;
    ctx.beginPath();
    ctx.moveTo(x, y - 5);
    ctx.lineTo(x + 4.5, y + 1);
    ctx.lineTo(x + 1, y + 4.5);
    ctx.lineTo(x - 4.5, y + 1);
    ctx.closePath();
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.strokeStyle = "#2f7fd0";
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }
  ctx.restore();
}

function drawVessel(
  ctx: CanvasRenderingContext2D,
  view: View,
  vessel: { lat: number; lon: number; label: string; heading?: number },
): void {
  const { x, y } = view.toPx(vessel.lat, vessel.lon);
  if (x < -40 || x > view.w + 40 || y < -40 || y > view.h + 40) return;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(((vessel.heading ?? 0) * Math.PI) / 180);
  ctx.beginPath();
  ctx.moveTo(0, -11);
  ctx.lineTo(6, 8);
  ctx.lineTo(0, 4.5);
  ctx.lineTo(-6, 8);
  ctx.closePath();
  ctx.fillStyle = "#f97316";
  ctx.fill();
  ctx.strokeStyle = "#7c2d12";
  ctx.lineWidth = 1.3;
  ctx.stroke();
  ctx.restore();

  ctx.save();
  ctx.font = "600 10px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineWidth = 3;
  ctx.strokeStyle = hexToRgba(ENC.contour, 0.9);
  ctx.strokeText(vessel.label, x, y + 18);
  ctx.fillStyle = "#7c2d12";
  ctx.fillText(vessel.label, x, y + 18);
  ctx.restore();
}

function drawScaleBar(
  ctx: CanvasRenderingContext2D,
  view: View,
  centerLat: number,
): void {
  const metersPerPx =
    (156543.03392804097 * Math.cos((centerLat * Math.PI) / 180)) / Math.pow(2, view.zoom);
  const targetPx = 170;
  const rawMeters = metersPerPx * targetPx;
  const niceMeters = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000];
  let chosen = niceMeters[niceMeters.length - 1];
  for (const n of niceMeters) {
    if (n >= rawMeters) {
      chosen = n;
      break;
    }
  }
  const barPx = chosen / metersPerPx;
  if (barPx < 20 || barPx > view.w * 0.6) return;

  const x0 = 14;
  const y0 = view.h - 16;

  ctx.save();
  ctx.font = "9px 'Segoe UI', system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";

  // Kilometre scale, alternating filled / hollow segments.
  const segs = 4;
  const segW = barPx / segs;
  for (let i = 0; i < segs; i++) {
    ctx.fillStyle = i % 2 === 0 ? ENC.ink : "#ffffff";
    ctx.fillRect(x0 + i * segW, y0, segW, 5);
    ctx.strokeStyle = ENC.ink;
    ctx.lineWidth = 0.8;
    ctx.strokeRect(x0 + i * segW, y0, segW, 5);
  }
  ctx.fillStyle = ENC.ink;
  ctx.fillText(
    chosen >= 1000 ? `${(chosen / 1000).toLocaleString()} km` : `${chosen} m`,
    x0 + barPx / 2,
    y0 - 2,
  );

  // Nautical-mile scale directly above, as on the reference chart.
  const nmPx = barPx;
  const nm = 1852;
  const nmCount = Math.max(1, Math.round((nmPx * metersPerPx) / nm));
  ctx.textBaseline = "bottom";
  ctx.fillText(`${nmCount.toLocaleString()} NM`, x0 + barPx / 2, y0 - 13);
  ctx.beginPath();
  for (let i = 0; i <= nmCount; i++) {
    const x = x0 + (i / nmCount) * nmPx;
    ctx.moveTo(x, y0 - 11);
    ctx.lineTo(x, y0 - 7);
  }
  ctx.strokeStyle = ENC.ink;
  ctx.lineWidth = 0.8;
  ctx.stroke();
  ctx.restore();
}

/**
 * The cached, purely geographic half of the chart: depth bands, sea-ice tint,
 * restricted areas, contours, coastline and soundings.  None of it depends on
 * anything but the map's pixel origin and zoom, so it can be rendered once and
 * blitted while the user pans.  That is what keeps the chart registered with
 * Leaflet's own (CSS-transformed) overlay and marker panes.
 */
function renderGeo(
  ctx: CanvasRenderingContext2D,
  view: View,
  grid: DepthGrid,
  land: WorldLand | null,
  iceAt: (lat: number, lon: number) => number,
  layers: EncChartLayers,
  props: RenderProps,
): void {
  const bounds = surfaceBounds(view);

  drawBlockRaster(ctx, view, grid, land, iceAt, layers);

  if (layers.restrictedAreas) {
    drawRestrictedAreas(ctx, view, props.seaIce ?? null, iceAt, bounds);
  }
  if (layers.depthContours) {
    drawDepthContours(ctx, view, grid, bounds);
  }
  drawCoastline(ctx, view, grid, bounds);
  if (land) drawWorldCoastline(ctx, view, land, grid, bounds);
  if (layers.depthSoundings) {
    drawSoundings(ctx, view, grid, bounds);
  }
}

/**
 * The per-frame half: graticule, place names, route, marks, icebergs, vessel
 * and scale bar.  These are a few dozen primitives, so they are cheap enough to
 * re-project on every frame.
 */
function renderDecor(
  ctx: CanvasRenderingContext2D,
  view: View,
  centerLat: number,
  layers: EncChartLayers,
  props: RenderProps,
): void {
  const bounds = surfaceBounds(view);

  drawGraticule(ctx, view, bounds);
  drawSeaNames(ctx, view, bounds);

  if (layers.plannedRoute && props.route && props.route.length > 1) {
    drawRoute(ctx, view, props.route);
  }
  if (layers.navigationMarks) {
    for (const mark of props.marks ?? []) drawNavigationMark(ctx, view, mark);
  }
  if (layers.aisTargets && props.icebergs && props.icebergs.length > 0) {
    drawIcebergs(ctx, view, props.icebergs);
  }
  if (layers.aisTargets && props.vessel) {
    drawVessel(ctx, view, props.vessel);
  }
  drawScaleBar(ctx, view, centerLat);
}

/**
 * Geographic bounds covered by a surface, honouring its overscan offset.
 */
function surfaceBounds(view: View): L.LatLngBounds {
  const nw = view.toLatLon(0, 0);
  const se = view.toLatLon(view.w, view.h);
  return L.latLngBounds(L.latLng(se.lat, nw.lon), L.latLng(nw.lat, se.lon));
}

/** How much extra width/height the cached geographic layer is drawn beyond the
 *  viewport, as a fraction of the viewport.  Panning within this margin is a
 *  blit rather than a re-render, which is what keeps the chart in step with the
 *  overlay panes. */
const GEO_OVERSCAN = 0.4;

/** Cached offscreen copy of the chart's geographic layers. */
interface GeoCache {
  canvas: HTMLCanvasElement;
  zoom: number;
  cssW: number;
  cssH: number;
  originX: number;
  originY: number;
  overscanX: number;
  overscanY: number;
  valid: boolean;
}

export function EncdisChartLayer(props: EncdisChartLayerProps): null {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [grid, setGrid] = useState<DepthGrid | null>(null);
  const [land, setLand] = useState<WorldLand | null>(null);
  const [error, setError] = useState<string | null>(null);

  const propsRef = useRef(props);
  propsRef.current = props;

  // Set by the canvas effect: invalidates the cached geographic layer.
  const geoInvalidator = useRef<(() => void) | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadDepthGrid()
      .then((g) => {
        if (!cancelled) setGrid(g);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    // The land mask is optional: without it the chart still renders, it just
    // has no continents outside the surveyed box.
    loadWorldLand()
      .then((m) => {
        if (!cancelled) setLand(m);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!props.active || !grid) return;

    const inspectDepth = (event: L.LeafletMouseEvent) => {
      const { lat, lng } = event.latlng;
      const depth = depthAt(grid, lat, lng);
      const content = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = "ENC chart query";
      const coordinates = document.createElement("div");
      coordinates.textContent = `${lat.toFixed(4)}°, ${lng.toFixed(4)}°`;
      const sounding = document.createElement("div");
      sounding.textContent = !gridCovers(grid, lat, lng)
        ? "Outside bathymetry coverage"
        : depth === -1
          ? "Land"
          : depth > 0
            ? `Depth: ${depth.toLocaleString()} m`
            : "No charted depth";
      content.append(heading, coordinates, sounding);

      L.popup({ maxWidth: 240 })
        .setLatLng(event.latlng)
        .setContent(content)
        .openOn(map);
    };

    map.on("click", inspectDepth);
    return () => {
      map.off("click", inspectDepth);
    };
  }, [grid, map, props.active]);

  useEffect(() => {
    if (!grid) return;

    // The canvas lives in the map *container*, not in a Leaflet pane.  Panes
    // are children of the map pane, which Leaflet translates to follow the
    // view, so a container-sized canvas inside a pane would be dragged around
    // by that transform.  The container itself is not transformed, which makes
    // it the right home for a screen-space chart.
    //
    // z-index 250 keeps it above the tile pane (200) and below the overlay
    // (400) and marker (600) panes, so routes, icebergs and the vessel still
    // draw on top of the chart.
    const host = map.getContainer();
    const canvas = document.createElement("canvas");
    canvas.className = "enc-chart-canvas";
    canvas.style.position = "absolute";
    canvas.style.left = "0";
    canvas.style.top = "0";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "250";
    host.appendChild(canvas);
    canvasRef.current = canvas;

    // Geographic layers are rendered into an oversized offscreen canvas, so a
    // pan is a single blit instead of a full re-render.  Leaflet pans by
    // transform, so without this the chart would lag a frame or more behind the
    // overlay panes and the sea-ice band would appear to slide on its own.
    const geo: GeoCache = {
      canvas: document.createElement("canvas"),
      zoom: Number.NaN,
      cssW: -1,
      cssH: -1,
      originX: Number.NaN,
      originY: Number.NaN,
      overscanX: 0,
      overscanY: 0,
      valid: false,
    };

    const resize = () => {
      const size = map.getSize();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(size.x * dpr));
      canvas.height = Math.max(1, Math.round(size.y * dpr));
      canvas.style.width = `${size.x}px`;
      canvas.style.height = `${size.y}px`;
      geo.valid = false;
    };

    let frame = 0;

    const buildGeo = (size: L.Point, dpr: number) => {
      const overscanX = Math.round(size.x * GEO_OVERSCAN);
      const overscanY = Math.round(size.y * GEO_OVERSCAN);
      const cssW = size.x + 2 * overscanX;
      const cssH = size.y + 2 * overscanY;
      geo.canvas.width = Math.max(1, Math.round(cssW * dpr));
      geo.canvas.height = Math.max(1, Math.round(cssH * dpr));
      const gctx = geo.canvas.getContext("2d");
      if (!gctx) {
        geo.valid = false;
        return;
      }
      const view = makeView(map, cssW, cssH, overscanX, overscanY, grid);
      gctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      gctx.clearRect(0, 0, cssW, cssH);
      const p = propsRef.current;
      renderGeo(gctx, view, grid, land, makeConcentrationSampler(p.seaIce), p.layers, {
        seaIce: p.seaIce,
        route: p.route,
        icebergs: p.icebergs,
        vessel: p.vessel,
        marks: p.marks,
      });
      geo.zoom = view.zoom;
      geo.cssW = cssW;
      geo.cssH = cssH;
      geo.originX = view.originX;
      geo.originY = view.originY;
      geo.overscanX = overscanX;
      geo.overscanY = overscanY;
      geo.valid = true;
    };

    geoInvalidator.current = () => {
      geo.valid = false;
    };

    const draw = () => {
      frame = 0;
      if (!propsRef.current.active) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const p = propsRef.current;
      const size = map.getSize();
      if (size.x < 1 || size.y < 1) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);

      const view = makeView(map, size.x, size.y, 0, 0, grid);
      // Use the same origin the view was built from, so the blit and the decor
      // can never disagree about where the world sits.
      const originX = view.originX;
      const originY = view.originY;
      const stale =
        !geo.valid ||
        geo.zoom !== view.zoom ||
        geo.cssW !== size.x + 2 * geo.overscanX ||
        geo.cssH !== size.y + 2 * geo.overscanY ||
        Math.abs(originX - geo.originX) > geo.overscanX ||
        Math.abs(originY - geo.originY) > geo.overscanY;
      if (stale) buildGeo(size, dpr);

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size.x, size.y);
      if (geo.valid) {
        // The cached surface starts `overscanX/Y` *before* the viewport, so the
        // blit has to shift it back by that margin as well as by the pan.
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(
          geo.canvas,
          geo.originX - originX - geo.overscanX,
          geo.originY - originY - geo.overscanY,
          geo.cssW,
          geo.cssH,
        );
        ctx.imageSmoothingEnabled = true;
      }
      renderDecor(ctx, view, map.getCenter().lat, p.layers, {
        seaIce: p.seaIce,
        route: p.route,
        icebergs: p.icebergs,
        vessel: p.vessel,
        marks: p.marks,
      });
    };

    const schedule = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(draw);
    };

    resize();
    draw();

    map.on("resize", resize);
    map.on("move zoom viewreset moveend zoomend", schedule);

    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      map.off("resize", resize);
      map.off("move zoom viewreset moveend zoomend", schedule);
      canvas.remove();
      canvasRef.current = null;
    };
  }, [grid, land, map]);

  // The chart deliberately does not constrain the map: it paints open ocean
  // wherever the surveyed grid runs out, so the ENC basemap can be panned and
  // zoomed across the whole world exactly like the default tile layer.
  // Dev-only handle so the chart's view can be inspected while tuning the
  // renderer.  Stripped from production builds.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (window as unknown as { __encMap?: L.Map }).__encMap = map;
  }, [map]);

  // React to prop changes (layer toggles, new route, fresh sea ice).
  useEffect(() => {
    if (!grid || !props.active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const iceAt = makeConcentrationSampler(props.seaIce);
    const size = map.getSize();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const view = makeView(map, size.x, size.y, 0, 0, grid);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);
    renderGeo(ctx, view, grid, land, iceAt, props.layers, {
      seaIce: props.seaIce,
      route: props.route,
      icebergs: props.icebergs,
      vessel: props.vessel,
      marks: props.marks,
    });
    renderDecor(ctx, view, map.getCenter().lat, props.layers, {
      seaIce: props.seaIce,
      route: props.route,
      icebergs: props.icebergs,
      vessel: props.vessel,
      marks: props.marks,
    });
    // Any prop change invalidates the cached geographic layer, since the depth
    // and ice fills baked into it may no longer match.
    geoInvalidator.current?.();
  }, [
    grid,
    map,
    props.active,
    props.layers,
    props.seaIce,
    props.route,
    props.icebergs,
    props.vessel,
    props.marks,
  ]);

  // Clear when the base layer is switched away.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (props.active) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }, [props.active]);

  if (error) {
    // Surfaced in the console; the chart simply stays blank.
    // eslint-disable-next-line no-console
    console.error("ENC chart depth grid failed to load:", error);
  }

  return null;
}
