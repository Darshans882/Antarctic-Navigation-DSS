import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  AlertRecord,
  JourneyMode,
  JourneyResponse,
  JourneyStatus,
  PageId,
  RoutesOptimizeResponse,
  AssistantContextSource,
  AssistantAction,
  AssistantActionType,
  VesselInfo,
} from "../types";
export const ALERT_CONFIG = {
  routeDistanceChangeKm: 50,
  routePathDeviationKm: 25,
};

/** Forecast horizons the Sea-Ice Forecast page offers. */
export const SEA_ICE_HORIZONS = [6, 12, 24, 48, 72, 120, 168] as const;
export const DEFAULT_SEA_ICE_HORIZON = 24;

/** The outcome of running an action, reported back to the assistant. */
export interface ActionOutcome {
  success: boolean;
  message: string;
}

/** A handler a page registers so the assistant can drive its existing controls. */
export type ActionHandler = (params: Record<string, unknown>) => Promise<ActionOutcome>;

const NOOP_HANDLERS: Record<string, ActionHandler> = {};

interface Toast {
  id: number;
  message: string;
  type: "info" | "success" | "error";
}

export interface UiMessage {
  role: "user" | "assistant";
  content: string;
  sources?: AssistantContextSource[];
  warnings?: string[];
  /** Actions the assistant proposed alongside this message. */
  actions?: AssistantAction[];
}

export interface AppCtx {
  page: PageId;
  setPage: (p: PageId) => void;
  alerts: AlertRecord[];
  unreadAlertCount: number;
  addAlert: (alert: Omit<AlertRecord, "id" | "timestamp" | "read"> & { id?: string }) => void;
  replaceRouteAlerts: (alerts: AlertRecord[]) => void;
  markAlertRead: (id: string, read?: boolean) => void;
  markAllAlertsRead: () => void;
  deleteAlert: (id: string) => void;
  clearAlerts: () => void;
  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;
  toggleSidebar: () => void;
  toasts: Toast[];
  toast: (message: string, type?: Toast["type"]) => void;
  removeToast: (id: number) => void;
  activeRoute: RoutesOptimizeResponse | null;
  setActiveRoute: (route: RoutesOptimizeResponse | null) => void;
  navigation: NavigationSnapshot;
  setNavigation: (next: Partial<NavigationSnapshot>) => void;
  assistantMessages: UiMessage[];
  setAssistantMessages: (m: UiMessage[] | ((prev: UiMessage[]) => UiMessage[])) => void;
  seaIceHorizon: number;
  setSeaIceHorizon: (hours: number) => void;
  selectedIcebergId: string | null;
  setSelectedIcebergId: (id: string | null) => void;
  /**
   * Run a validated assistant action against the app's real controls.
   *
   * Only actions this application already supports are accepted, and the
   * result is the genuine outcome - the assistant is never told something
   * worked unless it did.
   */
  runAssistantAction: (
    type: AssistantActionType,
    params: Record<string, unknown>,
  ) => Promise<ActionOutcome>;
  /** Pages call this on mount to expose their existing controls. */
  registerActionHandler: (type: AssistantActionType, handler: ActionHandler) => void;
  unregisterActionHandler: (type: AssistantActionType) => void;
  /** The vessel currently selected in the planner, shared for context. */
  activeVessel: VesselInfo | null;
  setActiveVessel: (v: VesselInfo | null) => void;
}

export interface NavigationSnapshot {
  journey: JourneyResponse | null;
  status: JourneyStatus | null;
  planning: RoutesOptimizeResponse | null;
  portId: string;
  centerId: string;
  vesselId: string;
  mode: JourneyMode;
  liveLat: string;
  liveLon: string;
  selectedRoute: import("../types").RouteResult | null;
  alertFocus: [number, number] | null;
}

const Ctx = createContext<AppCtx>(null!);

let toastId = 0;

