import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../services/api";

import type { SeaIceCurrentResponse, SeaIceForecastResponse } from "../types";
import { FALLBACK_SEA_ICE_CURRENT, FALLBACK_SEA_ICE_FORECAST } from "../data/fallbackSeaIce";

import { LoadingState, ErrorState } from "../components/common/States";

import { useApp, useAssistantActionHandler } from "../context/AppContext";
import { AntarcticPageHeader } from "../components/common/AntarcticPageHeader";
import { Antarctic3DGlobe } from "../components/maps/Antarctic3DGlobe";

import { seaIceLegendStops } from "../utils/colormap";

import {

  ChartPieIcon,

  Cog6ToothIcon,

  Square3Stack3DIcon,

  CalendarDaysIcon,

  ExclamationTriangleIcon,

  ShieldExclamationIcon,

} from "@heroicons/react/24/solid";

import {

  ArrowsUpDownIcon,

  ArrowTrendingDownIcon,

  ArrowPathIcon,

} from "@heroicons/react/24/outline";

import {

  XAxis,

  YAxis,

  CartesianGrid,

  Tooltip,

  ResponsiveContainer,

  PieChart,

  Pie,

  Cell,

  BarChart,

  Bar,

  ReferenceLine,

  Area,

  AreaChart,

} from "recharts";



const HORIZONS = [6, 12, 24, 48, 72, 120, 168];



function UnavailableBadge({ reason }: { reason?: string }) {

  return (

    <div className="flex flex-col items-center justify-center min-h-[70px] gap-2 py-3">

      <div className="flex items-center gap-1.5 text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs font-medium max-w-sm text-center">

        <svg className="w-3.5 h-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">

          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />

        </svg>

        {reason ?? "Data unavailable"}

      </div>

    </div>

  );

}



function SectionHeader({

  title,

  subtitle,

  tag,

  icon,

}: {

  title: string;

  subtitle?: string;

  tag?: string;

  icon?: React.ReactNode;

}) {

  return (

    <div className="flex items-start justify-between mb-4">

      <div className="flex items-center gap-2.5">

        {icon && (

          <div className="w-8 h-8 rounded-lg bg-blue-50/80 border border-blue-100/60 flex items-center justify-center shrink-0">

            {icon}

          </div>

        )}

        <div>

          <h3 className="text-sm font-semibold text-navy-900">{title}</h3>

          {subtitle && <p className="text-[11px] text-navy-400 mt-0.5">{subtitle}</p>}

        </div>

      </div>

      {tag && (

        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100 shrink-0">{tag}</span>

      )}

    </div>

  );

}



function RiskBadge({ level }: { level: string }) {

  const styles: Record<string, string> = {

    low: "bg-emerald-100 text-emerald-700 border-emerald-200",

    medium: "bg-amber-100 text-amber-700 border-amber-200",

    high: "bg-red-100 text-red-700 border-red-200",

  };

  return (

    <span

      aria-label={`${level === "medium" ? "Moderate" : level} ice risk`}

      className={`inline-flex items-center justify-center w-6 h-6 rounded-full border ${styles[level] ?? "bg-slate-100 text-slate-600 border-slate-200"}`}

    >

      <span className={`w-2 h-2 rounded-full ${level === "low" ? "bg-emerald-500" : level === "medium" ? "bg-amber-500" : "bg-red-500"}`} />

    </span>

  );

}



const ICE_TYPE_COLORS: Record<string, string> = {

  myi: "#1e40af", fyi: "#60a5fa", mixed: "#93c5fd", open_water: "#bfdbfe",

};

const ICE_TYPE_LABELS: Record<string, string> = {

  myi: "Older ice (formed over several years)", fyi: "Ice formed this year", mixed: "Mixed or unknown ice", open_water: "Open water",

};



