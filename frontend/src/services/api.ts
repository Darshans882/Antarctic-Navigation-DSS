import axios from "axios";
import type {
  AnalyticsSummaryResponse,
  AssistantActionResultRequest,
  AssistantChatRequest,
  AssistantChatResponse,
  DatasetStatusResponse,
  DatasetsResponse,
  HealthResponse,
  IcebergDetailResponse,
  IcebergDistanceResponse,
  IcebergPredictionsResponse,
  IcebergTrajectoryResponse,
  IcebergsListResponse,
  JourneyResponse,
  JourneyStatus,
  LegacyVesselInfo,
  ModelRegistryResponse,
  PortInfo,
  ResearchCenterInfo,
  RouteDetailResponse,
  RoutesOptimizeResponse,
  SeaIceCurrentResponse,
  SeaIceForecastResponse,
  SimulationConfig,
  StartJourneyRequest,
  VesselsResponse,
} from "../types";

const rawBase = (import.meta.env.VITE_API_BASE_URL ?? "").trim();
const normalizedBase = rawBase.replace(/\/+$/, "").replace(/\/api$/, "");
const isLocalBrowser =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "0.0.0.0");
// On localhost, always use the Vite proxy (/api) unless an explicit localhost URL was provided
const API_BASE_URL =
  isLocalBrowser && normalizedBase && !normalizedBase.includes("localhost") && !normalizedBase.includes("127.0.0.1")
    ? "/api"
    : normalizedBase
    ? `${normalizedBase}/api`
    : "/api";

const inFlightRequests = new Map<string, Promise<unknown>>();

function memoizedRequest<T>(key: string, request: () => Promise<T>): Promise<T> {
  const existing = inFlightRequests.get(key) as Promise<T> | undefined;
  if (existing) return existing;

  const promise = request().finally(() => {
    inFlightRequests.delete(key);
  });

  inFlightRequests.set(key, promise as Promise<unknown>);
  return promise;
}

const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 
    "Content-Type": "application/json",
    "bypass-tunnel-reminder": "true"
  },
});

const routeHttp = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: { 
    "Content-Type": "application/json",
    "bypass-tunnel-reminder": "true"
  },
});

routeHttp.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.detail ?? err.message ?? "Route request failed";
    return Promise.reject(new Error(typeof msg === "string" ? msg : JSON.stringify(msg)));
  },
);

http.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err.response?.data?.detail ??
      err.response?.data ??
      err.message ??
      "Unknown error";
    return Promise.reject(new Error(typeof msg === "string" ? msg : JSON.stringify(msg)));
  },
);

