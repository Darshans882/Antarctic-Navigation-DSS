import type { AlertRecord, JourneyStatus } from "../types";
import type { AppCtx } from "../context/AppContext";
import type { AssistantDashboardContext } from "../types";
import { labelRoutes } from "./routeLabels";

/**
 * Describe what the application is showing right now.
 *
 * This is the only place the assistant's picture of the app is assembled, so
 * both assistant UIs send an identical snapshot and neither can drift from what
 * the user actually sees. Values that the app has not loaded are simply left
 * out, which the backend reads as "unknown" rather than zero.
 */
export function buildAssistantContext(app: AppCtx): AssistantDashboardContext {
  const { page, alerts, unreadAlertCount, navigation, activeRoute, seaIceHorizon, selectedIcebergId } =
    app;
  const journey = navigation.journey;

  const context: AssistantDashboardContext = {
    page,
    vessel_id: navigation.vesselId || undefined,
    sea_ice_horizon: seaIceHorizon,
    selected_iceberg_id: selectedIcebergId ?? undefined,
    unread_alert_count: unreadAlertCount,
    alert_context: alerts.map((alert: AlertRecord) => ({
      title: alert.title,
      message: alert.message,
      type: alert.type,
      severity: alert.severity,
      reason: alert.reason,
      recommended_action: alert.recommendedAction,
      selected_route_label: alert.routeId,
      iceberg_id: alert.icebergId,
      distance_km: alert.distanceKm,
      read: alert.read,
      timestamp: alert.timestamp,
    })),
    navigation: {
      port_id: navigation.portId || null,
      center_id: navigation.centerId || null,
      vessel_id: navigation.vesselId || null,
      journey_mode: navigation.mode,
      live_lat: navigation.liveLat || null,
      live_lon: navigation.liveLon || null,
      selected_route: routeSummary(navigation.selectedRoute, "Selected Route"),
      routes_available: labelRoutes(navigation.planning ?? activeRoute),
      time_step_hours: 2,
      journey: journey
        ? {
            journey_id: journey.journey_id,
            origin: journey.origin,
            destination: journey.destination,
            journey_mode: journey.journey_mode,
            status: journeyStatus(navigation.status),
            total_distance_nm: journey.total_distance_nm ?? null,
            total_fuel_tons: journey.total_fuel_tons ?? null,
            estimated_duration_hours: journey.estimated_duration_hours ?? null,
            max_risk_level: journey.max_risk_level ?? null,
            route_update_count: journey.route_update_count ?? null,
            vessel_lat: journey.current_vessel_lat ?? null,
            vessel_lon: journey.current_vessel_lon ?? null,
            progress_percent: navigation.status?.progress_percent ?? null,
            remaining_distance_nm: navigation.status?.remaining_distance_nm ?? null,
            remaining_fuel_tons: navigation.status?.remaining_fuel_tons ?? null,
            current_time_hours: navigation.status?.current_time_hours ?? null,
            is_complete: navigation.status?.is_complete ?? false,
          }
        : null,
    },
  };

  const lat = Number(navigation.liveLat || journey?.current_vessel_lat);
  const lon = Number(navigation.liveLon || journey?.current_vessel_lon);
  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    context.vessel = {
      vessel_id: app.activeVessel?.vessel_id ?? navigation.vesselId ?? null,
      name: app.activeVessel?.name ?? null,
      lat,
      lon,
      heading_deg: null,
      speed_knots: null,
      speed_known: false,
    };
  } else if (app.activeVessel) {
    context.vessel = {
      vessel_id: app.activeVessel.vessel_id,
      name: app.activeVessel.name,
      lat: null,
      lon: null,
      heading_deg: null,
      speed_knots: null,
      speed_known: false,
    };
  }

  return context;
}

function routeSummary(route: unknown, label: string) {
  if (!route || typeof route !== "object") return null;
  const r = route as Record<string, unknown>;
  return {
    id: label,
    label,
    risk_level: (r.risk_level as string) ?? null,
    distance_nm: (r.distance_nm as number) ?? null,
    duration_hours: (r.travel_time_hours as number) ?? null,
    is_recommended: false,
    waypoints: (r.waypoints as unknown[]) ?? (r.coordinates as unknown[]) ?? null,
  };
}

/** Map the app's journey status object onto the assistant's three-state model. */
function journeyStatus(status: JourneyStatus | null): "not_started" | "active" | "complete" {
  if (!status) return "not_started";
  return status.is_complete ? "complete" : "active";
}