function IceClassificationPanel({ data }: { data: any }) {

  if (!data) return <div className="h-20 flex items-center justify-center text-xs text-navy-400">Loading...</div>;

  if (!data.available) return <UnavailableBadge reason={data.reason as string} />;

  const dist = data.distribution as Record<string, number>;

  const pieData = Object.entries(dist).map(([k, v]) => ({ name: ICE_TYPE_LABELS[k] ?? k, value: v, key: k }));

  return (

    <div>

      <div className="flex gap-4">

        <div className="w-40 h-40 flex-shrink-0">

          <ResponsiveContainer width="100%" height="100%">

            <PieChart>

              <Pie data={pieData} dataKey="value" cx="50%" cy="50%" innerRadius={35} outerRadius={60}>

                {pieData.map((e) => <Cell key={e.key} fill={ICE_TYPE_COLORS[e.key] ?? "#cbd5e1"} />)}

              </Pie>

              <Tooltip formatter={(v: number) => [`${v}%`]} contentStyle={{ fontSize: 11, borderRadius: 6 }} />

            </PieChart>

          </ResponsiveContainer>

        </div>

        <div className="flex flex-col justify-center gap-2 flex-1">

          {pieData.map((e) => (

            <div key={e.key} className="flex items-center gap-2">

              <div className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: ICE_TYPE_COLORS[e.key] ?? "#cbd5e1" }} />

              <span className="text-[11px] text-navy-700 flex-1">{e.name}</span>

              <span className="text-[11px] font-semibold text-navy-900">{e.value}%</span>

            </div>

          ))}

          <div className="mt-1 text-[10px] text-navy-500">Estimate confidence: {data.confidence as string}</div>

        </div>

      </div>

    </div>

  );

}



function ThicknessPanel({ data }: { data: any }) {

  if (!data) return <div className="h-20 flex items-center justify-center text-xs text-navy-400">Loading...</div>;

  if (!data.available) return <UnavailableBadge reason={data.reason as string} />;

  const barData = [

    { name: "Minimum", value: data.min_m as number },

    { name: "Average", value: data.mean_m as number },

    { name: "Maximum", value: data.max_m as number },

  ];

  return (

    <div>

      <div className="grid grid-cols-3 gap-2 mb-3">

        {[

          { label: "Minimum", value: `${data.min_m} m`, color: "text-blue-400" },

          { label: "Average", value: `${data.mean_m} m`, color: "text-blue-600" },

          { label: "Maximum", value: `${data.max_m} m`, color: "text-blue-900" },

        ].map((s) => (

          <div key={s.label} className="text-center bg-blue-50 rounded-lg p-2">

            <p className="text-[10px] text-navy-500">{s.label}</p>

            <p className={`text-sm font-bold ${s.color}`}>{s.value}</p>

          </div>

        ))}

      </div>

      <div className="h-[100px]">

        <ResponsiveContainer width="100%" height="100%">

          <BarChart data={barData} barCategoryGap="30%">

            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />

            <XAxis dataKey="name" tick={{ fontSize: 10 }} />

            <YAxis tick={{ fontSize: 10 }} unit=" m" domain={[0, 3.5]} />

            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} formatter={(v: number) => [`${v} m`]} />

            <Bar dataKey="value" fill="#3b82f6" radius={[3, 3, 0, 0]} />

          </BarChart>

        </ResponsiveContainer>

      </div>

    </div>

  );

}



function KeelDepthPanel({ data }: { data: any }) {

  if (!data) return <div className="h-20 flex items-center justify-center text-xs text-navy-400">Loading...</div>;

  if (!data.available) return <UnavailableBadge reason={data.reason as string} />;

  const stats = [

    { label: "Average ice thickness", value: `${data.mean_thickness_m} m` },

    { label: "Average depth below water", value: `${data.mean_keel_depth_m} m` },

    { label: "Deepest point below water", value: `${data.max_keel_depth_m} m` },

    { label: "Average space below ice", value: `${data.mean_subsurface_clearance_m} m` },

  ];

  return (

    <div>

      <div className="grid grid-cols-2 gap-2">

        {stats.map((s) => (

          <div key={s.label} className="bg-slate-50 rounded-lg p-2.5">

            <p className="text-[10px] text-navy-500">{s.label}</p>

            <p className="text-sm font-bold text-navy-900">{s.value}</p>

          </div>

        ))}

      </div>

    </div>

  );

}



