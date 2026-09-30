import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, forwardRef, useImperativeHandle } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import * as THREE from "three";
import type { IcebergInfo, IcebergTrajectoryResponse } from "../../types";
import { concentrationColor } from "../../utils/colormap";
import { haversineKm } from "../../utils/haversine";
import { useLandMask, buildSeaIcePoints, isLandCell } from "./globeData";
import { GlobeControls } from "./GlobeControls";

export interface GridData {
  lat: number[];
  lon: number[];
  concentration: number[][];
}

interface SeaIcePoint {
  lat: number;
  lng: number;
  concentration: number;
}

interface IcebergPoint {
  id: string;
  lat: number;
  lng: number;
  radius: number;
  altitude: number;
  color: string;
  label: string;
  selected: boolean;
}

interface PathDatum {
  points: [number, number][];
  color: string;
  dash: number;
  stroke: number;
}

const MAX_SEAICE_POINTS = 14000;
const MAX_ICE_POINTS = 12000;

const SELECTED_LAT_MIN = -75;
const SELECTED_LAT_MAX = -55;

const ICE_COLOR = "#0ea5e9";
const ICE_SELECTED = "#ef4444";
const VESSEL_COLOR = "#10b981";

function useSize(el: HTMLDivElement | null): { width: number; height: number } {
  const [size, setSize] = useState({ width: 800, height: 400 });
  useLayoutEffect(() => {
    if (!el) return;
    const update = () =>
      setSize({ width: el.clientWidth || 800, height: el.clientHeight || 400 });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return size;
}

/** Small circle of points at a fixed latitude (used to subtly mark the 55–75°S band). */
function ringPoints(lat: number, n = 72): [number, number][] {
  const pts: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    const lng = (i / n) * 360 - 180;
    pts.push([lat, lng]);
  }
  return pts;
}

/** Mean drift speed (km/h) between consecutive timestamped observations, if derivable. */
function avgDriftKmph(trajectory: IcebergTrajectoryResponse | null | undefined): number | null {
  if (!trajectory) return null;
  const pts = trajectory.observations.map((o) => ({
    lat: o.latitude,
    lng: o.longitude,
    ts: o.timestamp ? Date.parse(o.timestamp) : NaN,
  }));
  let total = 0;
  let cnt = 0;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1];
    const b = pts[i];
    if (!Number.isFinite(a.ts) || !Number.isFinite(b.ts)) continue;
    const dtH = (b.ts - a.ts) / 3600000;
    if (dtH <= 0) continue;
    total += haversineKm(a.lat, a.lng, b.lat, b.lng) / dtH;
    cnt++;
  }
  return cnt ? total / cnt : null;
}

export interface Antarctic3DGlobeProps {
  seaIce?: GridData | null;
  seaIceTimestamp?: string | null;
  seaIceHorizon?: number | null;
  icebergs?: IcebergInfo[];
  selectedIceberg?: string | null;
  trajectory?: IcebergTrajectoryResponse | null;
  vesselPos?: [number, number] | null;
  vesselLabel?: string;
  onIcebergSelect?: (id: string) => void;
  height?: string;
}

export interface GlobeMapRef {
  resize: () => void;
  flyTo: (options: {
    center?: [number, number];
    zoom?: number;
    pitch?: number;
    bearing?: number;
    duration?: number;
    essential?: boolean;
  }) => void;
}

