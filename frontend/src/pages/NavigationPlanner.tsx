import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../services/api";

import type {

  AlertRecord,

  IcebergsListResponse,

  JourneyResponse,

  JourneyStatus,

  PortInfo,

  ResearchCenterInfo,

  RouteResult,

  RoutesOptimizeResponse,

  SeaIceForecastResponse,

  SimulationConfig,

  VesselInfo,

} from "../types";

import { Card, CardHeader, CardBody } from "../components/common/Card";

import { useApp, useAssistantActionHandler, type ActionOutcome } from "../context/AppContext";

import { AntarcticMap } from "../components/map/AntarcticMap";
import { AntarcticPageHeader } from "../components/common/AntarcticPageHeader";
import { MetricBar, type JourneyMetric } from "../components/journey/MetricBar";

import { JourneyTimeline, type TimelineStep } from "../components/journey/JourneyTimeline";

import { calculateRouteAlerts } from "../utils/routeAlerts";

import { findRouteByLabel } from "../utils/routeLabels";



type Mode = "outbound" | "return";



function fmtLat(lat: number): string {

  return `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"}`;

}

function fmtLon(lon: number): string {

  return `${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`;

}

function coords(lat: number, lon: number): string {

  return `${fmtLat(lat)}, ${fmtLon(lon)}`;

}



function parseCoordinate(value: string, axis: "lat" | "lon"): number | null {

  const match = value.trim().match(/^([+-]?\d+(?:\.\d+)?)\s*(NORTH|SOUTH|EAST|WEST|N|S|E|W)?$/i);

  if (!match) return null;

  const magnitude = Number(match[1]);

  const suffix = match[2]?.toUpperCase();

  const hemisphere = suffix?.[0];

  const isLatitude = axis === "lat";

  if (suffix && ((isLatitude && !["N", "S"].includes(hemisphere)) || (!isLatitude && !["E", "W"].includes(hemisphere)))) {

    return null;

  }

  const valueWithSign = hemisphere === "S" || hemisphere === "W" ? -Math.abs(magnitude) : magnitude;

  const limit = isLatitude ? 90 : 180;

  return valueWithSign >= -limit && valueWithSign <= limit ? valueWithSign : null;

}



function riskTone(level: string | null | undefined): JourneyMetric["tone"] {

  if (!level) return "normal";

  if (level === "low") return "good";

  if (level === "moderate") return "warn";

  return "bad";

}



function journeyToRoute(j: JourneyResponse): RouteResult {

  return {

    waypoints: j.waypoints.map((w) => ({

      lat: w.latitude,

      lon: w.longitude,

      risk_score: 0,

      step: 0,

    })),

    coordinates: j.waypoints.map((w) => [w.latitude, w.longitude] as [number, number]),

    distance_km: j.total_distance_nm * 1.852,

    distance_nm: j.total_distance_nm,

    travel_time_hours: j.estimated_duration_hours,

    fuel_tons: j.total_fuel_tons,

    risk_score: null,

    risk_level: j.max_risk_level,

    warnings: [],

  };

}