function ChangeDetectionPanel({ data }: { data: any }) {

  if (!data) return <div className="h-20 flex items-center justify-center text-xs text-navy-400">Loading...</div>;

  if (!data.available) return <UnavailableBadge reason={data.reason as string} />;

  const changeItems = [

    { name: "Increasing", value: data.increase_pct_cells as number, fill: "#3b82f6" },

    { name: "Decreasing", value: data.decrease_pct_cells as number, fill: "#ef4444" },

    { name: "Stable", value: data.stable_pct_cells as number, fill: "#10b981" },

  ];

  const meanChange = data.mean_change_pct as number;

  return (

    <div>

      <div className="flex items-center gap-3 mb-3">

        <div className={`text-sm font-bold px-3 py-1.5 rounded-lg ${meanChange > 0 ? "bg-blue-100 text-blue-700" : meanChange < 0 ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700"}`}>

          {meanChange > 0 ? "+" : ""}{meanChange}%

        </div>

        <div>

          <p className="text-xs font-medium text-navy-700">Average change in ice cover</p>

          <p className="text-[11px] text-navy-500">Compared with the {data.horizon_hours}-hour forecast</p>

        </div>

      </div>

      <div className="space-y-1.5">

        {changeItems.map((item) => (

          <div key={item.name} className="flex items-center gap-2">

            <span className="text-[11px] text-navy-600 w-20">{item.name}</span>

            <div className="flex-1 bg-slate-100 rounded-full h-2">

              <div className="h-2 rounded-full transition-all" style={{ width: `${item.value}%`, backgroundColor: item.fill }} />

            </div>

            <span className="text-[11px] font-semibold text-navy-900 w-10 text-right">{item.value}%</span>

          </div>

        ))}

      </div>

    </div>

  );

}



function RiskPanel({ data }: { data: any }) {

  if (!data) return <div className="h-20 flex items-center justify-center text-xs text-navy-400">Loading...</div>;

  if (!data.available) return <UnavailableBadge reason={data.reason as string} />;

  const level = data.risk_level as string;

  const score = data.risk_score as number;

  const factors = data.factors as Record<string, number>;

  const factorData = [

    { name: "Avg ice cover", value: factors.mean_concentration_pct },

    { name: "Max ice cover", value: factors.max_concentration_pct },

    { name: "Area covered", value: factors.coverage_pct },

    { name: "Forecast change", value: Math.abs(factors.forecast_change_rate_pct) },

  ];

  return (

    <div>

      <div className="flex items-center gap-3 mb-4">

        <RiskBadge level={level} />

        <div>

          <p className="text-xs font-medium text-navy-700">{data.description as string}</p>

          <p className="text-[10px] text-navy-400">Risk score: {(score * 100).toFixed(1)} out of 100</p>

        </div>

      </div>

      <div className="h-[100px]">

        <ResponsiveContainer width="100%" height="100%">

          <BarChart data={factorData} barCategoryGap="20%">

            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />

            <XAxis dataKey="name" tick={{ fontSize: 9 }} />

            <YAxis tick={{ fontSize: 10 }} unit="%" domain={[0, 100]} />

            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} formatter={(v: number) => [`${v.toFixed(1)}%`]} />

            <Bar dataKey="value" fill="#6366f1" radius={[3, 3, 0, 0]} />

          </BarChart>

        </ResponsiveContainer>

      </div>

    </div>

  );

}



function ClimateTrendPanel({ data }: { data: any }) {

  if (!data) return <div className="h-20 flex items-center justify-center text-xs text-navy-400">Loading...</div>;

  if (!data.available) return <UnavailableBadge reason={data.reason as string} />;

  const series = (data.series as Array<Record<string, unknown>>).map((s, i) => ({

    idx: i,

    mean: s.mean_concentration_pct as number,

  }));

  const anomaly = data.anomaly_pct as number;

  const direction = data.anomaly_direction as string;

  return (

    <div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">

        {[

          { label: "Usual level", value: `${data.baseline_pct}%` },

          { label: "Current", value: `${data.current_pct}%` },

          { label: "Difference from usual", value: `${anomaly > 0 ? "+" : ""}${anomaly}%` },

          { label: "Past readings", value: String(data.record_count) },

        ].map((s) => (

          <div key={s.label} className="bg-slate-50 rounded-lg p-2 text-center">

            <p className="text-[10px] text-navy-500">{s.label}</p>

            <p className="text-xs font-bold text-navy-900">{s.value}</p>

          </div>

        ))}

      </div>

      <p className="text-[11px] text-navy-500 mb-2">Overall pattern: {direction}</p>

      <div className="h-[140px]">

        <ResponsiveContainer width="100%" height="100%">

          <AreaChart data={series}>

            <defs>

              <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">

                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />

                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />

              </linearGradient>

            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />

            <XAxis dataKey="idx" tick={{ fontSize: 9 }} label={{ value: "Past readings", position: "insideBottom", fontSize: 9 }} />

            <YAxis tick={{ fontSize: 10 }} unit="%" domain={["auto", "auto"]} />

            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} formatter={(v: number) => [`${v}%`, "Average ice cover"]} />

            <Area type="monotone" dataKey="mean" stroke="#3b82f6" strokeWidth={2} fill="url(#trendGrad)" name="Average ice cover" />

            <ReferenceLine y={data.baseline_pct as number} stroke="#94a3b8" strokeDasharray="4 4" />

          </AreaChart>

        </ResponsiveContainer>

      </div>

    </div>

  );

}



