import { ENC, LEGEND_ITEMS, SAFETY_CONTOUR, SAFETY_DEPTH } from "./palette";
import type { EncChartLayers } from "./EncdisChartLayer";

/**
 * ECDIS side panel, modelled on the reference chart's right-hand column:
 * Position (GPS), Chart Information, Display, Layers and Legend.
 *
 * Values that the project actually knows (position, course, speed, heading,
 * scale) are read from live state; the chart's metadata (S-57 cell, datum,
 * projection, safety contour/depth, palette) is static chart configuration.
 */

export interface EcdisVesselInfo {
  lat: number;
  lon: number;
  label: string;
  cog: number;
  sog: number;
  hdg: number;
}

interface EcdisSidebarProps {
  active: boolean;
  vessel: EcdisVesselInfo | null;
  zoom: number;
  centerLat: number;
  layers: EncChartLayers;
  onToggleLayer: (key: keyof EncChartLayers) => void;
  encName: string;
}

const LAYER_TOGGLES: { key: keyof EncChartLayers; label: string }[] = [
  { key: "depthContours", label: "Depth Contours" },
  { key: "depthSoundings", label: "Depth Soundings" },
  { key: "seaIceArea", label: "Sea Ice Area" },
  { key: "seaIceOverlay", label: "Sea Ice Overlay" },
  { key: "restrictedAreas", label: "Restricted Areas" },
  { key: "plannedRoute", label: "Planned Route" },
  { key: "navigationMarks", label: "Navigation Marks" },
  { key: "aisTargets", label: "AIS Targets" },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-slate-300/70 last:border-b-0">
      <h3
        className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-slate-600"
        style={{ background: ENC.panelHeaderFill }}
      >
        {title}
      </h3>
      <div className="px-2.5 py-1.5 space-y-0.5">{children}</div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] text-slate-500">{label}</span>
      <span className="text-[10px] font-semibold tabular-nums text-slate-700">{value}</span>
    </div>
  );
}

function formatLat(value: number): string {
  const deg = Math.floor(Math.abs(value));
  const min = (Math.abs(value) - deg) * 60;
  return `${deg}°${min.toFixed(3).padStart(6, "0")}'${value >= 0 ? "N" : "S"}`;
}

function formatLon(value: number): string {
  const deg = Math.floor(Math.abs(value));
  const min = (Math.abs(value) - deg) * 60;
  return `${deg}°${min.toFixed(3).padStart(6, "0")}'${value >= 0 ? "E" : "W"}`;
}

/** Degrees, or a dash when the value is unavailable. */
function formatDeg(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(1)}°` : "—";
}

/** Speed over ground in knots, or a dash when the value is unavailable. */
function formatSpeed(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(1)} kn` : "—";
}

/** Chart scale denominator for the current view, in the usual 1:x form. */
function scaleDenominator(zoom: number, centerLat: number): number {
  const metersPerPx = (156543.03392804097 * Math.cos((centerLat * Math.PI) / 180)) / Math.pow(2, zoom);
  const denominator = metersPerPx * (96 / 0.0254);
  if (denominator >= 1e6) {
    return Math.round(denominator / 1e6) * 1e6;
  }
  if (denominator >= 1e3) {
    return Math.round(denominator / 1e3) * 1e3;
  }
  return Math.round(denominator);
}

export function EcdisSidebar({
  active,
  vessel,
  zoom,
  centerLat,
  layers,
  onToggleLayer,
  encName,
}: EcdisSidebarProps): JSX.Element | null {
  if (!active) return null;

  const scale = scaleDenominator(zoom, centerLat);

  return (
    <aside
      className="ecdis-sidebar absolute right-0 top-0 bottom-0 z-[700] w-[212px] overflow-y-auto border-l border-slate-300 text-slate-700 shadow-lg"
      style={{ background: ENC.panelFill }}
      aria-label="ECDIS chart information"
    >
      <header
        className="px-2.5 py-1.5 text-[12px] font-bold uppercase tracking-[0.22em] text-slate-700"
        style={{ background: ENC.panelHeaderFill }}
      >
        ECDIS
      </header>

      <Section title="Position (GPS)">
        {vessel ? (
          <>
            <Row label="Lat" value={formatLat(vessel.lat)} />
            <Row label="Lon" value={formatLon(vessel.lon)} />
            <Row label="COG" value={formatDeg(vessel.cog)} />
            <Row label="SOG" value={formatSpeed(vessel.sog)} />
            <Row label="HDG" value={formatDeg(vessel.hdg)} />
            <p className="pt-0.5 text-[9px] font-semibold text-slate-600">{vessel.label}</p>
          </>
        ) : (
          <p className="text-[9px] text-slate-500">No vessel position</p>
        )}
      </Section>

      <Section title="Chart Information">
        <Row label="ENC" value={encName} />
        <Row label="Scale" value={`1:${scale.toLocaleString("en-US")}`} />
        <Row label="Datum" value="WGS-84" />
        <Row label="Projection" value="Mercator" />
      </Section>

      <Section title="Display">
        <Row label="Palette" value="Day" />
        <Row label="Depth Unit" value="Metres" />
        <Row label="Safety Contour" value={String(SAFETY_CONTOUR)} />
        <Row label="Safety Depth" value={String(SAFETY_DEPTH)} />
      </Section>

      <Section title="Layers">
        {LAYER_TOGGLES.map(({ key, label }) => (
          <label
            key={key}
            className="flex cursor-pointer items-center gap-1.5 py-[1px] text-[10px] text-slate-600 hover:text-slate-900"
          >
            <input
              type="checkbox"
              checked={layers[key]}
              onChange={() => onToggleLayer(key)}
              className="h-2.5 w-2.5 accent-sky-600"
            />
            <span>{label}</span>
          </label>
        ))}
      </Section>

      <Section title="Legend">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5 py-[1px]">
            <span
              className="inline-block h-2.5 w-3.5 shrink-0 rounded-[1px] border"
              style={
                item.kind === "fill"
                  ? { background: item.color, borderColor: "#9aa7b5" }
                  : { background: "transparent", borderColor: item.color, borderTopWidth: 2 }
              }
            />
            <span className="truncate text-[9px] text-slate-600">{item.label}</span>
          </div>
        ))}
      </Section>
    </aside>
  );
}