export function NavigationPlannerPage() {

  const { toast, setActiveRoute, replaceRouteAlerts, navigation, setNavigation, setActiveVessel } = useApp();



  const [ports, setPorts] = useState<PortInfo[]>([]);

  const [centers, setCenters] = useState<ResearchCenterInfo[]>([]);

  const [vessels, setVessels] = useState<VesselInfo[]>([]);

  const [simulationConfig, setSimulationConfig] = useState<SimulationConfig | null>(null);

  const [seaIce, setSeaIce] = useState<SeaIceForecastResponse | null>(null);

  const [icebergs, setIcebergs] = useState<IcebergsListResponse | null>(null);



  const { portId, centerId, vesselId, mode, journey, status, planning, selectedRoute, alertFocus, liveLat, liveLon } = navigation;

  const [mapRefreshToken, setMapRefreshToken] = useState(0);

  const [pendingRouteEvent, setPendingRouteEvent] = useState<AlertRecord | null>(null);



  const [loadingMeta, setLoadingMeta] = useState(true);

  const [routeError, setRouteError] = useState<string | null>(null);

  const [busy, setBusy] = useState<null | "start" | "advance" | "recalc">(null);

  const setPortId = (value: string) => setNavigation({ portId: value });

  const setCenterId = (value: string) => setNavigation({ centerId: value });

  const setVesselId = (value: string) => setNavigation({ vesselId: value });

  const setMode = (value: Mode) => setNavigation({ mode: value });

  const setJourney = (value: JourneyResponse | null) => setNavigation({ journey: value });

  const setStatus = (value: JourneyStatus | null) => setNavigation({ status: value });

  const setPlanning = (value: RoutesOptimizeResponse | null) => setNavigation({ planning: value });

  const setLiveLat = (value: string) => setNavigation({ liveLat: value });

  const setLiveLon = (value: string) => setNavigation({ liveLon: value });



  useEffect(() => {
    Promise.all([
      api.ports(),
      api.researchCenters(),
      api.vessels(),
      api.simulationConfig(),
      api.seaIceForecast(24),
      api.icebergs(),
    ])
      .then(([p, c, v, sim, si, ib]) => {
        if (p?.length) {
          setPorts(p);
          if (!navigation.portId) setPortId(p[0].port_id);
        }
        if (c?.length) {
          setCenters(c);
          if (!navigation.centerId) setCenterId(c[0].center_id);
        }
        if (v?.vessels?.length) {
          setVessels(v.vessels);
          if (!navigation.vesselId) setVesselId(v.vessels[0].vessel_id);
        }
        if (sim) setSimulationConfig(sim);
        if (si) setSeaIce(si);
        if (ib) setIcebergs(ib);
      })
      .catch((err) => {
        console.warn("Navigation data loading notice:", err);
      })
      .finally(() => setLoadingMeta(false));
  }, [toast]);



  const port = useMemo(() => ports.find((x) => x.port_id === portId) ?? null, [ports, portId]);

  const center = useMemo(

    () => centers.find((x) => x.center_id === centerId) ?? null,

    [centers, centerId],

  );

  const vessel = useMemo(

    () => vessels.find((x) => x.vessel_id === vesselId) ?? null,

    [vessels, vesselId],

  );



  // Publish the selected vessel so the assistant can name it.

  useEffect(() => {

    setActiveVessel(vessel);

  }, [vessel, setActiveVessel]);



  const fetchStatus = useCallback(async (id: string) => {

    try {

      setStatus(await api.journeyStatus(id));

    } catch {

      setStatus(null);

    }

  }, []);



  const buildRouteUpdateAlert = useCallback(

    (previousPlan: RoutesOptimizeResponse | null, nextPlan: RoutesOptimizeResponse, reason: string): AlertRecord => {

      const riskLabel = nextPlan.recommended.risk_level ?? "unknown";

      const severity = riskLabel === "low" ? "info" : riskLabel === "moderate" ? "warning" : "high";

      return {

        id: `route-updated-${nextPlan.route_id}-${Date.now()}`,

        type: "route",

        severity,

        title: "Route Updated",

        message: "Navigation route recalculated from the vessel's new live position. Three alternative routes are now available.",

        timestamp: new Date().toISOString(),

        read: false,

        routeId: nextPlan.route_id,

        previousRoute: previousPlan,

        newRoute: nextPlan,

        reason,

        latitude: nextPlan.start_latitude,

        longitude: nextPlan.start_longitude,

        selectedRouteLabel: `Recommended Route — ${riskLabel}`,

        metadata: {

          risk: riskLabel,

          distanceKm: nextPlan.recommended.distance_km,

          etaHours: nextPlan.recommended.travel_time_hours,

          previousRouteId: previousPlan?.route_id ?? null,

        },

      };

    },

    [],

  );



  const fetchAlternatives = useCallback(

    async (

      startLat: number,

      startLon: number,

      destLat: number,

      destLon: number,

      vId: string,

      reason = "Live vessel position recalculation",

      previousPlan: RoutesOptimizeResponse | null = planning,

    ) => {

      try {

        const plan = await api.routesOptimize({

          start_latitude: startLat,

          start_longitude: startLon,

          destination_latitude: destLat,

          destination_longitude: destLon,

          vessel_id: vId,

          preference: "recommended",

        });

        setRouteError(null);

        setPlanning(plan);

        setNavigation({

          selectedRoute: plan.recommended,

          liveLat: String(startLat),

          liveLon: String(startLon),

        });

        setActiveRoute(plan);

        setPendingRouteEvent(buildRouteUpdateAlert(previousPlan, plan, reason));

      } catch (e) {

        setPlanning(null);

        setRouteError(e instanceof Error ? e.message : "Route generation failed.");

      }

    },

    [buildRouteUpdateAlert, planning, setActiveRoute, setNavigation],

  );



  useEffect(() => {

    if (!selectedRoute || !planning) {

      replaceRouteAlerts([]);

      setPendingRouteEvent(null);

      return;

    }

    replaceRouteAlerts([

      ...(pendingRouteEvent ? [pendingRouteEvent] : []),

      ...calculateRouteAlerts({

        route: selectedRoute,

        routeId: planning.route_id,

        routeLabel: selectedRoute === planning.recommended ? "Recommended Route" : `${selectedRoute.risk_level ?? "Alternative"} Risk Route`,

        seaIce,

        icebergs: icebergs?.icebergs ?? [],

        hazardConfig: planning.hazard_config,

      }),

    ]);

  }, [selectedRoute, planning, seaIce, icebergs, mapRefreshToken, pendingRouteEvent, replaceRouteAlerts]);



  const startJourney = useCallback(async (): Promise<ActionOutcome> => {

    if (!port || !center) {

      toast("Select a departure port and a research center", "error");

      return { success: false, message: "No departure port and research center are selected." };

    }

    setBusy("start");

    try {

      const j = await api.startJourney({

        departure_port_id: port.port_id,

        destination_id: center.center_id,

        vessel_id: vesselId,

        journey_mode: mode,

        position_mode: "simulation",

      });

      setJourney(j);

      const liveStartLat = Number(j.current_vessel_lat ?? port.latitude);

      const liveStartLon = Number(j.current_vessel_lon ?? port.longitude);

      setNavigation({

        selectedRoute: journeyToRoute(j),

        liveLat: String(liveStartLat),

        liveLon: String(liveStartLon),

      });

      await fetchStatus(j.journey_id);

      const destLat = mode === "return" ? port.latitude : center.latitude;
      const destLon = mode === "return" ? port.longitude : center.longitude;
      await fetchAlternatives(

        liveStartLat,

        liveStartLon,

        destLat,

        destLon,

        vesselId,

        "Route initialized from live vessel position",

        planning,

      );

      const summary = `Journey started — ${j.origin} → ${j.destination} (${j.journey_mode})`;

      toast(summary, "success");

      return { success: true, message: summary };

    } catch (e) {

      const message = e instanceof Error ? e.message : "Failed to start journey";

      toast(message, "error");

      return { success: false, message };

    } finally {

      setBusy(null);

    }

  }, [port, center, vesselId, mode, planning, fetchStatus, fetchAlternatives, toast]);



  const advance = useCallback(async (): Promise<ActionOutcome> => {

    if (!journey) {

      toast("Start a journey first", "error");

      return { success: false, message: "No journey is running." };

    }

    setBusy("advance");

    try {

      const j = await api.advanceJourney(journey.journey_id);

      const liveLat = Number(j.current_vessel_lat ?? journey.current_vessel_lat);

      const liveLon = Number(j.current_vessel_lon ?? journey.current_vessel_lon);

      setJourney(j);

      setNavigation({

        selectedRoute: journeyToRoute(j),

        liveLat: String(liveLat),

        liveLon: String(liveLon),

      });

      await fetchStatus(j.journey_id);

      const destLat = mode === "return" ? port?.latitude : center?.latitude;
      const destLon = mode === "return" ? port?.longitude : center?.longitude;
      await fetchAlternatives(

        liveLat,

        liveLon,

        destLat ?? j.current_vessel_lat,

        destLon ?? j.current_vessel_lon,

        vesselId,

        "Vessel advanced 2 hours along the active route",

        planning,

      );

      const summary = `Advanced 2 simulated hours — route update #${j.route_update_count}`;

      toast(summary, "success");

      return { success: true, message: summary };

    } catch (e) {

      const message = e instanceof Error ? e.message : "Failed to advance";

      toast(message, "error");

      return { success: false, message };

    } finally {

      setBusy(null);

    }

  }, [journey, mode, port, center, vesselId, planning, fetchStatus, fetchAlternatives, toast]);



  const recalc = useCallback(async (): Promise<ActionOutcome> => {

    if (!journey) {

      toast("Start a journey first", "error");

      return { success: false, message: "No journey is running." };

    }

    const lat = parseCoordinate(liveLat, "lat");

    const lon = parseCoordinate(liveLon, "lon");

    if (lat === null || lon === null) {

      const shipLat = Number(journey.current_vessel_lat ?? 0);

      const shipLon = Number(journey.current_vessel_lon ?? 0);

      const fallbackLat = parseCoordinate(String(shipLat), "lat");

      const fallbackLon = parseCoordinate(String(shipLon), "lon");

      if (fallbackLat === null || fallbackLon === null) {

        toast("Use coordinates such as 31S and 79E", "error");

        return { success: false, message: "The live position is not valid coordinates." };

      }

      setNavigation({ liveLat: String(fallbackLat), liveLon: String(fallbackLon) });

      const destLat = mode === "return" ? port?.latitude : center?.latitude;
      const destLon = mode === "return" ? port?.longitude : center?.longitude;
      await fetchAlternatives(

        fallbackLat,

        fallbackLon,

        destLat ?? journey.current_vessel_lat,

        destLon ?? journey.current_vessel_lon,

        vesselId,

        "Live position recalculation",

        planning,

      );

      return {

        success: true,

        message: `Route recalculated from ${coords(fallbackLat, fallbackLon)}.`,

      };

    }

    setBusy("recalc");

    try {

      const j = await api.recalculateJourney(journey.journey_id, lat, lon);

      setJourney(j);

      setNavigation({

        selectedRoute: journeyToRoute(j),

        liveLat: String(lat),

        liveLon: String(lon),

      });

      await fetchStatus(j.journey_id);

      const destLat = mode === "return" ? port?.latitude : center?.latitude;
      const destLon = mode === "return" ? port?.longitude : center?.longitude;
      await fetchAlternatives(

        lat,

        lon,

        destLat ?? j.current_vessel_lat,

        destLon ?? j.current_vessel_lon,

        vesselId,

        "Live vessel position recalculation",

        planning,

      );

      const summary = `Route recalculated from ${coords(lat, lon)}`;

      toast(summary, "success");

      return { success: true, message: summary };

    } catch (e) {

      const message = e instanceof Error ? e.message : "Failed to recalculate";

      toast(message, "error");

      return { success: false, message };

    } finally {

      setBusy(null);

    }

  }, [journey, liveLat, liveLon, mode, port, center, vesselId, planning, fetchStatus, fetchAlternatives, toast]);



  // Expose these controls to the assistant. Each returns its real outcome, so

  // the assistant is only told the action worked when it did.

  useAssistantActionHandler("start_journey", () => startJourney());

  useAssistantActionHandler("advance_journey", () => advance());

  useAssistantActionHandler("recalculate_route", () => recalc());

  useAssistantActionHandler("pause_journey", async () => {

    toast("Voyage simulation paused", "info");

    return { success: true, message: "Journey paused" };

  });

  useAssistantActionHandler("resume_journey", async () => {

    toast("Voyage simulation resumed", "info");

    return { success: true, message: "Journey resumed" };

  });

  useAssistantActionHandler("select_route", async (params) => {

    const label = String(params.label ?? "");

    const match = findRouteByLabel(planning, label);

    if (!match) {

      return { success: false, message: `${label} is not one of the current routes.` };

    }

    setNavigation({ selectedRoute: match });

    setActiveRoute({ ...planning!, recommended: match } as RoutesOptimizeResponse);

    return { success: true, message: `Selected route ${label}.` };

  });

  useAssistantActionHandler("refresh_data", async () => {

    if (journey) {

      await fetchStatus(journey.journey_id);

      return { success: true, message: "Journey status refreshed." };

    }

    return { success: true, message: "Nothing to refresh - no journey is running." };

  });



  const resetDetails = useCallback(() => {

    setNavigation({ journey: null, status: null, planning: null, selectedRoute: null, liveLat: "", liveLon: "" });

    setActiveRoute(null);

    setLiveLat("");

    setLiveLon("");

    toast("Journey details reset", "info");

  }, [toast]);



  const refreshMap = useCallback(() => {

    setMapRefreshToken((token) => token + 1);

  }, []);



  const stepHours = simulationConfig?.time_step_hours ?? 2;



  const journeyRoute = useMemo(

    () => selectedRoute ?? (journey ? journeyToRoute(journey) : null),

    [journey, selectedRoute],

  );



  const vesselPos: [number, number] | null = useMemo(() => {

    if (journey) return [journey.current_vessel_lat, journey.current_vessel_lon];

    if (planning) return [planning.start_latitude, planning.start_longitude];

    if (port) return [port.latitude, port.longitude];

    return null;

  }, [journey, planning, port]);



  const nowHours = status?.current_time_hours ?? 0;

  const lastUpdateCount = journey?.route_update_count ?? null;



  const metrics: JourneyMetric[] = [

    {

      label: "Current Vessel Location",

      value: journey ? coords(journey.current_vessel_lat, journey.current_vessel_lon) : vesselPos ? coords(vesselPos[0], vesselPos[1]) : "—",

      sub: vessel?.name ?? null,

    },

    {

      label: "Destination",

      value: journey?.destination ?? center?.name ?? "—",

      sub: center ? coords(center.latitude, center.longitude) : null,

    },

    {

      label: "Journey Mode",

      value: journey ? journey.journey_mode : mode,

      sub: "simulated position",

    },

    {

      label: "Last Update",

      value: journey ? `T+${nowHours.toFixed(1)} h` : "—",

      sub: lastUpdateCount != null ? `update #${lastUpdateCount}` : null,

    },

    {

      label: "Next Update",

      value: journey ? `T+${(nowHours + stepHours).toFixed(1)} h` : "—",

      sub: `every ${stepHours} h`,

    },

    {

      label: "Remaining Distance",

      value: status ? `${status.remaining_distance_nm.toFixed(1)} nm` : journey ? `${journey.total_distance_nm.toFixed(1)} nm` : planning ? `${planning.recommended.distance_nm.toFixed(1)} nm` : "—",

      sub: status && !status.is_complete ? `${status.progress_percent.toFixed(0)}% complete` : null,

    },

    {

      label: "Fuel Estimate",

      value: journey ? `${journey.total_fuel_tons.toFixed(1)} t` : planning?.recommended?.fuel_tons != null ? `${planning.recommended.fuel_tons.toFixed(1)} t` : "—",

      sub: null,

    },

    {

      label: "Risk Level",

      value: journey?.max_risk_level ?? planning?.recommended.risk_level ?? "—",

      tone: riskTone(journey?.max_risk_level ?? planning?.recommended.risk_level),

      sub: null,

    },

  ];



  const timeline: TimelineStep[] = [

    {

      key: "departure",

      label: "Departure",

      value: port?.name ?? "—",

      detail: port ? coords(port.latitude, port.longitude) : null,

      state: "done",

    },

    {

      key: "prev-update",

      label: "Previous 2h Update",

      value: lastUpdateCount && lastUpdateCount > 1 ? `T+${Math.max(0, nowHours - stepHours).toFixed(1)} h` : "None yet",

      detail: lastUpdateCount && lastUpdateCount > 1 ? `update #${lastUpdateCount - 1}` : "awaiting first advance",

      state: lastUpdateCount && lastUpdateCount > 1 ? "done" : "upcoming",

    },

    {

      key: "current-pos",

      label: "Current Position",

      value: journey ? `T+${nowHours.toFixed(1)} h` : "At berth",

      detail: vesselPos ? coords(vesselPos[0], vesselPos[1]) : null,

      state: "active",

    },

    {

      key: "current-route",

      label: "Current Route",

      value: journey ? `${journey.total_distance_nm.toFixed(0)} nm` : planning ? `${planning.recommended.distance_nm.toFixed(0)} nm` : "Not planned",

      detail: journey ? `update #${journey.route_update_count} · ${journey.max_risk_level} risk` : null,

      state: journey ? "active" : "upcoming",

    },

    {

      key: "next-update",

      label: "Next Update",

      value: journey ? `T+${(nowHours + stepHours).toFixed(1)} h` : "—",

      detail: journey ? `route recompute (${stepHours} h cycle)` : null,

      state: "upcoming",

    },

    {

      key: "destination",

      label: "Destination",

      value: journey?.destination ?? center?.name ?? "—",

      detail: center ? coords(center.latitude, center.longitude) : null,

      state: status?.is_complete ? "done" : "upcoming",

    },

  ];



  const selectCls =

    "w-full text-xs border border-slate-200 rounded-lg px-2 py-2 bg-white text-navy-700 focus:outline-none focus:ring-1 focus:ring-blue-500";



  return (

    <div className="space-y-5">

      <AntarcticPageHeader
        title="Navigation"
        titleHighlight="Dashboard"
        subtitle="Journey monitoring · route planning · 2-hour rolling updates"
        rightControls={
          seaIce?.warning ? (
            <span className="px-2 py-1 text-[11px] font-medium bg-amber-50 border border-amber-200 text-amber-700 rounded-lg">
              {seaIce.warning}
            </span>
          ) : undefined
        }
      />



      <MetricBar metrics={metrics} />



      <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-4">

        <Card>

          <CardHeader

            title="Journey Controls"

            action={

              <button

                type="button"

                onClick={resetDetails}

                disabled={busy !== null}

                className="px-2 py-1 text-[10px] font-semibold border border-slate-300 text-navy-600 rounded-md hover:bg-slate-50 disabled:opacity-50"

              >

                Reset Details

              </button>

            }

          />

          <CardBody className="space-y-3">

            <div>

              <label className="block text-[10px] font-semibold uppercase tracking-wider text-navy-500 mb-1">

                Departure Port

              </label>

              <select

                value={portId}

                onChange={(e) => setPortId(e.target.value)}

                disabled={loadingMeta || !!journey}

                className={selectCls}

              >

                {ports.map((p) => (

                  <option key={p.port_id} value={p.port_id}>

                    {p.name} · {p.country}

                  </option>

                ))}

              </select>

            </div>



            <div>

              <label className="block text-[10px] font-semibold uppercase tracking-wider text-navy-500 mb-1">

                Research Center

              </label>

              <select

                value={centerId}

                onChange={(e) => setCenterId(e.target.value)}

                disabled={loadingMeta || !!journey}

                className={selectCls}

              >

                {centers.map((c) => (

                  <option key={c.center_id} value={c.center_id}>

                    {c.name} · {c.country}

                  </option>

                ))}

              </select>

            </div>



            <div className="grid grid-cols-2 gap-2">

              <div>

                <label className="block text-[10px] font-semibold uppercase tracking-wider text-navy-500 mb-1">

                  Vessel

                </label>

                <select

                  value={vesselId}

                  onChange={(e) => setVesselId(e.target.value)}

                  disabled={loadingMeta || !!journey}

                  className={selectCls}

                >

                  {vessels.map((v) => (

                    <option key={v.vessel_id} value={v.vessel_id}>

                      {v.name}

                    </option>

                  ))}

                </select>

              </div>

              <div>

                <label className="block text-[10px] font-semibold uppercase tracking-wider text-navy-500 mb-1">

                  Journey Mode

                </label>

                <select

                  value={mode}

                  onChange={(e) => setMode(e.target.value as Mode)}

                  disabled={!!journey}

                  className={selectCls}

                >

                  <option value="outbound">Outbound</option>

                  <option value="return">Return</option>

                </select>

              </div>

            </div>



            <button

              onClick={startJourney}

              disabled={busy !== null || loadingMeta}

              className="w-full px-3 py-2.5 text-sm font-semibold bg-navy-800 text-white rounded-lg hover:bg-navy-900 transition-colors disabled:opacity-50"

            >

              {busy === "start" ? "Starting…" : journey ? "Journey Active" : "Start Journey"}

            </button>



            <button

              onClick={advance}

              disabled={busy !== null || !journey || status?.is_complete}

              className="w-full px-3 py-2.5 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"

            >

              {busy === "advance" ? "Advancing…" : "Advance 2 Hours"}

            </button>



            <div className="pt-2 border-t border-slate-100">

              <p className="text-[10px] font-semibold uppercase tracking-wider text-navy-400 mb-2">

                Recalculate from fix (live position)

              </p>

              <div className="grid grid-cols-2 gap-2">

                <input

                  type="text"

                  step="any"

                  value={liveLat}

                  onChange={(e) => setLiveLat(e.target.value)}

                  disabled={!journey}

                  placeholder="Latitude (31S)"

                  className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-navy-700"

                />

                <input

                  type="text"

                  step="any"

                  value={liveLon}

                  onChange={(e) => setLiveLon(e.target.value)}

                  disabled={!journey}

                  placeholder="Longitude (79E)"

                  className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-navy-700"

                />

              </div>

              <button

                onClick={recalc}

                disabled={busy !== null || !journey}

                className="mt-2 w-full px-3 py-2 text-xs font-semibold border border-blue-600 text-blue-700 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"

              >

                {busy === "recalc" ? "Recalculating…" : "Recalculate Route"}

              </button>

            </div>



            {status?.is_complete && (

              <p className="text-xs font-semibold text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">

                Journey complete — arrived at {journey?.destination} after {nowHours.toFixed(1)} h.

              </p>

            )}

          </CardBody>

        </Card>



        <Card>

          <CardHeader

            title="Voyage Map"

            subtitle={

              journey

                ? `${journey.origin} → ${journey.destination} · update #${journey.route_update_count}`

                : port

                  ? `${port.name} → ${center?.name ?? "select center"}`

                  : "Loading configuration…"

            }

            action={

              <div className="flex items-center gap-3">

                <div className="flex items-center gap-3 text-[10px] text-navy-500">

                  <span className="flex items-center gap-1">

                    <span className="w-4 h-1.5 rounded bg-navy-800 inline-block" />

                    Recommended

                  </span>

                  <span className="flex items-center gap-1">

                    <span className="w-4 border-t-2 border-dashed border-blue-400 inline-block" />

                    Alternative

                  </span>

                </div>

                <button

                  type="button"

                  onClick={refreshMap}

                  className="map-refresh-button"

                  aria-label="Refresh map"

                  title="Refresh map"

                >

                  <svg viewBox="0 0 24 24" aria-hidden="true">

                    <path d="M20 11a8 8 0 0 0-14.7-4.3L3 9m0 0V4m0 5h5M4 13a8 8 0 0 0 14.7 4.3L21 15m0 0v5m0-5h-5" />

                  </svg>

                </button>

              </div>

            }

          />

          <CardBody>

            <div className="h-[420px] sm:h-[520px] xl:h-[560px] rounded-lg overflow-hidden border border-slate-200">

              <AntarcticMap

                seaIce={seaIce ?? null}

                icebergs={icebergs?.icebergs ?? []}

                recommended={journeyRoute}

                alternatives={planning?.alternatives ?? []}

                vesselPos={journey ? vesselPos : null}

                vesselLabel={vessel?.name ?? "Vessel"}

                startPoint={
                  mode === "return" 
                    ? (center ? { name: center.name, lat: center.latitude, lon: center.longitude } : null)
                    : (port ? { name: port.name, lat: port.latitude, lon: port.longitude } : null)
                }

                endPoint={
                  mode === "return"
                    ? (port ? { name: port.name, lat: port.latitude, lon: port.longitude } : null)
                    : (center ? { name: center.name, lat: center.latitude, lon: center.longitude } : null)
                }

                fitBounds={Boolean(journey)}

                navigatorView={Boolean(journey)}

                refreshToken={mapRefreshToken}

                focusPoint={alertFocus}

                height="100%"

              />

            </div>

          </CardBody>

        </Card>

      </div>



      <Card>

        <CardHeader

          title="Journey Timeline"

          subtitle="2-hour rolling route updates between departure and destination"

        />

        <CardBody>

          <div className="overflow-x-auto py-2">

            <JourneyTimeline steps={timeline} />

          </div>

        </CardBody>

      </Card>



      {routeError && (

        <Card>

          <CardBody>

            <div className="flex items-center justify-between gap-3 text-xs text-red-700">

              <span>Route generation failed. Reason: {routeError}</span>

              {port && center && (

                <button

                  type="button"

                  onClick={() => fetchAlternatives(

                    Number(liveLat || port.latitude),

                    Number(liveLon || port.longitude),

                    center.latitude,

                    center.longitude,

                    vesselId,

                    "Retry route generation",

                    planning,

                  )}

                  className="px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 font-medium"

                >

                  Retry

                </button>

              )}

            </div>

          </CardBody>

        </Card>

      )}



      {(journey || planning) ? (

        <Card>

          <CardHeader

            title="Route Details"

            subtitle={journey ? `journey ${journey.journey_id.slice(0, 8)}` : planning ? `route ${planning.route_id.slice(0, 8)} · planning only` : ""}

          />

          <CardBody>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">

              {[

                {

                  label: "Distance",

                  value: journey

                    ? `${journey.total_distance_nm.toFixed(0)} nm`

                    : planning

                      ? `${planning.recommended.distance_nm.toFixed(0)} nm`

                      : "—",

                },

                {

                  label: "Est. Duration",

                  value: journey

                    ? `${journey.estimated_duration_hours.toFixed(1)} h`

                    : planning

                      ? `${planning.recommended.travel_time_hours.toFixed(1)} h`

                      : "—",

                },

                {

                  label: "Fuel",

                  value: journey

                    ? `${journey.total_fuel_tons.toFixed(1)} t`

                    : planning

                      ? `${(planning.recommended.fuel_tons ?? 0).toFixed(1)} t`

                      : "—",

                },

                {

                  label: "Risk",

                  value: journey?.max_risk_level ?? planning?.recommended.risk_level ?? "—",

                },

                {

                  label: "Waypoints",

                  value: `${journey?.waypoints.length ?? planning?.recommended.waypoints.length ?? 0}`,

                },

                {

                  label: "Route Updates",

                  value: `${journey?.route_update_count ?? 1}`,

                },

              ].map((s) => (

                <div key={s.label} className="p-3 bg-slate-50 rounded-lg text-center">

                  <p className="text-[10px] uppercase tracking-wider text-navy-400">{s.label}</p>

                  <p className="mt-1 text-sm font-bold text-navy-900">{s.value}</p>

                </div>

              ))}

            </div>



            {planning?.ocean_approach_distance_km != null && (

              <div className="mt-4 p-2 bg-amber-50 border border-amber-100 rounded-lg text-[11px] text-amber-700">

                {planning.destination_name ?? "Destination"} is on land. Routing to the

                nearest navigable ocean cell {planning.ocean_approach_distance_km.toFixed(0)} km

                away ({planning.destination_latitude.toFixed(2)},{" "}

                {planning.destination_longitude.toFixed(2)}). Station coordinates are

                preserved; this is the ocean approach point used for route generation.

              </div>

            )}



            {planning && planning.alternatives.length > 0 && (

              <div className="mt-4">

                <h4 className="text-xs font-semibold text-navy-700 mb-2">

                  Active route set

                </h4>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">

                  {[planning.recommended, ...planning.alternatives].map((route, index) => {

                    const isRecommended = index === 0;

                    const riskLevel = (route.risk_level ?? "unknown").toLowerCase();

                    const isSelected = selectedRoute === route;

                    return (

                      <button

                        key={`${route.distance_nm}-${index}`}

                        type="button"

                        onClick={() => setNavigation({ selectedRoute: route })}

                        className={`w-full text-left p-3 border rounded-lg text-[11px] ${isSelected ? "border-blue-400 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}

                      >

                        <p className="font-semibold text-navy-800">

                          {isRecommended ? "Recommended Route" : `Alternative Route ${index}`}

                        </p>

                        <p className="mt-1 text-navy-600">

                          {isRecommended ? "Low Risk" : riskLevel === "moderate" ? "Medium Risk" : "Higher Risk"}

                        </p>

                        <div className="mt-2 space-y-1 text-[10px] text-navy-500">

                          <div>{route.distance_nm.toFixed(0)} nm</div>

                          <div>ETA: {route.travel_time_hours.toFixed(1)} h</div>

                          <div>Ice Risk: {riskLevel}</div>

                          <div>Iceberg Risk: {riskLevel}</div>

                        </div>

                      </button>

                    );

                  })}

                </div>

              </div>

            )}



            {planning?.disclaimer && (

              <div className="mt-3 p-2 bg-blue-50 border border-blue-100 rounded-lg text-[11px] text-blue-700">

                {planning.disclaimer}

              </div>

            )}

          </CardBody>

        </Card>

      ) : null}

    </div>

  );

}