export const api = {
  health: () =>
    http.get<HealthResponse>("/health").then((r) => r.data),

  datasets: () =>
    http.get<DatasetsResponse>("/datasets").then((r) => r.data),

  datasetsStatus: () =>
    http.get<DatasetStatusResponse>("/datasets/status").then((r) => r.data),

  seaIceCurrent: () =>
    http.get<SeaIceCurrentResponse>("/sea-ice/current").then((r) => r.data),

  seaIceForecast: (horizonHours: number, model = "persistence") =>
    memoizedRequest(`seaIceForecast:${horizonHours}:${model}`, () =>
      http
        .get<SeaIceForecastResponse>("/sea-ice/forecast", {
          params: { horizon_hours: horizonHours, model },
        })
        .then((r) => r.data),
    ),

  icebergs: () =>
    http.get<IcebergsListResponse>("/icebergs").then((r) => r.data),

  icebergDetail: (id: string) =>
    http.get<IcebergDetailResponse>(`/icebergs/${id}`).then((r) => r.data),

  icebergPredict: (icebergIds: string[], horizonHours = 24) =>
    http
      .post<IcebergPredictionsResponse>("/icebergs/predict", {
        iceberg_ids: icebergIds,
        horizon_hours: horizonHours,
      })
      .then((r) => r.data),

  icebergTrajectory: (id: string) =>
    memoizedRequest(`icebergTrajectory:${id}`, () =>
      http
        .get<IcebergTrajectoryResponse>(`/icebergs/${id}/trajectory`)
        .then((r) => r.data),
    ),

  icebergDistance: (a: string, b: string) =>
    http
      .get<IcebergDistanceResponse>("/icebergs/distance", {
        params: { iceberg_a: a, iceberg_b: b },
      })
      .then((r) => r.data),

  routesOptimize: (payload: {
    start_latitude: number;
    start_longitude: number;
    destination_latitude: number;
    destination_longitude: number;
    vessel_id: string;
    preference: string;
  }) => {
    const key = `routesOptimize:${payload.vessel_id}:${payload.preference}:${payload.start_latitude}:${payload.start_longitude}:${payload.destination_latitude}:${payload.destination_longitude}`;
    return memoizedRequest(key, () =>
      routeHttp.post<RoutesOptimizeResponse>("/routes/optimize", payload).then((r) => r.data),
    );
  },

  routeDetail: (id: string) =>
    http.get<RouteDetailResponse>(`/routes/${id}`).then((r) => r.data),

  vessels: () =>
    http.get<VesselsResponse>("/vessels").then((r) => r.data),

  // ---- Legacy /api/v1 config + journey lifecycle (mounted on the same
  // backend, so it flows through the same Vite proxy) ----
  ports: () =>
    http.get<PortInfo[]>("/v1/config/ports").then((r) => r.data),

  researchCenters: () =>
    http.get<ResearchCenterInfo[]>("/v1/config/research-centers").then((r) => r.data),

  legacyVessels: () =>
    http.get<LegacyVesselInfo[]>("/v1/vessels/").then((r) => r.data),

  simulationConfig: () =>
    http.get<SimulationConfig>("/v1/config/simulation").then((r) => r.data),

  startJourney: (payload: StartJourneyRequest) =>
    http.post<JourneyResponse>("/v1/navigation/journey", payload).then((r) => r.data),

  advanceJourney: (journeyId: string) =>
    http.post<JourneyResponse>(`/v1/navigation/journey/${journeyId}/advance`).then((r) => r.data),

  recalculateJourney: (journeyId: string, lat: number, lon: number) =>
    http
      .post<JourneyResponse>(`/v1/navigation/journey/${journeyId}/recalculate`, null, {
        params: { lat, lon },
      })
      .then((r) => r.data),

  journeyStatus: (journeyId: string) =>
    http.get<JourneyStatus>(`/v1/navigation/journey/${journeyId}/status`).then((r) => r.data),

  analyticsSummary: () =>
    http.get<AnalyticsSummaryResponse>("/analytics/summary").then((r) => r.data),

  modelsStatus: () =>
    http.get<ModelRegistryResponse>("/models/status").then((r) => r.data),

  assistantChat: (payload: AssistantChatRequest) =>
    http.post<AssistantChatResponse>("/assistant/chat", payload).then((r) => r.data),
  assistantActionResult: (payload: AssistantActionResultRequest) =>
    http
      .post<AssistantChatResponse>("/assistant/action-result", payload)
      .then((r) => r.data),
  // ---- Advanced Sea-Ice Intelligence endpoints (/api/sea-ice/intelligence/...) ----
  seaIceClassification: () =>
    memoizedRequest("seaIceClassification", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/classification").then((r) => r.data),
    ),

  seaIceThickness: () =>
    memoizedRequest("seaIceThickness", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/thickness").then((r) => r.data),
    ),

  seaIceKeelDepth: () =>
    memoizedRequest("seaIceKeelDepth", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/keel-depth").then((r) => r.data),
    ),

  seaIceMeltPond: () =>
    memoizedRequest("seaIceMeltPond", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/melt-pond").then((r) => r.data),
    ),

  seaIceChange: (horizonHours = 24) =>
    memoizedRequest(`seaIceChange:${horizonHours}`, () =>
      http
        .get<Record<string, unknown>>("/sea-ice/intelligence/change", {
          params: { horizon_hours: horizonHours },
        })
        .then((r) => r.data),
    ),

  seaIceMeltZones: (horizonHours = 24) =>
    memoizedRequest(`seaIceMeltZones:${horizonHours}`, () =>
      http
        .get<Record<string, unknown>>("/sea-ice/intelligence/melt-zones", {
          params: { horizon_hours: horizonHours },
        })
        .then((r) => r.data),
    ),

  seaIceRisk: (horizonHours = 24) =>
    memoizedRequest(`seaIceRisk:${horizonHours}`, () =>
      http
        .get<Record<string, unknown>>("/sea-ice/intelligence/risk", {
          params: { horizon_hours: horizonHours },
        })
        .then((r) => r.data),
    ),

  seaIceClimateTrend: () =>
    memoizedRequest("seaIceClimateTrend", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/climate-trend").then((r) => r.data),
    ),

  seaIceModelConvergence: () =>
    memoizedRequest("seaIceModelConvergence", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/model-convergence").then((r) => r.data),
    ),

  seaIceSpectral: () =>
    memoizedRequest("seaIceSpectral", () =>
      http.get<Record<string, unknown>>("/sea-ice/intelligence/spectral").then((r) => r.data),
    ),
};