export const Antarctic3DGlobe = forwardRef<GlobeMapRef, Antarctic3DGlobeProps>((props, ref) => {
  const {
    seaIce,
    seaIceTimestamp,
    seaIceHorizon,
    icebergs = [],
    selectedIceberg,
    trajectory,
    vesselPos,
    vesselLabel = "Vessel",
    onIcebergSelect,
    height = "100%",
  } = props;

  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { width, height: pxHeight } = useSize(containerRef.current);

  const maskState = useLandMask();
  const mask = maskState.status === "ready" ? maskState.mask : null;
  const isLand = useCallback(
    (lat: number, lon: number) => (mask ? isLandCell(mask, lat, lon) : false),
    [mask],
  );

  const [webglOk, setWebglOk] = useState(true);
  useEffect(() => {
    try {
      const c = document.createElement("canvas");
      const gl =
        c.getContext("webgl2") || c.getContext("webgl") || c.getContext("experimental-webgl");
      setWebglOk(Boolean(gl));
    } catch {
      setWebglOk(false);
    }
  }, []);

  useImperativeHandle(ref, () => ({
    resize: () => {
      // Globe auto-resizes via useSize, but we can manually trigger if needed
    },
    flyTo: (options) => {
      const g = globeRef.current;
      if (!g) return;

      const camera = g.camera() as THREE.PerspectiveCamera;
      const controls = g.controls() as any;

      camera.fov = 45;
      camera.near = 0.1;
      camera.far = 100;
      camera.updateProjectionMatrix();

      const startPos = camera.position.clone();
      const startTarget = controls.target.clone();

      const { zoom = 2.6, pitch = 30, duration = 1200 } = options;

      // Calculate responsive values
      // Base distance from 0, 2.8, 5.2 is approx 5.9
      // Base zoom is 2.6
      const zoomScale = 2.6 / zoom;

      // Adjust Z (pitch approx) based on pitch ratio from 30
      const pitchScale = pitch / 30;

      const endPos = new THREE.Vector3(0, 2.8 * zoomScale, 5.2 * zoomScale * pitchScale);
      const endTarget = new THREE.Vector3(0, -0.35, 0);

      const startTime = performance.now();
      const animate = (time: number) => {
        const elapsed = time - startTime;
        const t = Math.min(elapsed / duration, 1);

        // easeInOut
        const easeT = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

        camera.position.lerpVectors(startPos, endPos, easeT);
        controls.target.lerpVectors(startTarget, endTarget, easeT);

        if (t < 1) {
          requestAnimationFrame(animate);
        }
      };
      requestAnimationFrame(animate);
    }
  }));

  const seaIcePoints = useMemo<SeaIcePoint[]>(() => {
    if (!seaIce || !seaIce.lat?.length || !seaIce.concentration?.length) return [];
    return buildSeaIcePoints(seaIce, isLand, MAX_SEAICE_POINTS);
  }, [seaIce, isLand]);

  const inBand = useCallback((lat: number) => {
    return lat >= SELECTED_LAT_MIN && lat <= SELECTED_LAT_MAX;
  }, []);

  const icebergPoints = useMemo<IcebergPoint[]>(() => {
    const drift = avgDriftKmph(trajectory);
    const pts = icebergs
      .filter(
        (ib) =>
          !ib.on_land &&
          !isLand(ib.latitude, ib.longitude) &&
          inBand(ib.latitude) &&
          Number.isFinite(ib.latitude) &&
          Number.isFinite(ib.longitude),
      )
      .map((ib): IcebergPoint => {
        const selected = selectedIceberg === ib.iceberg_id;
        const dims =
          ib.length_km != null
            ? `<div>${ib.length_km}${ib.width_km != null ? `×${ib.width_km}` : ""} km</div>`
            : "";
        const timestamp = ib.last_observed
          ? `<div>${new Date(ib.last_observed).toLocaleString()}</div>`
          : "";
        const speed = selected && drift != null ? `<div>Drift ≈ ${drift.toFixed(2)} km/h</div>` : "";
        const demo = ib.demo ? `<div style="color:#b45309">Demo</div>` : "";
        return {
          id: ib.iceberg_id,
          lat: ib.latitude,
          lng: ib.longitude,
          radius: selected ? 1.2 : 0.8,
          altitude: 0.03,
          color: selected ? ICE_SELECTED : ICE_COLOR,
          label: `<div style="font-size:12px;line-height:1.4">
              <strong>${ib.iceberg_id}</strong>
              <div>${ib.latitude.toFixed(3)}, ${ib.longitude.toFixed(3)}</div>
              ${timestamp}${dims}${speed}${demo}
            </div>`,
          selected,
        };
      });
    return pts.slice(0, MAX_ICE_POINTS);
  }, [icebergs, selectedIceberg, inBand, isLand, trajectory]);

  const vesselPoints = useMemo<IcebergPoint[]>(() => {
    if (!vesselPos) return [];
    return [
      {
        id: "vessel",
        lat: vesselPos[0],
        lng: vesselPos[1],
        radius: 1.1,
        altitude: 0.035,
        color: VESSEL_COLOR,
        label: `<div style="font-size:12px;line-height:1.4"><strong>${vesselLabel}</strong><div>${vesselPos[0].toFixed(3)}, ${vesselPos[1].toFixed(3)}</div></div>`,
        selected: false,
      },
    ];
  }, [vesselPos, vesselLabel]);

  const pointData = useMemo(
    () => [...seaIcePoints, ...icebergPoints, ...vesselPoints],
    [seaIcePoints, icebergPoints, vesselPoints],
  );

  const pathData = useMemo<PathDatum[]>(() => {
    const paths: PathDatum[] = [];
    // Subtle rings marking the selected 55–75°S Antarctic band on the sea-ice view
    if (seaIce) {
      paths.push({
        points: ringPoints(SELECTED_LAT_MAX, 96),
        color: "rgba(109,40,217,0.35)",
        dash: 4,
        stroke: 0.5,
      });
      paths.push({
        points: ringPoints(SELECTED_LAT_MIN, 96),
        color: "rgba(109,40,217,0.35)",
        dash: 4,
        stroke: 0.5,
      });
    }
    if (!trajectory) return paths;
    const obs: [number, number][] = trajectory.observations.map((p) => [
      p.latitude,
      p.longitude,
    ]);
    const pred: [number, number][] = trajectory.predictions.map((p) => [
      p.latitude,
      p.longitude,
    ]);
    if (obs.length > 1) {
      paths.push({ points: obs, color: "#0b3d6e", dash: 0, stroke: 2 });
    }
    const connectedPrediction = obs.length > 0 ? [obs[obs.length - 1], ...pred] : pred;
    if (connectedPrediction.length > 1) {
      paths.push({ points: connectedPrediction, color: "#f59e0b", dash: 3, stroke: 1.0 });
    }
    return paths;
  }, [seaIce, trajectory]);

  const onPointClick = useCallback(
    (point: object) => {
      const p = point as SeaIcePoint | IcebergPoint;
      if ("id" in p && p.id !== "vessel" && onIcebergSelect) {
        onIcebergSelect(p.id);
      }
    },
    [onIcebergSelect],
  );

  // --- camera control ---
  // On load: snap to polar top-down, pause 500ms, animate 2s to flat low-angle.
  const introPlayedRef = useRef(false);

  /**
   * animateCam
   *  toPolar=false → intro:  polar top-down  ➜  flat low-angle  (2 s default)
   *  toPolar=true  → reset:  current pos     ➜  flat low-angle  (1 s default)
   *
   * Both end at the FLAT LOW-ANGLE view so the globe never snaps back to polar
   * on reset (reset just means "return to the nice flat view").
   *
   * react-globe.gl scene units: globe radius ≈ 100, Y axis = North Pole direction.
   *
   * POLAR TOP-DOWN (start of intro only):
   *   Camera is placed in FRONT of the globe (positive Z) at equatorial level,
   *   looking at (0, -GLOBE_R, 0) — i.e. the South Pole on the surface.
   *   This gives a circular polar overhead look without flipping OrbitControls.
   *
   * FLAT LOW-ANGLE (permanent end state):
   *   Camera is above the Southern Ocean surface (~55°S) close to the globe,
   *   looking toward the South Pole.  The resulting render is the wide, flat,
   *   horizon-style view the user requested.
   */
  const GLOBE_R = 100;

  // ── POLAR snap position ────────────────────────────────────────────────────
  // Sit at equatorial distance in front (+Z), tilted down toward the south pole.
  // OrbitControls stays happy (camera is never below the globe).
  const POLAR_POS    = new THREE.Vector3(0, GLOBE_R * 0.5, GLOBE_R * 2.8);
  const POLAR_TARGET = new THREE.Vector3(0, -GLOBE_R * 0.8, 0);   // toward S.Pole surface
  const POLAR_FOV    = 38;

  // ── LOW-ANGLE oblique position ─────────────────────────────────────────────
  // Camera at ~55°S latitude, just above the ocean, looking toward pole.
  // elevDeg = elevation BELOW the equatorial plane.
  const elevRad    = (55 * Math.PI) / 180;            // 55° below equator
  const lowDist    = GLOBE_R * 1.75;                  // close to surface
  const LOW_POS    = new THREE.Vector3(
    0,
    -lowDist * Math.sin(elevRad),                     // below equatorial plane
     lowDist * Math.cos(elevRad),                     // in front of globe
  );
  const LOW_TARGET  = new THREE.Vector3(0, -GLOBE_R * 0.95, 0);  // South Pole surface
  const LOW_FOV    = 65;                              // wide cinematic FOV

  const animateCam = useCallback(
    (toPolar: boolean, duration = 2000) => {
      const g = globeRef.current;
      if (!g) return;
      const camera   = g.camera() as THREE.PerspectiveCamera;
      const controls = g.controls() as any;
      if (!camera || !controls) return;

      const startPos    = camera.position.clone();
      const startTarget = controls.target.clone();
      const startFov    = camera.fov;

      // Both "reset" and "intro end" land at the flat low-angle view.
      // toPolar is kept for future use but currently unused (reset = flat too).
      const endPos    = toPolar ? POLAR_POS    : LOW_POS;
      const endTarget = toPolar ? POLAR_TARGET : LOW_TARGET;
      const endFov    = toPolar ? POLAR_FOV    : LOW_FOV;

      const startTime = performance.now();

      // easeInOutCubic
      const ease = (t: number) =>
        t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

      const tick = (now: number) => {
        const raw = Math.min((now - startTime) / duration, 1);
        const e   = ease(raw);

        camera.position.lerpVectors(startPos, endPos, e);
        controls.target.lerpVectors(startTarget, endTarget, e);
        camera.fov = startFov + (endFov - startFov) * e;
        camera.updateProjectionMatrix();
        controls.update();

        if (raw < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const flyToIceberg = useCallback(
    (id: string | null | undefined) => {
      if (!id || !globeRef.current) return;
      const ib = icebergs.find((i) => i.iceberg_id === id);
      if (!ib) return;
      globeRef.current.pointOfView(
        { lat: ib.latitude, lng: ib.longitude, altitude: 1.3 },
        900,
      );
    },
    [icebergs],
  );

  useEffect(() => {
    if (selectedIceberg) flyToIceberg(selectedIceberg);
  }, [selectedIceberg, flyToIceberg]);

  const zoom = useCallback((factor: number) => {
    const g = globeRef.current;
    if (!g) return;
    const camera   = g.camera() as THREE.PerspectiveCamera;
    const controls = g.controls() as any;
    const dir      = camera.position.clone().normalize();
    const newDist  = Math.max(110, camera.position.length() * factor);
    camera.position.copy(dir.multiplyScalar(newDist));
    if (controls) controls.update();
  }, []);

  // Reset → smoothly return to the flat low-angle view (1 s)
  const resetView = useCallback(() => {
    animateCam(false, 1000);
  }, [animateCam]);

  const toggleRotate = useCallback((on: boolean) => {
    const g = globeRef.current;
    if (!g) return;
    const c = g.controls();
    c.autoRotate = on;
    c.autoRotateSpeed = 0.6;
  }, []);

  const pointLatFn = (d: object) => (d as SeaIcePoint | IcebergPoint).lat;
  const pointLngFn = (d: object) => (d as SeaIcePoint | IcebergPoint).lng;
  const pointAltFn = (d: object) => {
    const p = d as SeaIcePoint | IcebergPoint;
    // Sea-ice concentration data lies FLAT on the surface (altitude 0.005 = nearly zero)
    if ("concentration" in p) return 0.005;
    return "altitude" in p ? p.altitude : 0.025;
  };
  const pointColorFn = (d: object) => {
    const p = d as SeaIcePoint | IcebergPoint;
    if ("concentration" in p) return concentrationColor(p.concentration);
    return p.color;
  };
  const pointRadiusFn = (d: object) => {
    const p = d as SeaIcePoint | IcebergPoint;
    if ("concentration" in p) return 0.3;
    return p.radius;
  };
  const pointLabelFn = (d: object) => {
    const p = d as SeaIcePoint | IcebergPoint;
    if ("concentration" in p) {
      const ts = seaIceTimestamp ? new Date(seaIceTimestamp).toLocaleString() : "—";
      const horizon = seaIceHorizon != null ? `${seaIceHorizon}h` : "—";
      return `<div style="font-size:11px;line-height:1.4">
          <div>Lat ${p.lat.toFixed(2)}° · Lon ${p.lng.toFixed(2)}°</div>
          <div style="font-weight:600">${(p.concentration * 100).toFixed(1)}% concentration</div>
          <div>${ts}</div>
          <div>Horizon ${horizon}</div>
        </div>`;
    }
    return p.label;
  };
  const pathPointsFn = (d: object) => (d as PathDatum).points;
  const pathColorFn = (d: object) => (d as PathDatum).color;
  const pathStrokeFn = (d: object) => (d as PathDatum).stroke;
  const pathDashLengthFn = (d: object) => (d as PathDatum).dash;
  const pathDashGapFn = (d: object) => ((d as PathDatum).dash > 0 ? 1.5 : 0);

  if (!webglOk) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-slate-200 bg-white text-xs text-navy-500"
        style={{ height }}>
        WebGL is required to render the 3D globe but is unavailable in this browser.
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-slate-200" style={{ height }}>
      <div ref={containerRef} className="h-full w-full">
        {pointData.length > 0 ? (
          <Globe
            ref={globeRef}
            width={width}
            height={pxHeight}
            backgroundColor="rgba(255,255,255,0)"
            globeImageUrl={`${import.meta.env.BASE_URL ?? ""}data/world-map.png`}
            atmosphereColor="#a7d7f5"
            atmosphereAltitude={0.12}
            onGlobeReady={() => {
              // INTRO ANIMATION — runs once per component lifetime.
              // Guard prevents re-firing on HMR / React StrictMode double-invoke.
              if (introPlayedRef.current) return;
              introPlayedRef.current = true;

              const g = globeRef.current;
              if (!g) return;
              const camera   = g.camera() as THREE.PerspectiveCamera;
              const controls = g.controls() as any;
              if (!camera || !controls) return;

              // ── Step 1: snap instantly to the polar top-down view ─────────
              camera.fov = POLAR_FOV;
              camera.updateProjectionMatrix();
              camera.position.copy(POLAR_POS);
              controls.target.copy(POLAR_TARGET);
              controls.update();

              // ── Step 2: after 500 ms pause, animate to the flat low-angle ─
              setTimeout(() => animateCam(false, 2000), 500);
            }}
            pointsData={pointData}
            pointLat={pointLatFn}
            pointLng={pointLngFn}
            pointAltitude={pointAltFn}
            pointColor={pointColorFn}
            pointRadius={pointRadiusFn}
            pointLabel={pointLabelFn}
            onPointClick={onPointClick}
            pathsData={pathData}
            pathPoints={pathPointsFn}
            pathColor={pathColorFn}
            pathStroke={pathStrokeFn}
            pathDashLength={pathDashLengthFn}
            pathDashGap={pathDashGapFn}
            pathPointAlt={0.04}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-navy-400">
            No data to display
          </div>
        )}
      </div>

      <GlobeControls
        onZoomIn={() => zoom(0.6)}
        onZoomOut={() => zoom(1.7)}
        onReset={resetView}
        onToggleRotate={toggleRotate}
      />

      {mask && (
        <div className="absolute bottom-2 right-2 z-[600] rounded bg-white/85 px-2 py-1 text-[10px] text-navy-500 shadow-card border border-slate-200">
          Ocean-only · land-mask verified
        </div>
      )}
      {maskState.status === "error" && (
        <div className="absolute bottom-2 left-2 z-[600] rounded bg-white/95 px-2 py-1 text-[10px] text-amber-700 shadow-card border border-amber-200 max-w-[260px]">
          Land mask unavailable — ocean-only rendering cannot be verified.
        </div>
      )}
      {!mask && maskState.status !== "error" && (
        <div className="absolute bottom-2 left-2 z-[600] rounded bg-white/85 px-2 py-1 text-[10px] text-navy-400 shadow-card border border-slate-200">
          Loading land mask…
        </div>
      )}
    </div>
  );
});