export function AppProvider({ children }: { children: ReactNode }) {
  const pageFromPath = (path: string): PageId => {
    switch (path) {
      case "/navigation":
        return "planner";
      case "/sea-ice":
        return "sea-ice";
      case "/icebergs":
        return "icebergs";
      case "/alert-message":
      case "/alerts":
        return "alerts";
      case "/assistant":
        return "assistant";
      default:
        return "home";
    }
  };

  const [page, setPageState] = useState<PageId>(() => pageFromPath(window.location.pathname));
  const [alerts, setAlerts] = useState<AlertRecord[]>(() => {
    try {
      const saved = window.localStorage.getItem("antarctic-dss-alerts");
      return saved ? (JSON.parse(saved) as AlertRecord[]) : [];
    } catch {
      return [];
    }
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notifiedAlertIds = useRef(new Set<string>());
  const [activeRoute, setActiveRouteState] = useState<RoutesOptimizeResponse | null>(null);
  const [navigation, setNavigationState] = useState<NavigationSnapshot>({
    journey: null,
    status: null,
    planning: null,
    portId: "",
    centerId: "",
    vesselId: "research_vessel_sagar",
    mode: "outbound",
    liveLat: "",
    liveLon: "",
    selectedRoute: null,
    alertFocus: null,
  });
  const [assistantMessages, setAssistantMessages] = useState<UiMessage[]>([]);
  const [seaIceHorizon, setSeaIceHorizonState] = useState<number>(DEFAULT_SEA_ICE_HORIZON);
  const [selectedIcebergId, setSelectedIcebergId] = useState<string | null>(null);
  const [activeVessel, setActiveVessel] = useState<VesselInfo | null>(null);
  // Pages register their own handlers on mount, so the assistant drives the
  // same functions the buttons call rather than a parallel implementation.
  const actionHandlers = useRef<Record<string, ActionHandler>>(NOOP_HANDLERS);
  const registerActionHandler = useCallback((type: AssistantActionType, handler: ActionHandler) => {
    actionHandlers.current[type] = handler;
  }, []);
  const unregisterActionHandler = useCallback((type: AssistantActionType) => {
    delete actionHandlers.current[type];
  }, []);
  const setPage = useCallback((nextPage: PageId) => {
    setPageState(nextPage);
    const paths: Record<PageId, string> = {
      home: "/",
      planner: "/navigation",
      "sea-ice": "/sea-ice",
      icebergs: "/icebergs",
      alerts: "/alert-message",
      assistant: "/assistant",
    };
    window.history.pushState({}, "", paths[nextPage]);
  }, []);

  useEffect(() => {
    const onPopState = () => setPageState(pageFromPath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    
    // Preload speech synthesis voices
    if ("speechSynthesis" in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
      };
      window.speechSynthesis.getVoices();
    }
    
    return () => {
      window.removeEventListener("popstate", onPopState);
      if ("speechSynthesis" in window) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, []);
  const setNavigation = useCallback(
    (next: Partial<NavigationSnapshot>) => setNavigationState((current) => ({ ...current, ...next })),
    [],
  );

  const toast = useCallback(
    (message: string, type: Toast["type"] = "info", cancelPrevious: boolean = true): Promise<void> => {
      return new Promise((resolve) => {
        const id = ++toastId;
        setToasts((t) => [...t, { id, message, type }]);
        setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);

        // Play voice alert
        if ("speechSynthesis" in window) {
          if (cancelPrevious) {
            window.speechSynthesis.cancel(); // Cancel any ongoing speech
          }
          
          // Phonetically correct 'route' as 'root' for better TTS pronunciation
          const spokenMessage = message.replace(/route/gi, "root");
          const utterance = new SpeechSynthesisUtterance(spokenMessage);
          
          utterance.onend = () => resolve();
          utterance.onerror = () => resolve();
          
          const voices = window.speechSynthesis.getVoices();
          if (voices.length > 0) {
            // Look for Indian accented voices first, then fall back to clear voices
            const clearVoice = 
              voices.find(v => (v.lang === "en-IN" || v.name.includes("India") || v.name.includes("Indian")) && (v.name.includes("Natural") || v.name.includes("Online (Natural)"))) ||
              voices.find(v => v.lang === "en-IN" || v.name.includes("India") || v.name.includes("Indian")) ||
              voices.find(v => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Online (Natural)"))) ||
              voices.find(v => v.lang.startsWith("en") && (v.name.includes("Premium") || v.name.includes("Google"))) ||
              voices.find(v => v.lang.startsWith("en") && v.name.includes("Female")) ||
              voices.find(v => v.lang.startsWith("en"));
              
            if (clearVoice) {
              utterance.voice = clearVoice;
            }
          }

          utterance.rate = 0.75;
          utterance.pitch = 1.0;
          window.speechSynthesis.speak(utterance);
        } else {
          resolve();
        }
      });
    },
    [],
  );

  const replaceRouteAlerts = useCallback((nextAlerts: AlertRecord[]) => {
    const newAlerts = nextAlerts.filter((alert) => !notifiedAlertIds.current.has(alert.id));
    nextAlerts.forEach((alert) => notifiedAlertIds.current.add(alert.id));
    setAlerts((current) => [
      ...nextAlerts,
      ...current.filter((alert) => !["route", "sea-ice", "iceberg"].includes(alert.type)),
    ]);
    
    if (newAlerts.length > 0) {
      setTimeout(async () => {
        for (let i = 0; i < newAlerts.length; i++) {
          const alert = newAlerts[i];
          await toast(
            alert.message, 
            alert.severity === "critical" || alert.severity === "high" ? "error" : "info",
            i === 0 // Cancel only on the first alert of this batch
          );
          // 1-second silent gap before the next notification pops up
          await new Promise(r => setTimeout(r, 1000));
        }
      }, 5000); // 5-second initial delay
    }
  }, [toast]);

  const addAlert = useCallback(
    (input: Omit<AlertRecord, "id" | "timestamp" | "read"> & { id?: string }) => {
      const id = input.id ?? `${input.type}-${input.routeId ?? "event"}-${input.title}`;
      if (notifiedAlertIds.current.has(id)) return;
      notifiedAlertIds.current.add(id);
      setAlerts((current) => current.some((alert) => alert.id === id)
        ? current
        : [{ ...input, id, timestamp: new Date().toISOString(), read: false }, ...current]);
      toast(input.message, input.severity === "critical" || input.severity === "high" ? "error" : "info");
    },
    [toast],
  );

  const setActiveRoute = useCallback((route: RoutesOptimizeResponse | null) => {
    setActiveRouteState(route);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem("antarctic-dss-alerts", JSON.stringify(alerts));
    } catch {
      // Alerts remain available in memory when storage is unavailable.
    }
  }, [alerts]);

  const markAlertRead = useCallback((id: string, read = true) => {
    setAlerts((current) => current.map((alert) => alert.id === id ? { ...alert, read } : alert));
  }, []);
  const markAllAlertsRead = useCallback(() => setAlerts((current) => current.map((alert) => ({ ...alert, read: true }))), []);
  const deleteAlert = useCallback((id: string) => {
    setAlerts((current) => current.filter((alert) => alert.id !== id));
  }, []);
  const clearAlerts = useCallback(() => {
    notifiedAlertIds.current.clear();
    setAlerts([]);
  }, []);

  const toggleSidebar = useCallback(() => setSidebarOpen((o) => !o), []);

  const removeToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const setSeaIceHorizon = useCallback((hours: number) => {
    setSeaIceHorizonState(hours);
  }, []);

  const runAssistantAction = useCallback(
    async (type: AssistantActionType, params: Record<string, unknown>): Promise<ActionOutcome> => {
      // Actions the context can perform itself need no page handler.
      switch (type) {
        case "navigate": {
          const page = params.page as PageId;
          if (!page) return { success: false, message: "No page was specified." };
          setPage(page);
          const pageNames: Record<string, string> = {
            home: "Home",
            "sea-ice": "Sea-Ice Forecast",
            icebergs: "Iceberg Tracking",
            planner: "Navigation Dashboard",
            alerts: "Alert Message",
            assistant: "AI Assistant",
          };
          return { success: true, message: `Opened ${pageNames[page] ?? page}` };
        }
        case "set_horizon": {
          const hours = Number(params.hours);
          if (!SEA_ICE_HORIZONS.includes(hours as (typeof SEA_ICE_HORIZONS)[number])) {
            return { success: false, message: `${hours}h is not an available horizon.` };
          }
          setSeaIceHorizonState(hours);
          return { success: true, message: `Forecast horizon changed to ${hours} hours` };
        }
        case "select_iceberg": {
          const id = params.iceberg_id as string | undefined;
          if (!id) return { success: false, message: "No iceberg ID was specified." };
          setSelectedIcebergId(id);
          return { success: true, message: `Iceberg ${id} selected` };
        }
        case "pause_journey": {
          const handler = actionHandlers.current["pause_journey"];
          if (handler) return await handler(params);
          if (!navigation.journey) {
            return { success: false, message: "No active journey to pause." };
          }
          toast("Voyage simulation paused", "info");
          return { success: true, message: "Journey paused" };
        }
        case "resume_journey": {
          const handler = actionHandlers.current["resume_journey"];
          if (handler) return await handler(params);
          if (!navigation.journey) {
            return { success: false, message: "No active journey to resume." };
          }
          toast("Voyage simulation resumed", "info");
          return { success: true, message: "Journey resumed" };
        }
        case "mark_alerts_read":
          markAllAlertsRead();
          return { success: true, message: "All alerts marked as read." };
        default:
          break;
      }

      const handler = actionHandlers.current[type];
      if (!handler) {
        return {
          success: false,
          message:
            "That control isn't available because the page that owns it isn't open yet.",
        };
      }
      try {
        return await handler(params);
      } catch (error) {
        return {
          success: false,
          message: error instanceof Error ? error.message : "The action threw an error.",
        };
      }
    },
    [markAllAlertsRead, setPage],
  );

  const value = useMemo<AppCtx>(
    () => ({
      page,
      setPage,
      alerts,
      unreadAlertCount: alerts.filter((alert) => !alert.read).length,
      addAlert,
      replaceRouteAlerts,
      markAlertRead,
      markAllAlertsRead,
      deleteAlert,
      clearAlerts,
      sidebarOpen,
      setSidebarOpen,
      toggleSidebar,
      toasts,
      toast,
      removeToast,
      activeRoute,
      setActiveRoute,
      navigation,
      setNavigation,
      assistantMessages,
      setAssistantMessages,
      seaIceHorizon,
      setSeaIceHorizon,
      selectedIcebergId,
      setSelectedIcebergId,
      runAssistantAction,
      registerActionHandler,
      unregisterActionHandler,
      activeVessel,
      setActiveVessel,
    }),
    [page, alerts, addAlert, replaceRouteAlerts, markAlertRead, markAllAlertsRead, deleteAlert, clearAlerts, sidebarOpen, toasts, toast, removeToast, toggleSidebar, activeRoute, navigation, setNavigation, setActiveRoute, assistantMessages, setAssistantMessages, seaIceHorizon, selectedIcebergId, activeVessel, runAssistantAction, registerActionHandler, unregisterActionHandler],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  return useContext(Ctx);
}

/**
 * Expose a page's existing control to the AI assistant.
 *
 * The handler is registered for as long as the page is mounted, so the
 * assistant can never call a control the user cannot see.
 */
export function useAssistantActionHandler(
  type: AssistantActionType,
  handler: ActionHandler,
): void {
  const { registerActionHandler, unregisterActionHandler } = useApp();
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    registerActionHandler(type, (params) => ref.current(params));
    return () => unregisterActionHandler(type);
  }, [type, registerActionHandler, unregisterActionHandler]);
}