function CollapsibleSection({

  title,

  children,

  defaultOpen = true,

  icon,

}: {

  title: string;

  children: React.ReactNode;

  defaultOpen?: boolean;

  icon?: React.ReactNode;

}) {

  const [open, setOpen] = useState(defaultOpen);

  return (

    <div className="bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden">

      <button

        onClick={() => setOpen((v) => !v)}

        className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-slate-50 transition-colors"

      >

        <div className="flex items-center gap-2.5">

          {icon && (

            <div className="w-8 h-8 rounded-lg bg-blue-50/80 border border-blue-100/60 flex items-center justify-center shrink-0">

              {icon}

            </div>

          )}

          <span className="text-sm font-semibold text-navy-900">{title}</span>

        </div>

        <svg className={`w-4 h-4 text-navy-400 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">

          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />

        </svg>

      </button>

      {open && <div className="px-5 pb-5 pt-1">{children}</div>}

    </div>

  );

}



function StatCardWave({ id }: { id: string }) {

  return (

    <svg

      className="absolute right-0 bottom-0 h-10 w-24 pointer-events-none select-none"

      viewBox="0 0 100 40"

      fill="none"

      xmlns="http://www.w3.org/2000/svg"

      preserveAspectRatio="none"

    >

      <defs>

        <linearGradient id={`wave-back-${id}`} x1="50" y1="12" x2="50" y2="40" gradientUnits="userSpaceOnUse">

          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.32" />

          <stop offset="100%" stopColor="#e0f2fe" stopOpacity="0" />

        </linearGradient>

        <linearGradient id={`wave-front-${id}`} x1="50" y1="6" x2="50" y2="40" gradientUnits="userSpaceOnUse">

          <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.45" />

          <stop offset="100%" stopColor="#bae6fd" stopOpacity="0" />

        </linearGradient>

      </defs>

      <path

        d="M0 40 C 20 40, 28 30, 44 26 C 60 22, 68 32, 78 24 C 88 16, 94 12, 100 14 L 100 40 Z"

        fill={`url(#wave-back-${id})`}

      />

      <path

        d="M12 40 C 30 40, 38 32, 54 28 C 66 24, 74 30, 84 12 C 90 4, 96 8, 100 20 L 100 40 Z"

        fill={`url(#wave-front-${id})`}

      />

    </svg>

  );

}



export function SeaIceForecastPage() {

  const { toast, seaIceHorizon: horizon, setSeaIceHorizon: setHorizon } = useApp();

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const [current, setCurrent] = useState<SeaIceCurrentResponse | null>(null);

  const [forecast, setForecast] = useState<SeaIceForecastResponse | null>(null);



  const [classificationData, setClassificationData] = useState<Record<string, unknown> | null>(null);

  const [thicknessData, setThicknessData] = useState<Record<string, unknown> | null>(null);

  const [keelData, setKeelData] = useState<Record<string, unknown> | null>(null);

  const [changeData, setChangeData] = useState<Record<string, unknown> | null>(null);

  const [riskData, setRiskData] = useState<Record<string, unknown> | null>(null);

  const [climateTrendData, setClimateTrendData] = useState<Record<string, unknown> | null>(null);



  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cur, fc] = await Promise.all([api.seaIceCurrent(), api.seaIceForecast(horizon)]);
      setCurrent(cur ?? FALLBACK_SEA_ICE_CURRENT);
      setForecast(fc ?? { ...FALLBACK_SEA_ICE_FORECAST, horizon_hours: horizon });
    } catch (e) {
      console.warn("Sea-ice load notice:", e);
      setCurrent(FALLBACK_SEA_ICE_CURRENT);
      setForecast({ ...FALLBACK_SEA_ICE_FORECAST, horizon_hours: horizon });
    } finally {
      setLoading(false);
    }
  }, [horizon, toast]);



  const loadIntelligence = useCallback(async () => {

    const settle = <T,>(p: Promise<T>) => p.then((v) => ({ ok: true, value: v } as const)).catch(() => ({ ok: false, value: null } as const));

    const [cls, thick, keel, change, risk, trend] = await Promise.all([

      settle(api.seaIceClassification()), settle(api.seaIceThickness()), settle(api.seaIceKeelDepth()),

      settle(api.seaIceChange(horizon)),

      settle(api.seaIceRisk(horizon)), settle(api.seaIceClimateTrend()),

    ]);

    if (cls.ok) setClassificationData(cls.value as Record<string, unknown>);

    if (thick.ok) setThicknessData(thick.value as Record<string, unknown>);

    if (keel.ok) setKeelData(keel.value as Record<string, unknown>);

    if (change.ok) setChangeData(change.value as Record<string, unknown>);

    if (risk.ok) setRiskData(risk.value as Record<string, unknown>);

    if (trend.ok) setClimateTrendData(trend.value as Record<string, unknown>);

  }, [horizon]);



  useEffect(() => { load(); }, [load]);

  useEffect(() => { loadIntelligence(); }, [loadIntelligence]);



  // Let the assistant refresh this page using the same loader the button uses.

  useAssistantActionHandler("refresh_data", async () => {

    await load();

    await loadIntelligence();

    return { success: true, message: "Sea-ice forecast refreshed." };

  });



  const legendStops = useMemo(() => seaIceLegendStops(), []);



  if (loading) return <LoadingState message="Loading sea-ice forecast..." />;

  if (error) return <ErrorState message={error} retry={load} />;



  return (

    <div className="space-y-5">

      <AntarcticPageHeader
        title="Sea-Ice"
        titleHighlight="Forecast"
        subtitle="Antarctic Sea-Ice Observations · Predictive Intelligence · 120h Horizons"
        rightControls={
          <>
            <label className="text-xs text-navy-800 font-medium">Horizon:</label>
            <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-navy-700">
              {HORIZONS.map((h) => <option key={h} value={h}>{h}h</option>)}
            </select>
          </>
        }
      />





      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">

        {[

          {

            id: "mean",

            label: "Mean Concentration",

            value: forecast ? `${(forecast.mean_concentration * 100).toFixed(1)}%` : "—",

            icon: (

              <svg className="w-5 h-5 text-blue-600" viewBox="0 0 24 24" fill="currentColor">

                <rect x="3.5" y="10" width="3.5" height="11" rx="1.75" />

                <rect x="10.25" y="4" width="3.5" height="17" rx="1.75" />

                <rect x="17" y="10" width="3.5" height="11" rx="1.75" />

              </svg>

            ),

          },

          {

            id: "max",

            label: "Max Concentration",

            value: forecast ? `${(forecast.max_concentration * 100).toFixed(1)}%` : "—",

            icon: (

              <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">

                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />

              </svg>

            ),

          },

          {

            id: "coverage",

            label: "Coverage",

            value: forecast ? `${forecast.coverage_pct.toFixed(1)}%` : "—",

            icon: <ChartPieIcon className="w-5 h-5 text-blue-600" />,

          },

          {

            id: "model",

            label: "Model",

            value: forecast?.model ?? "—",

            icon: <Cog6ToothIcon className="w-5 h-5 text-blue-600" />,

          },

        ].map((s) => (

          <div

            key={s.label}

            className="relative overflow-hidden bg-white rounded-2xl border border-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.04)] p-3.5 flex items-center justify-between"

          >

            <div className="flex items-center gap-3.5 z-10 min-w-0">

              <div className="w-11 h-11 rounded-xl bg-blue-50/80 border border-blue-100/50 flex items-center justify-center shrink-0">

                {s.icon}

              </div>

              <div className="min-w-0">

                <p className="text-xs font-medium text-navy-500 truncate">{s.label}</p>

                <p className="text-lg font-bold text-navy-900 mt-0.5 tracking-tight truncate">{s.value}</p>

              </div>

            </div>

            <StatCardWave id={s.id} />

          </div>

        ))}

      </div>



      <div className="bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden">

        <div className="px-5 pt-4 pb-2 flex items-start justify-between">

          <div>

            <h3 className="text-sm font-semibold text-navy-900">Concentration Map</h3>

            <p className="text-[11px] text-navy-400">Forecast valid: {forecast?.forecast_time ? new Date(forecast.forecast_time).toLocaleString() : "—"}</p>

          </div>

        </div>

        <div className="px-5 pb-2">

          <div className="flex items-center gap-2 mb-1">

            <div className="flex items-center gap-1 flex-wrap">

              {legendStops.map((s, i) => (

                <div key={i} className="flex items-center gap-0.5">

                  <div className="w-6 h-3 rounded-sm" style={{ backgroundColor: s.color }} />

                  <span className="text-[10px] text-navy-500">{s.pct}%</span>

                </div>

              ))}

            </div>

          </div>

        </div>

        <div className="h-[400px]">

          <Antarctic3DGlobe

            seaIce={forecast ?? current}

            seaIceTimestamp={forecast?.forecast_time ?? current?.timestamp ?? null}

            seaIceHorizon={horizon}

            height="400px"

          />

        </div>

      </div>



      <div>

        <h2 className="text-base font-bold text-navy-900 mb-1 mt-6">Sea-Ice Details</h2>

        <p className="text-xs text-navy-400 mb-4">Estimates of ice type and thickness, how ice cover is changing, and longer-term patterns.</p>



        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

          <div className="bg-white rounded-xl border border-slate-200 shadow-card p-5">

            <SectionHeader

              title="Types of Ice"

              subtitle="Estimated share of each ice type"

              tag="Estimate"

              icon={<Square3Stack3DIcon className="w-4 h-4 text-blue-600" />}

            />

            <IceClassificationPanel data={classificationData} />

          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-card p-5">

            <SectionHeader

              title="Ice Thickness"

              subtitle="Estimated using ice-cover measurements"

              tag="Estimate"

              icon={<ArrowsUpDownIcon className="w-4 h-4 text-blue-600 stroke-[2]" />}

            />

            <ThicknessPanel data={thicknessData} />

          </div>

        </div>



        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

          <div className="bg-white rounded-xl border border-slate-200 shadow-card p-5">

            <SectionHeader

              title="Ice Below the Waterline"

              subtitle="Estimated depth and space beneath the ice"

              tag="Estimate"

              icon={<ArrowTrendingDownIcon className="w-4 h-4 text-blue-600 stroke-[2]" />}

            />

            <KeelDepthPanel data={keelData} />

          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-card p-5">

            <SectionHeader

              title="How Ice Cover Is Changing"

              subtitle={`Now compared with the ${horizon}-hour forecast`}

              tag="Forecast"

              icon={<ArrowPathIcon className="w-4 h-4 text-blue-600 stroke-[2]" />}

            />

            <ChangeDetectionPanel data={changeData} />

          </div>

        </div>



        <CollapsibleSection

          title="Long-Term Ice Cover and Risk"

          icon={<ShieldExclamationIcon className="w-4 h-4 text-blue-600" />}

        >

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

            <div>

              <SectionHeader

                title="Ice Cover Over Time"

                subtitle="Compared with past readings"

                icon={<CalendarDaysIcon className="w-4 h-4 text-blue-600" />}

              />

              <ClimateTrendPanel data={climateTrendData} />

            </div>

            <div>

              <SectionHeader

                title="Ice Conditions Risk"

                subtitle="Based on ice cover and forecast changes"

                icon={<ExclamationTriangleIcon className="w-4 h-4 text-blue-600" />}

              />

              <RiskPanel data={riskData} />

            </div>

          </div>

        </CollapsibleSection>

      </div>

    </div>

  );

}

