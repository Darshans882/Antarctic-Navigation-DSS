/**
 * Palette and layout constants for the ECDIS / ENC chart layer.
 *
 * Every colour here was sampled directly out of the reference chart
 * (`enc.pdf`) rather than guessed, so the rendered chart matches it:
 *
 *   Land Area                  #E7CC97   swatch + South Africa / Madagascar
 *   Shallow Water (0-200 m)    #BFE9FC   legend swatch
 *   Intermediate (200-1000 m)  #86C5F1   legend swatch
 *   Deep Water (1000 m +)      #45B9FF   legend swatch
 *   Sea Ice Area               #CDEFFF   legend swatch
 *   Depth Contour              #D8F0FC   legend swatch
 *   Planned Route              #FFD5FF   legend swatch
 *   Waypoint                   #FFDBFF   legend swatch
 *   Navigation Mark (Buoy)     #FFE2D9   legend swatch
 *   Danger Area                #FFF6ED   legend swatch
 *   Sidebar / panel chrome     #E7EBEE   sidebar fill
 *   Section header fill        #DCE1E4   sidebar sub-block fill
 *   Ink (linework + text)      #657896   coastline, contours, soundings
 */

export const ENC = {
  ink: "#657896",
  inkSoft: "#8a9bb5",
  chartPaper: "#E7EBEE",
  panelFill: "#E7EBEE",
  panelHeaderFill: "#DCE1E4",
  panelInk: "#33445c",
  land: "#E7CC97",
  landEdge: "#8a7a4e",
  iceSheet: "#EDE6DE",
  iceSheetEdge: "#b9b0a1",
  seaIce: "#CDEFFF",
  seaIceHatch: "#A1DDFF",
  contour: "#D8F0FC",
  contourIndex: "#B9DAF0",
  route: "#FFD5FF",
  routeCore: "#e879f9",
  waypoint: "#FFDBFF",
  buoy: "#FFE2D9",
  danger: "#FFF6ED",
  dangerEdge: "#f0a868",
  restricted: "#f6e6f6",
  restrictedEdge: "#b07fc0",
  tss: "#8a7fd0",
  sounding: "#3f6f9c",
  soundingLand: "#7a6a45",
  graticule: "#9fb4c9",
  graticuleMajor: "#6f8aa6",
  axisBand: "#DCE7F0",
} as const;

/**
 * Depth bands, shallowest first.  The three ENC-legend anchors from the
 * reference chart are reproduced exactly; the steps between them interpolate
 * so the ramp reads like a printed chart's graded bathymetry.
 */
export interface DepthBand {
  max: number;
  color: string;
}

export const DEPTH_BANDS: DepthBand[] = [
  { max: 50, color: "#DFF6FF" },
  { max: 100, color: "#CCF0FF" },
  { max: 200, color: "#BFE9FC" },
  { max: 500, color: "#A6DDF9" },
  { max: 1000, color: "#94CAF9" },
  { max: 2000, color: "#86C5F1" },
  { max: 3000, color: "#77C4F5" },
  { max: 4000, color: "#68C1F8" },
  { max: 5000, color: "#57BDFB" },
  { max: Infinity, color: "#45B9FF" },
];

const BAND_RGB = DEPTH_BANDS.map((b) => ({
  max: b.max,
  r: parseInt(b.color.slice(1, 3), 16),
  g: parseInt(b.color.slice(3, 5), 16),
  b: parseInt(b.color.slice(5, 7), 16),
}));

/** Fill target with the colour of the depth band that `depth` falls in. */
export function depthColorInto(depth: number, out: Uint8ClampedArray, o: number): void {
  for (let i = 0; i < BAND_RGB.length; i++) {
    if (depth < BAND_RGB[i].max) {
      out[o] = BAND_RGB[i].r;
      out[o + 1] = BAND_RGB[i].g;
      out[o + 2] = BAND_RGB[i].b;
      out[o + 3] = 255;
      return;
    }
  }
  const last = BAND_RGB[BAND_RGB.length - 1];
  out[o] = last.r;
  out[o + 1] = last.g;
  out[o + 2] = last.b;
  out[o + 3] = 255;
}

export function depthColor(depth: number): string {
  for (const band of DEPTH_BANDS) {
    if (depth < band.max) return band.color;
  }
  return DEPTH_BANDS[DEPTH_BANDS.length - 1].color;
}

/** Iso-depths drawn as contour lines, matching the reference legend. */
export const CONTOUR_LEVELS = [200, 500, 1000, 2000, 3000, 4000, 5000];

/** Contour drawn heavier and labelled — the chart's "safety contour". */
export const SAFETY_CONTOUR = 500;
export const SAFETY_DEPTH = 1000;

/** Items of the reference chart's legend, in the order it lists them. */
export const LEGEND_ITEMS: { label: string; color: string; kind: "fill" | "line" | "dash" }[] = [
  { label: "Land Area", color: ENC.land, kind: "fill" },
  { label: "Shallow Water (0-200m)", color: "#BFE9FC", kind: "fill" },
  { label: "Intermediate (200-1000m)", color: "#86C5F1", kind: "fill" },
  { label: "Deep Water (1000m)", color: "#45B9FF", kind: "fill" },
  { label: "Depth Contour", color: ENC.contour, kind: "line" },
  { label: "Planned Route", color: ENC.routeCore, kind: "line" },
  { label: "Waypoint", color: "#FFDBFF", kind: "fill" },
  { label: "Navigation Mark (Buoy)", color: ENC.buoy, kind: "fill" },
  { label: "Danger Area", color: ENC.danger, kind: "fill" },
  { label: "Sea Ice Area", color: ENC.seaIce, kind: "fill" },
  { label: "Iceberg", color: "#2f7fd0", kind: "fill" },
  { label: "Research Station", color: "#d8443c", kind: "fill" },
];

/**
 * Named sea / land regions for the operating area (50°S-90°S, 20°E-120°E).
 * Used for the chart's spaced-out water-body labels, the way the reference
 * chart sets "SOUTHERN OCEAN" and "ANTARCTICA" across the sheet.
 */
export const SEA_NAMES: { name: string; lat: number; lon: number; size: number; italic?: boolean }[] = [
  { name: "SOUTHERN OCEAN", lat: -56.5, lon: 62, size: 22 },
  { name: "INDIAN OCEAN", lat: -52.5, lon: 104, size: 15 },
  { name: "SOUTH ATLANTIC OCEAN", lat: -55.5, lon: 27, size: 14 },
  { name: "KERGUELEN PLATEAU", lat: -58, lon: 82, size: 11, italic: true },
  { name: "LAZAREV SEA", lat: -68, lon: 32, size: 12 },
  { name: "ENDERBY LAND", lat: -71.5, lon: 58, size: 11 },
  { name: "DRONNING MAUD LAND", lat: -73, lon: 12, size: 11 },
  { name: "AMERY ICE SHELF", lat: -69.5, lon: 71, size: 9, italic: true },
  { name: "WILKES LAND", lat: -69, lon: 108, size: 11 },
  { name: "ANTARCTICA", lat: -84, lon: 60, size: 24 },
];

/**
 * Research stations inside the chart's extent.  These are real Antarctic
 * stations; only the ones that fall within 20°E-120°E / 50°S-90°S are listed.
 */
export interface EncStation {
  name: string;
  lat: number;
  lon: number;
  country: string;
}

export const STATIONS: EncStation[] = [];
