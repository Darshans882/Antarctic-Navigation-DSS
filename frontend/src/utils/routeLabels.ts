import type { AssistantRouteSummary, RoutesOptimizeResponse } from "../types";

/**
 * Routes come back from the API as a bare recommended route plus a list of
 * alternatives, with no names. The assistant needs something to refer to them
 * by, so we label them here - once - and use the same labels both when sending
 * context and when acting on a "select that route" request.
 */
export function labelRoutes(
  planning: RoutesOptimizeResponse | null,
): AssistantRouteSummary[] {
  if (!planning) return [];
  const summarise = (route: RoutesOptimizeResponse["recommended"], index: number | null) => ({
    id: `${planning.route_id}:${index ?? "rec"}`,
    label: index === null ? "Recommended Route" : `Alternative Route ${index}`,
    risk_level: route.risk_level,
    distance_nm: route.distance_nm,
    duration_hours: route.travel_time_hours,
    is_recommended: index === null,
  });
  return [
    summarise(planning.recommended, null),
    ...planning.alternatives.map((route, i) => summarise(route, i + 1)),
  ];
}

/** Find a labelled route summary by its assistant label. */
export function findRouteByLabel(
  planning: RoutesOptimizeResponse | null,
  label: string,
): RoutesOptimizeResponse["recommended"] | null {
  if (!planning) return null;
  if (label === "Recommended Route") return planning.recommended;
  const match = /^Alternative Route (\d+)$/.exec(label);
  if (!match) return null;
  return planning.alternatives[Number(match[1]) - 1] ?? null;
}
